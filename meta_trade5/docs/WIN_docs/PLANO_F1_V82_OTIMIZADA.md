# PLANO DE IMPLEMENTAÇÃO — F1 V8.2 OTIMIZADA
## Parallel High-Performance Grid Search

**Data:** 2026-05-04  
**Versao Alvo:** V8.2 (sucessora da V8.1)  
**Objetivo:** 10-20x speedup + 90% memoria reduzida  

---

## 1. ARQUITETURA V8.2

### 1.1 Visao Geral

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN PROCESS (Coordinator)                │
├─────────────────────────────────────────────────────────────┤
│  1. Load parquet → Shared Memory (read-only)                │
│  2. Spawn N workers (default=10)                             │
│  3. Distribuir sinais para workers                          │
│  4. Collect results via Queue                               │
│  5. IO Thread salva resultados em background                 │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Worker 0     │   │  Worker 1     │   │  Worker N-1   │
│  (Process 0)  │   │  (Process 1)  │   │  (Process N)  │
├───────────────┤   ├───────────────┤   ├───────────────┤
│ Load signal   │   │ Load signal   │   │ Load signal   │
│ from shared   │   │ from shared   │   │ from shared   │
│ memory        │   │ memory        │   │ memory        │
│               │   │               │   │               │
│ Process all   │   │ Process all   │   │ Process all   │
│ 4032 combos   │   │ 4032 combos   │   │ 4032 combos   │
│               │   │               │   │               │
│ Keep Top N    │   │ Keep Top N    │   │ Keep Top N    │
│ in memory     │   │ in memory     │   │ in memory     │
│               │   │               │   │               │
│ Send Top N to │   │ Send Top N to │   │ Send Top N to │
│ Result Queue  │   │ Result Queue  │   │ Result Queue  │
└───────────────┘   └───────────────┘   └───────────────┘
```

### 1.2 Componentes Principais

| Componente | Responsabilidade | Implementacao |
|------------|------------------|---------------|
| **SharedMemory** | Parquet read-only compartilhado | `multiprocessing.shared_memory` |
| **Worker Pool** | Processamento paralelo | `multiprocessing.Pool(10)` |
| **Result Queue** | Coleta assincrona de resultados | `multiprocessing.Queue` |
| **IO Thread** | Save em background | `threading.Thread` + `queue.Queue` |
| **Top N Keeper** | Manter apenas melhores configs | `heapq.nlargest` |

---

## 2. OTIMIZACOES DETALHADAS

### 2.1 Shared Memory para Parquet (Read-Only)

**Problema V8.1:**
- Cada worker carrega proprio parquet = 21 × 130 MB = **2.7 GB duplicado**
- Race conditions potenciais

**Solucao V8.2:**
```python
from multiprocessing import shared_memory, Array
import numpy as np

# Main process
def load_parquet_to_shared(path):
    df = pl.read_parquet(path).to_pandas()
    
    # Criar shared arrays para cada coluna
    shared_arrays = {}
    for col in df.columns:
        arr = np.ascontiguousarray(df[col].values)
        shm = shared_memory.SharedMemory(create=True, size=arr.nbytes)
        shm_arr = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
        shm_arr[:] = arr[:]
        shared_arrays[col] = (shm, arr.shape, arr.dtype)
    
    return shared_arrays

# Worker process
def worker_init(shared_arrays):
    """Inicializar worker com acesso a shared memory."""
    global SHARED_DATA
    SHARED_DATA = {}
    for col, (shm, shape, dtype) in shared_arrays.items():
        existing_shm = shared_memory.SharedMemory(name=shm.name)
        SHARED_DATA[col] = np.ndarray(shape, dtype=dtype, buffer=existing_shm.buf)
```

**Beneficios:**
- ✅ **130 MB total** (vs 2.7 GB duplicado)
- ✅ **Zero copy** — workers acessam mesma memoria
- ✅ **Read-only seguro** — nenhum worker modifica dados

---

### 2.2 Worker Pool com 10 Workers

**Configuracao:**
```python
N_WORKERS = int(os.environ.get('F1_WORKERS', '10'))  # Default 10, via env

