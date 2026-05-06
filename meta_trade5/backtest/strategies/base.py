"""Classe base para estratégias de backtest."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Strategy:
    """Parâmetros completos de uma estratégia dual-mode EMA20.

    Subclasses sobrescrevem os atributos de classe com seus defaults.
    Instâncias podem ser criadas com overrides individuais para grid search.

    Compatibilidade retroativa:
        V84/V85 usam gatilho_min e gatilho_max (campos legados).
        V86+    usam gatilho_min_range / gatilho_min_trend e gatilho_max_atr_mult.
        O engine detecta qual campo usar com base em gatilho_min_range > 0.
    """
    name: str = "base"

    # ── Filtros de entrada ────────────────────────────────────────────────────
    adx_period: int      = 14        # período do ADX (7 → mais rápido, mais ruído)
    adx_threshold: float = 25.0      # limiar RANGE↔TREND
    use_adx7: bool       = False     # True → usa coluna ADX7, False → ADX<period>

    # ── Gatilhos V84/V85 (legados — use _range/_trend em novos estratégias) ──
    # Mantidos para compatibilidade reversa. Se gatilho_min_range > 0, o engine
    # usa os campos separados; caso contrário usa gatilho_min (legado).
    gatilho_min: int     = 150       # dist mínima EMA20 (usado por V84/V85)
    gatilho_max: int     = 700       # dist máxima EMA20 (RANGE only, legado)

    # ── Gatilhos V86+ (separados por modo) ───────────────────────────────────
    # Quando gatilho_min_range > 0 (V86+), o engine ignora gatilho_min.
    gatilho_min_range: int   = 0     # 0 = usa gatilho_min legado
    gatilho_min_trend: int   = 0     # 0 = usa gatilho_min legado
    # GATILHO_MAX dinâmico: se None, usa gatilho_max fixo; caso contrário ATR×mult
    gatilho_max_atr_mult: float = 0.0       # TREND gmax (e RANGE se range_mult=0); 0=off
    gatilho_max_range_atr_mult: float = 0.0 # RANGE gmax separado (V89+); 0=usa gmax_atr_mult

    # ── Filtro de ADX máximo (V87+) ───────────────────────────────────────────
    adx_max: float = 9999.0          # sem limite por padrão; V87 WIN usa 50

    # ── Cooldown pós-SL (V87+) ────────────────────────────────────────────────
    cooldown_candles: int = 0        # candles M5 de espera após SL; 0 = off

    # ── Filtro de slope EMA para RANGE ───────────────────────────────────────
    atr_max: float       = 550.0     # ATR máximo permitido
    atr_min: float       = 0.0       # ATR mínimo (0 = sem filtro); V88+: 250 bloqueia tarde fraca
    ema_slope_max: float = 80.0      # filtro de slope para RANGE

    # ── TP/SL multipliers (sobre ATR) ────────────────────────────────────────
    tp_range_mult: float = 1.4
    sl_range_mult: float = 0.8
    tp_trend_mult: float = 1.5
    sl_trend_mult: float = 0.8

    # ── H-Progress ────────────────────────────────────────────────────────────
    progress_candles: int    = 2     # candles M5 sem progresso → ação
    progress_m1_candles: int = 4     # candles M1 sem progresso → ação (se use_m1_progress)
    progress_threshold: float = 0.15 # fração do TP que deve estar percorrida
    progress_mode: str   = "BE"      # "BE" ou "TP30"
    progress_tp_pct: float = 0.30    # fração do TP original como alvo parcial (TP30%)
    grace_candles: int   = 3         # candles de graça para TP30% antes de ir a BE
    be_offset: int       = 10        # pontos do BE acima do entry
    use_m1_progress: bool = False    # True → H-Progress em M1 (mais rápido)

    # ── H-Slope Decay (TREND only) ────────────────────────────────────────────
    slope_decay_factor: float = 0.65  # slope cai abaixo de 65% do entry slope → BE

    # ── Bloqueio de RANGE por horário (V88+) ─────────────────────────────────
    # Lista de tuplas (hora_inicio, hora_fim) em que RANGE é bloqueado.
    # Formato: float BRT (9.5 = 09:30, 14.5 = 14:30). None = sem bloqueio.
    # Não pode ser um field mutável no dataclass base; use None e sobrescreva na subclasse.
    range_hora_bloqueio: object = None

    # ── Circuit Breaker ───────────────────────────────────────────────────────
    max_sl_consec: int = 3

    def adx_col(self) -> str:
        """Nome da coluna ADX a ser usada no DataFrame de indicadores."""
        if self.use_adx7:
            return "ADX7"
        return f"ADX{self.adx_period}"

    def use_tp30(self) -> bool:
        return self.progress_mode == "TP30"

    def resolve_gatilho_min(self, mode: str) -> int:
        """Retorna o gatilho mínimo correto para o modo dado."""
        if mode == "RANGE":
            return self.gatilho_min_range if self.gatilho_min_range > 0 else self.gatilho_min
        else:
            return self.gatilho_min_trend if self.gatilho_min_trend > 0 else self.gatilho_min

    def entry_allowed(self, c: dict, mode: str, signal: str) -> bool:
        """Hook de filtro extra. Retorna False para bloquear entrada.
        V91 e anteriores retornam True sempre. V92+ sobrescreve para RSI/BB/VWAP."""
        return True

    def resolve_gatilho_max(self, atr: float, mode: str = "TREND") -> float:
        """Retorna o gatilho máximo: dinâmico (ATR×mult) ou fixo, por modo."""
        if mode == "RANGE" and self.gatilho_max_range_atr_mult > 0:
            return atr * self.gatilho_max_range_atr_mult
        if self.gatilho_max_atr_mult > 0:
            return atr * self.gatilho_max_atr_mult
        return float(self.gatilho_max)
