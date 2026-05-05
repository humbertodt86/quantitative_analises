# CHANGELOG de Documentacao

## 2026-05-02 — Atualizacao V6.6

### Arquivos Atualizados

| Arquivo | Mudanca |
|---------|---------|
| `AGENTS.md` | **REESCRITO.** Removido WDO (custo=1.2, VWAP_Z, DXY, super_wdo_M5). Focado em WIN (custo=30, super_win_continuous.parquet, 21 sinais PA_). Adicionado pipeline V6.6, GridAdvisor, Signal Discovery. |
| `GUIA_CICLOS_V66.md` | **NOVO.** Guia V6.6 completo. Substitui GUIA_CICLOS.md (V6.3). |
| `GUIA_CICLOS.md` | **MARCADO COMO DESATUALIZADO.** Adicionado aviso no topo apontando para GUIA_CICLOS_V66.md. |
| `DOCUMENTACAO_DADOS.md` | Atualizado contagem de colunas: 43 -> **154** (super_win_continuous.parquet). Adicionado nota sobre colunas novas. |

### Problemas Corrigidos nos Docs

| Problema | Arquivo | Correcao |
|----------|---------|----------|
| `numba_f1.py` nao existe | GUIA_CICLOS.md | Referencia correta: `engines/f1_fast_screener.py` |
| `correlation.py` nao existe | GUIA_CICLOS.md | Referencia correta: `scripts/dna_analysis.py` |
| `ensemble_v2.py` nao existe | GUIA_CICLOS.md | Funcionalidade integrada em `orchestrator_v65.py` |
| Custo=1.2 pts (WDO) | AGENTS.md | Corrigido para 30 pts (WIN) |
| 43 colunas no parquet | DOCUMENTACAO_DADOS.md | Corrigido para 154 colunas |
| V6.4 Autopilot como "futuro" | GUIA_CICLOS.md | Ja implementado na V6.6 |

### Arquivos Ainda Desatualizados (Proxima Iteracao)

| Arquivo | Versao | Problema |
|---------|--------|----------|
| `ENGINE_V2_DOCUMENTATION.md` | V134 | Faltam V139 + Layers 2/3/4 (ensemble, day-filter, risk manager) |
| `ENGINE_V2_TECHNICAL_REFERENCE.md` | WDO | Documentacao WDO legada, nao reflete WIN |
| `ARQUITETURA_V67_DRAFT.md` | Draft | Muitos "needed" features ja existem no codigo |
| `INVENTARIO_ESTRATEGIAS.md` | V5.1 | 5 versoes atras, resultados de pipeline antigo |

### Pendencias

- [ ] Re-escanear schema completo do `super_win_continuous.parquet` (154 colunas)
- [ ] Atualizar `ENGINE_V2_DOCUMENTATION.md` com V139 + 4 Layers
- [ ] Decidir: manter docs WDO ou arquivar?
- [ ] Atualizar `INVENTARIO_ESTRATEGIAS.md` com resultados V6.6
- [ ] Criar doc para `GridAdvisor` (`scripts/grid_advisor.py`)