# Pool de processos
with Pool(processes=N_WORKERS, initializer=worker_init, initargs=(shared_arrays,)) as pool:
    # Distribuir sinais para workers
    results = pool.map_async(process_signal, PA_SIGNALS)
    
    # Processar resultados conforme chegam
    for result in results.get():
        process_result(result)
```

**Distribuicao de Trabalho:**
- 21 sinais / 10 workers = **2-3 sinais por worker**
- Cada worker processa **~766K configs** (2-3 sinais × 4032 combos)
- Tempo estimado por worker: **~45 segundos**

**Load Balancing:**
```python
# Dynamic load balancing via imap_unordered
for result in pool.imap_unordered(process_signal, PA_SIGNALS, chunksize=1):
    # Resultados chegam conforme completam
    collect_result(result)
```

---

### 2.3 Top N em Memoria (Por Sinal)

**Problema V8.1:**
- Acumula **16M rows** em memoria
- 5.6 GB pico de memoria

**Solucao V8.2:**
```python
import heapq

TOP_N_PER_SIGNAL = int(os.environ.get('F1_TOP_N', '1000'))  # Default 1000

def process_signal(signal_name):
    """Processa 1 sinal e retorna apenas Top N configs."""
    results = f1_screen_signal_vectorized(df, signal_name, direction=-1)
    
    # Manter apenas Top N por sinal
    top_n = heapq.nlargest(TOP_N_PER_SIGNAL, results, key=lambda x: x['net'])
    
    return {
        'signal': signal_name,
        'top_configs': top_n,
        'total_combos': len(results),
    }
```

**Beneficios:**
- ✅ **21 sinais × 1000 configs = 21,000 rows** (vs 16M)
- ✅ **~50 MB memoria** (vs 5.6 GB) — **99% reducao**
- ✅ **IO final 100x mais rapido** (20 MB vs 2.1 GB)

---

### 2.4 IO Thread Assincrono

**Problema V8.1:**
- `to_csv()` bloqueia execucao por 30-60s
- IO sincrono desperdica CPU

**Solucao V8.2:**
```python
import threading
import queue

class IOManager:
    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._io_worker, daemon=True)
        self.thread.start()
    
    def _io_worker(self):
        """Thread dedicada para IO."""
        while True:
            task = self.queue.get()
            if task is None:
                break
            
            df, path, callback = task
            df.to_csv(path, index=False)
            
            if callback:
                callback(path)
            
            self.queue.task_done()
    
    def save_async(self, df, path, callback=None):
        """Agendar save em background (nao bloqueia)."""
        self.queue.put((df, path, callback))
    
    def wait_completion(self):
        """Aguardar todos os saves pendentes."""
        self.queue.join()
        self.queue.put(None)
        self.thread.join()

# Uso
io_mgr = IOManager()

# Durante processamento — nao bloqueia
io_mgr.save_async(df_top100, 'F1_TOP100.csv', callback=on_save_complete)

