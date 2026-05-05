# PLANO DE IMPLEMENTAÇÃO — F1 V8.3 GPU (RTX 4060 8GB)
## GPU-Accelerated Grid Search com CuPy CUDA

**Data:** 2026-05-04  
**GPU:** NVIDIA GeForce RTX 4060 Laptop GPU (8GB VRAM, 3072 CUDA cores)  
**Objetivo:** 100-500x speedup vs CPU (451s → 1-5s)  

---

## 1. ARQUITETURA V8.3 GPU

### 1.1 Visao Geral

```
┌─────────────────────────────────────────────────────────────┐
│                    CPU (Host)                                │
│  1. Load parquet da RAM (130 MB)                             │
│  2. Transferir para GPU VRAM via PCI-E 3.0 x16              │
│     - Throughput: ~32 GB/s (teorico), ~25 GB/s (real)        │
│     - Tempo: 130 MB / 25 GB/s = ~5ms                         │
│  3. Lancar kernel GPU                                         │
│  4. Aguardar completacao                                      │
│  5. Transferir resultados de volta (21K rows × 11 cols)       │
│     - Tempo: < 1ms                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ PCI-E 3.0 x16 (~25 GB/s)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    GPU (RTX 4060 8GB)                        │
│  3072 CUDA cores @ 2.6 GHz                                   │
│  8GB GDDR6 VRAM                                              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Kernel 1: Signal Mask (vetorizado)                   │   │
│  │  - 2000 rows × 21 sinais = 42K threads                │   │
│  │  - Tempo: ~0.1ms                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Kernel 2: Grid Search (massivamente paralelo)        │   │
│  │  - 4032 combos × 2000 rows = 8M threads               │   │
│  │  - Blocos: 256 threads × 32000 blocos                 │   │
│  │  - Tempo: ~10-50ms                                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Kernel 3: Top-K Reduction (por sinal)                │   │
│  │  - 21 sinais × 1000 top = 21K threads                 │   │
│  │  - Tempo: ~0.5ms                                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Pipeline de Execucao

| Fase | Operacao | Tempo Estimado |
|------|----------|----------------|
| 1 | Load parquet (CPU RAM) | 100ms |
| 2 | Transfer CPU → GPU (PCI-E) | 5ms |
| 3 | Signal mask kernel | 0.1ms |
| 4 | Grid search kernel | 50ms |
| 5 | Top-K reduction | 0.5ms |
| 6 | Transfer GPU → CPU (PCI-E) | 1ms |
| 7 | Save CSV (IO) | 100ms |
| **TOTAL** | | **~157ms** |

**Target:** < 500ms (vs 451s V8.1 = **900x speedup**)

---

## 2. OTIMIZACOES GPU-SPECIFIC

### 2.1 Memoria VRAM (8GB)

**Alocacao estimada:**

| Array | Tamanho | Memoria |
|-------|---------|---------|
| `close` (2000 rows, float32) | 2000 × 4 bytes | 8 KB |
| `high` (2000 rows, float32) | 2000 × 4 bytes | 8 KB |
| `low` (2000 rows, float32) | 2000 × 4 bytes | 8 KB |
| `atr` (2000 rows, float32) | 2000 × 4 bytes | 8 KB |
| `signal` (2000 rows, int32) | 2000 × 4 bytes | 8 KB |
| `results` (8M combos, struct) | 8M × 32 bytes | 256 MB |
| `temp buffers` | N/A | 50 MB |
| **TOTAL** | | **~340 MB** |

**Margem de seguranca:** 8GB - 340MB = **7.66 GB livres**

**Expansao possivel:**
- Aumentar grid: 12×8×6×7 = 4032 → 20×15×10×10 = 30,000 combos
- Aumentar rows: 2000 → 10,000 rows (5x mais dados)
- **Cenario maximo:** 30,000 × 10,000 = 300M combos (~12GB, requer streaming)

### 2.2 CUDA Kernel Design

#### Kernel 1: Signal Mask (Preprocessing)

```python
@cp.fuse
def signal_mask_kernel(signal, atr, direction, out):
    """Calcular mascara de sinais validos."""
    idx = cp.cuda.blockIdx.x * cp.cuda.blockDim.x + cp.cuda.threadIdx.x
    if idx < len(signal):
        out[idx] = (signal[idx] == direction) and (not cp.isnan(atr[idx]))
