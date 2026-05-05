"""Configuração de instrumentos suportados pelo framework de backtest.

Convenção de timezone:
    Os arquivos de tick exportados pelo MT5 usam BRT codificado como epoch UTC
    (utcfromtimestamp retorna hora BRT diretamente). Os CSVs de candle também
    têm horários em BRT. Nunca aplicar conversão de timezone sobre esses dados.
    hora_start / hora_limit / hora_panic são todos em BRT.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class InstrumentConfig:
    # ── Fontes de dados ──────────────────────────────────────────────────────
    tick_file: str         # arquivo CSV de ticks (data/ticks/...)
    candle_file: str       # arquivo CSV OHLC longo (data/candles/IND$_M5.csv)
    candle_file_recent: str = ""    # arquivo OHLC M5 do contrato atual (atualizar via ExportM5Bars.mq5)
    candle_m1_recent:  str = ""    # arquivo OHLC M1 do contrato atual (opcional — para H-Progress)
    indicators_file:   str = ""    # CSV de indicadores exportado pelo BOT durante backtest (ground truth MT5)
                                   # ATENÇÃO: usar o CSV gerado pelo próprio robô (v7.01+), NÃO pelo ExportIndicators.mq5
                                   # Ver MT5_PYTHON_ALINHAMENTO.md seção 4.1 para detalhes

    # ── Horários BRT ────────────────────────────────────────────────────────
    hora_start: float = 9.5    # hora mínima para aceitar entradas (9:30 BRT)
    hora_limit: float = 17.5   # hora corte de novas entradas (17:30 BRT)
    hora_panic: float = 17 + 55 / 60  # fechamento forçado (17:55 BRT)

    # ── Filtros de volatilidade ──────────────────────────────────────────────
    atr_max: float = 550.0     # ATR máximo permitido para entrada

    # ── Gatilhos padrão (sobrescritos pela Strategy) ─────────────────────────
    # Mantidos apenas como fallback para estratégias antigas (V84/V85).
    # V86+ usam gatilho_min_range/gatilho_min_trend diretamente na Strategy.
    gatilho_min: int = 150     # dist mínima da EMA (DEFAULT — sobreposto por Strategy)
    gatilho_max: int = 700     # dist máxima da EMA (DEFAULT — sobreposto por Strategy)

    # ── Escala financeira ────────────────────────────────────────────────────
    valor_ponto: float = 0.20  # valor em R$ de 1 ponto (WIN = R$0.20)
    custo_trade: float = 2.0   # custo de corretagem por trade (R$)


INSTRUMENTS: dict[str, InstrumentConfig] = {
    "WIN": InstrumentConfig(
        # ── Dados ────────────────────────────────────────────────────────────
        # tick_file: arquivo completo Mar30-Abr15/2026 (1.73 GB, 26.8M ticks)
        # candle_file: série histórica longa ago/2022-atual (IND$ contínuo)
        # candle_file_recent: contrato atual Jan-Abr/2026 (atualizar do MT5)
        tick_file="data/raw/ticks/WINJ26_ticks.csv",
        candle_file="data/candles/IND$_M5.csv",
        candle_file_recent="data/candles/WINJ26_M5.csv",
        candle_m1_recent="data/candles/WINJ26_M1.csv",
        # indicators_file: gerado pelo bot durante Strategy Tester
        # V91: Ind_V91_v7.00_WINJ26_2026.01.02.csv (bot v7.01, ground truth MT5)
        # V92: após rodar v92_win.mq5 no Strategy Tester, copiar Ind_V92_v1.00_*.csv aqui
        indicators_file="data/candles/Ind_V94_v1.00_WINJ26_2026.01.02.csv",
        # ── Horários BRT ─────────────────────────────────────────────────────
        # WIN: abre 10:00 BRT, mas bot checa desde 9:30 (tolerância)
        hora_start=9.5,
        hora_limit=17.5,
        hora_panic=17 + 55 / 60,
        # ── Filtros ──────────────────────────────────────────────────────────
        atr_max=550.0,
        gatilho_min=150,   # fallback V84
        gatilho_max=700,   # fallback V84
        valor_ponto=0.20,
        custo_trade=2.0,
    ),
    "WDO": InstrumentConfig(
        # WDO$ contínuo — dados disponíveis set/2022-abr/2026 (~100k barras M5)
        # Preço em pontos (USD cents × 10), ex: 5971 pts = USD 5.971
        # ATR M5 médio: 6.3pts | p50=5.0 | p90=11.0
        # dist EMA20 M5: escala semelhante (~3-8 pts)
        # tick: usar ticks do WDOK26 quando exportados do MT5
        tick_file="data/ticks/WDOK26_ticks.csv",          # TODO: exportar ticks do MT5
        candle_file="data/candles/WDO$_M5.csv",            # disponível set/2022-abr/2026
        candle_file_recent="data/candles/WDOK26_M5.csv",   # TODO: exportar contrato atual
        hora_start=9.0,
        hora_limit=17.5,
        hora_panic=17 + 55 / 60,
        atr_max=15.0,       # p99 do ATR M5 ~ 14pts
        gatilho_min=3,      # dist mínima EMA20 (provisório — calibrar com grid)
        gatilho_max=20,     # dist máxima EMA20 (provisório — calibrar com grid)
        valor_ponto=10.0,   # R$10 por ponto (1 lote mini)
        custo_trade=0.30,   # custo em R$ por trade (estimado)
    ),
}