# No final — aguardar
io_mgr.wait_completion()
```

**Beneficios:**
- ✅ **0 segundos bloqueando** — IO overlap com computacao
- ✅ **Throughput maximizado** — CPU e IO trabalham em paralelo

---

### 2.5 Cache-Friendly Loop (Batch Processing)

**Problema V8.1:**
- Loop acessa colunas aleatoriamente da memoria
- Cache misses frequentes

**Solucao V8.2:**
```python
def f1_screen_cache_friendly(df_dict, signal_name, direction=-1):
    """
    Processamento cache-friendly:
    1. Extrair TODOS os arrays de uma vez (contiguo em memoria)
    2. Processar em batches que cabem no L3 cache
    3. Minimizar acessos aleatorios
    """
    
    # Extrair arrays uma vez (contiguo)
    signal = np.ascontiguousarray(df_dict[signal_name], dtype=np.int32)
    atr = np.ascontiguousarray(df_dict['ATR'], dtype=np.float64)
    close = np.ascontiguousarray(df_dict['close'], dtype=np.float64)
    high = np.ascontiguousarray(df_dict['high'], dtype=np.float64)
    low = np.ascontiguousarray(df_dict['low'], dtype=np.float64)
    
    # Batch size otimizado para L3 cache (~8MB)
    # Cada batch: 100K rows × 5 arrays × 8 bytes = 4MB
    BATCH_SIZE = 100_000
    n_rows = len(signal)
    
    all_results = []
    
    for batch_start in range(0, n_rows, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, n_rows)
        
        # Processar batch inteiro (vetorizado)
        batch_results = _process_batch(
            signal[batch_start:batch_end],
            atr[batch_start:batch_end],
            close[batch_start:batch_end],
            high[batch_start:batch_end],
            low[batch_start:batch_end],
            direction
        )
        
        all_results.extend(batch_results)
    
    return all_results

def _process_batch(signal, atr, close, high, low, direction):
    """Processar 1 batch vetorizado."""
    # ... logica vetorizada existente ...
```

**Beneficios:**
- ✅ **L3 cache hit rate > 90%** (vs ~60% atual)
- ✅ **20-30% mais rapido** por worker
- ✅ **Pre-fetching automatico** da CPU

---

## 3. PARAMETRIZACAO

### 3.1 Variaveis de Ambiente

```bash
# Numero de workers (default: 10)
export F1_WORKERS=10

# Top N configs por sinal (default: 1000)
export F1_TOP_N=1000

# Batch size para cache (default: 100000)
export F1_BATCH_SIZE=100000