```

**Threads:** 2000 (1 por row)  
**Tempo:** < 0.1ms

#### Kernel 2: Grid Search (Main computation)

```python
@cp.elementwise
def grid_search_kernel(
    close, high, low, atr, valid_idx,
    tp_grid, sl_grid, atr_min_grid, atr_max_grid,
    out_net, out_n, out_wr, out_count
):
    """
    Cada thread processa 1 combo (tp, sl, atr_min, atr_max).
    Thread block: 256 threads
    Grid: (num_combos + 255) // 256 blocos
    """
    combo_idx = i
    num_combos = len(tp_grid) * len(sl_grid) * len(atr_min_grid) * len(atr_max_grid)
    
    if combo_idx >= num_combos:
        return
    
    # Decodificar combo_idx para (tp, sl, atr_min, atr_max)
    tp_idx = combo_idx % len(tp_grid)
    sl_idx = (combo_idx // len(tp_grid)) % len(sl_grid)
    atr_min_idx = (combo_idx // (len(tp_grid) * len(sl_grid))) % len(atr_min_grid)
    atr_max_idx = combo_idx // (len(tp_grid) * len(sl_grid) * len(atr_min_grid))
    
    tp = tp_grid[tp_idx]
    sl = sl_grid[sl_idx]
    atr_min = atr_min_grid[atr_min_idx]
    atr_max = atr_max_grid[atr_max_idx]
    
    # Processar todas as rows validas (vetorizado)
    net = 0.0
    n = 0
    wins = 0
    
    for row_idx in range(len(valid_idx)):
        i = valid_idx[row_idx]
        # ... logica de simulacao ...
        net += pnl
        n += 1
        if pnl > 0:
            wins += 1
    
    # Atomic write (sem race condition)
    out_net[combo_idx] = net
    out_n[combo_idx] = n
    out_wr[combo_idx] = (wins / n * 100) if n > 0 else 0
    out_count[combo_idx] = 1
```

**Threads:** 4032 (1 por combo) × 2000 rows = **8M operacoes paralelas**  
**Tempo:** 10-50ms (dependendo de otimizacoes)

#### Kernel 3: Top-K Reduction

```python
def top_k_reduction(results, k=1000):
    """
    Para cada sinal, manter apenas top K configs por net PnL.
    Usar thrust::sort_by_key + slice.
    """
    # CuPy tem cupy.argsort para GPU sorting
    sorted_idx = cp.argsort(-results['net'])  # Descending
    top_k_idx = sorted_idx[:k]
    return results[top_k_idx]
```

**Threads:** 21K (1 por resultado)  
**Tempo:** < 0.5ms

### 2.3 Otimizacoes de Memoria

#### Shared Memory (L1 cache)

```python
# Usar shared memory para grids (reutilizados por todas threads)
TP_SHARED = cp.cuda.SharedMemory(12 * 4)  # 12 TP values × 4 bytes
SL_SHARED = cp.cuda.SharedMemory(8 * 4)   # 8 SL values × 4 bytes
# ... carregar uma vez, usar por todo o kernel ...
```

**Beneficio:** 100x mais rapido que global memory

#### Register Tiling

```python
# Cada thread carrega blocos de rows para registers
BLOCK_SIZE = 32  # Rows por batch
for batch_start in range(0, num_rows, BLOCK_SIZE):
    # Carregar batch para registers
    local_close = close[batch_start:batch_start+BLOCK_SIZE]
    # Processar batch inteiro
    # ...
```

**Beneficio:** Reduz acessos a memoria global

### 2.4 Async Transfers (Overlap)

```python
stream1 = cp.cuda.Stream()
stream2 = cp.cuda.Stream()

with stream1:
    # Transferir dados para GPU
    d_close = cp.asarray(h_close)
    d_high = cp.asarray(h_high)
    # ...

with stream2:
    # Processar kernel
    grid_search_kernel(...)
    # Transferir resultados de volta
    h_results = cp.asnumpy(d_results)

# Streams executam em paralelo (overlap transfer + compute)
stream1.synchronize()
stream2.synchronize()
```

**Beneficio:** Esconder latencia de transferencia PCI-E

---

## 3. ESTRATEGIA DE IMPLEMENTACAO

### 3.1 Abordagem Hibrida (CPU + GPU)

```
CPU (Python):
- Load parquet
- Pre-processamento (filtros basicos)
- Post-processamento (save CSV)
- Orchestracao

GPU (CuPy):
- Signal mask calculation
- Grid search (90% do tempo)
- Top-K reduction
```

### 3.2 Fases de Implementacao

#### Fase 1: Basico Funcional (30 min)
- [ ] Setup CuPy e alocacao de memoria GPU
- [ ] Transferencia CPU → GPU
- [ ] Kernel grid search basico (nao otimizado)
- [ ] Transferencia GPU → CPU
- [ ] Validar corretude (comparar com V8.1)

#### Fase 2: Otimizacao (30 min)
- [ ] Shared memory para grids
- [ ] Register tiling
- [ ] Block size optimization (256 vs 512 vs 1024 threads)
- [ ] Loop unrolling

#### Fase 3: Advanced (30 min)
- [ ] Async streams (overlap transfer + compute)
- [ ] Multi-GPU support (se disponivel)
- [ ] Streaming para grids > 8GB

#### Fase 4: Benchmark (15 min)
- [ ] Comparar vs V8.1 (451s)
- [ ] Comparar vs V8.2 (12.5s)
- [ ] Profiling GPU (nvprof ou Nsight)
- [ ] Documentar resultados

**Tempo total:** 1.75 horas

---

## 4. BENCHMARKS ESPERADOS

### Cenario 1: Full Scan (21 sinais, 16M configs)

| Metrica | V8.1 CPU | V8.2 CPU (10 workers) | V8.3 GPU (RTX 4060) | Speedup |
|---------|----------|----------------------|---------------------|---------|
| **Tempo total** | 451s | 12.5s | **~0.5s** | **900x** |
| **Configs/s** | 35K | 6.6K* | **32M** | **900x** |
| **Memoria** | 5.6 GB | 500 MB | **340 MB (VRAM)** | **16x** |
| **Energia** | ~100W | ~150W | **~200W (GPU)** | N/A |

\* V8.2 conta apenas grid combos, nao rows × combos

### Cenario 2: Expanded Grid (100M configs)

| Metrica | V8.1 CPU | V8.2 CPU | V8.3 GPU |
|---------|----------|----------|----------|
| **Tempo** | 47 min | 15 min | **~3s** |
| **Viavel?** | Sim | Sim | **Sim** |

### Cenario 3: Massive Grid (1B configs)

| Metrica | V8.1 CPU | V8.2 CPU | V8.3 GPU |
|---------|----------|----------|----------|
| **Tempo** | 7.8 horas | 2.5 horas | **~30s** |
| **Viavel?** | Sim | Sim | **Sim (com streaming)** |

---

## 5. LIMITACOES E WORKAROUNDS

### Limitacao 1: 8GB VRAM

**Problema:** Grid > 8GB nao cabe na VRAM

**Solucao: Streaming**
```python
# Dividir grid em chunks
num_chunks = ceil(total_combos / MAX_COMBOS_PER_CHUNK)
for chunk_idx in range(num_chunks):
    # Processar chunk na GPU
    process_chunk(chunk_idx, chunk_size)
    # Salvar resultados parciais
    save_partial_results(chunk_idx)
    # Limpar VRAM
    cp.get_default_memory_pool().free_all_blocks()
```

### Limitacao 2: PCI-E Bottleneck

**Problema:** Transferencia CPU ↔ GPU pode dominar tempo total

**Solucao: Minimizar transfers**
- Load once, process multiple times (reutilizar dados na VRAM)
- Batch multiple signals together
- Async streams para overlap

### Limitacao 3: Precision Float32

**Problema:** Float32 tem 7 digitos de precisao (vs Float64 com 15)

**Solucao:**
- Usar Float32 para PnL (suficiente para pts)
- Usar Float64 apenas para acumuladores criticos
- Validar que erro < 0.01%

---

## 6. CRITÉRIOS DE ACEITACAO

### Performance
- [ ] Tempo total < 5s (vs 451s V8.1)
- [ ] Speedup > 100x vs V8.1
- [ ] Speedup > 10x vs V8.2 (CPU 10 workers)
- [ ] GPU utilization > 80% (nsight profiling)

### Memoria
- [ ] VRAM usage < 6GB (de 8GB)
- [ ] Zero OOM errors
- [ ] Streaming funciona para grids > 8GB

### Funcionalidade
- [ ] Mesmos top 100 configs que V8.1 (validar corretude)
- [ ] Tolerancia de 0.1% no PnL (float32 precision)
- [ ] Graceful shutdown em caso de erro

### Robustez
- [ ] Handler para GPU crash
- [ ] Fallback para CPU se GPU indisponivel
- [ ] Log detalhado de performance

---

## 7. RISCOS E MITIGACOES

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| CuPy incompativel | Baixa | Alto | Fallback para V8.2 CPU |
| VRAM insuficiente | Media | Alto | Streaming automatico |
| PCI-E bottleneck | Media | Medio | Async streams + batching |
| Precision float32 | Baixa | Baixo | Validacao pos-execucao |
| GPU overheating | Baixa | Medio | Throttling automatico |

---

## 8. ARQUIVOS GERADOS

| Arquivo | Conteudo |
|---------|----------|
| `f1_full_scan_v83_gpu.py` | Implementacao GPU |
| `f1_full_scan_v83_hybrid.py` | Versao hibrida (CPU + GPU) |
| `F1_FULL_RESULTS_V83.csv` | Resultados GPU |
| `f1_benchmark_v81_v82_v83.md` | Comparativo 3 versoes |

---

## 9. PROXIMOS PASSOS

1. **Implementar Fase 1** — Basico funcional (30 min)
2. **Validar corretude** — Comparar com V8.1 (15 min)
3. **Otimizar (Fase 2-3)** — Shared memory, streams (60 min)
4. **Benchmark (Fase 4)** — Comparar vs V8.1/V8.2 (15 min)
5. **Documentar** — Relatorio final (15 min)

**Tempo total:** 2.25 horas

---

**Status:** Plano pronto para implementacao  
**Target:** 451s → 0.5s (900x speedup)  
**Risco:** Baixo (fallback para V8.2 CPU)