# Habilitar debug (default: false)
export F1_DEBUG=false
```

### 3.2 Config Default

```python
DEFAULT_CONFIG = {
    'n_workers': 10,
    'top_n_per_signal': 1000,
    'batch_size': 100_000,
    'use_shared_memory': True,
    'use_async_io': True,
    'debug': False,
}
```

---

## 4. ESTRUTURA DE ARQUIVOS

### 4.1 Arquivos Gerados

| Arquivo | Conteudo | Tamanho |
|---------|----------|---------|
| `f1_full_scan_v81_legacy.py` | Versao original (backup) | N/A |
| `f1_full_scan_v82.py` | Nova versao otimizada | N/A |
| `F1_FULL_RESULTS_V82.csv` | Top 1000 por sinal (21K rows) | ~20 MB |
| `F1_BEST_PER_SIGNAL_V82.csv` | Melhor config por sinal (21 rows) | ~2 KB |
| `F1_TOP100_GLOBAL_V82.csv` | Top 100 global | ~10 KB |
| `f1_performance_v82.txt` | Metricas de performance | ~1 KB |

### 4.2 Comparacao V8.1 vs V8.2

| Metrica | V8.1 (Legacy) | V8.2 (Otimizada) | Melhoria |
|---------|---------------|------------------|----------|
| **Tempo total** | 451s (7.5 min) | ~45s | **10x** |
| **Memoria pico** | 5.6 GB | ~500 MB | **11x** |
| **Arquivo final** | 2.1 GB (16M rows) | 20 MB (21K rows) | **105x** |
| **Workers** | 1 (single-thread) | 10 (multiprocessing) | **10x** |
| **IO blocking** | 60s | 0s (async) | **∞** |
| **Cache hit rate** | ~60% | ~90% | **1.5x** |

---

## 5. IMPLEMENTACAO PASSO-A-PASSO

### Passo 1: Backup da Versao Legacy (5 min)
```bash
cp f1_full_scan_v81.py f1_full_scan_v81_legacy.py
```

### Passo 2: Shared Memory Setup (30 min)
- Criar `load_parquet_to_shared()`
- Criar `worker_init()` para workers
- Testar acesso read-only

### Passo 3: Worker Pool (30 min)
- Criar `Pool(processes=10)`
- Implementar `process_signal()` para worker
- Testar com 2-3 sinais primeiro

### Passo 4: Top N Keeper (15 min)
- Implementar `heapq.nlargest()` por sinal
- Reduzir memoria acumulada
- Validar que top configs sao preservadas

### Passo 5: IO Thread (20 min)
- Criar classe `IOManager`
- Implementar `save_async()`
- Testar nao-bloqueio

### Passo 6: Cache-Friendly Loop (30 min)
- Implementar batch processing
- Otimizar para L3 cache
- Benchmark cache hit rate

### Passo 7: Integracao e Testes (30 min)
- Juntar todos componentes
- Teste completo com 21 sinais
- Validar performance e memoria

### Passo 8: Documentacao (15 min)
- Atualizar README
- Documentar variaveis de ambiente
- Criar exemplos de uso

**Tempo total estimado:** 2.5 horas

---

## 6. CRITÉRIOS DE ACEITACAO

### Performance
- [ ] Tempo total < 60s (vs 451s V8.1)
- [ ] Configs/segundo > 300,000 (vs 35,637 V8.1)
- [ ] CPU utilization > 80% (10+ cores ativos)

### Memoria
- [ ] Pico de memoria < 500 MB (vs 5.6 GB V8.1)
- [ ] Memoria por worker < 50 MB
- [ ] Shared memory < 150 MB

### Funcionalidade
- [ ] Mesmos top 100 configs que V8.1 (validar corretude)
- [ ] Top 1000 por sinal preservados
- [ ] IO assincrono nao bloqueia execucao
- [ ] Graceful shutdown em caso de erro

### Robustez
- [ ] Handler para worker crash
- [ ] Timeout por sinal (5 min max)
- [ ] Retry automatico em caso de falha
- [ ] Log detalhado de performance

---

## 7. RISCOS E MITIGACOES

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Shared memory corrompida | Baixa | Alto | Read-only + checksum |
| Worker deadlock | Media | Alto | Timeout + kill worker |
| Memoria exceder limite | Baixa | Medio | Top N rigoroso + GC |
| IO queue overflow | Baixa | Baixo | Queue size limit + backpressure |
| Resultados inconsistentes | Baixa | Alto | Validacao pos-execucao |

---

## 8. BENCHMARKS ESPERADOS

### Cenario 1: Full Scan (21 sinais, 16M configs)

| Metrica | V8.1 | V8.2 (target) |
|---------|------|---------------|
| Tempo | 451s | 45s |
| Memoria | 5.6 GB | 500 MB |
| CPU | 5% (1 core) | 80% (10 cores) |
| IO blocking | 60s | 0s |

### Cenario 2: Single Signal (766K configs)

| Metrica | V8.1 | V8.2 (target) |
|---------|------|---------------|
| Tempo | 21.5s | 2.5s |
| Memoria | 270 MB | 50 MB |
| Cache hit | 60% | 90% |

### Cenario 3: Memory Stress Test

| Carga | V8.1 | V8.2 (target) |
|-------|------|---------------|
| 10 sinais | 2.8 GB | 250 MB |
| 21 sinais | 5.6 GB | 500 MB |
| 50 sinais* | OOM | 1.2 GB |

\* Com sinais adicionais futuros

---

## 9. PROXIMOS PASSOS

1. **Aprovar este plano** — Confirmar arquitetura e targets
2. **Criar backup** — `f1_full_scan_v81_legacy.py`
3. **Implementar V8.2** — Seguir passos 2-8
4. **Validar benchmarks** — Rodar testes de performance
5. **Documentar** — Atualizar README e exemplos
6. **Deploy** — Substituir V8.1 por V8.2 (manter legacy como backup)

---

**Status:** Plano pronto para implementacao  
**Tempo estimado:** 2.5 horas  
**Risco:** Baixo (backup mantido, reversao facil)
