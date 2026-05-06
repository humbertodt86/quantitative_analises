"""Engine V119 — Hybrid Intensity v2 (Wrapper around V109).

Changes from V109:
1. Sniper: GK_Ratio > 1.3 ignition + Z-Score < 2.2 exhaustion block
   ADX reduced 28->22, Slope 28->18 (early entry compensated by GK gate)
2. BE Trigger: Profit >= 1.0x ATR -> move SL to Entry + 15
3. H-Progress Inertia: Duration >= 6 candles AND profit < 40pts -> close market
4. Hunter: unchanged from V109 (workhorse proven at +6,094 pts March OOS)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional

from .engine_tick_real import _build_tick_index
from .config import InstrumentConfig
from .strategies.base import Strategy
from .engine import Position, _make_trade

# =====================================================================
# V119 Feature Prep (GK + Z-Score)
# =====================================================================

def add_gk(df: pd.DataFrame) -> pd.DataFrame:
    o=df["open"].values.astype(float); h=df["high"].values.astype(float)
    l=df["low"].values.astype(float); c=df["close"].values.astype(float)
    n=len(df); gk=np.zeros(n)
    for i in range(1,n):
        if o[i]>0 and l[i]>0:
            hr=h[i]/max(l[i],1e-9); cr=c[i]/max(o[i],1e-9)
            if hr>0 and cr>0:
                t1=0.5*np.log(hr)**2; t2=(2*np.log(2)-1)*np.log(cr)**2
                gk[i]=np.sqrt(max(t1-t2,0))
    df["GK_VOL"]=gk
    gk_vol=pd.Series(gk).ffill().fillna(0)
    gk_sma=gk_vol.rolling(20,min_periods=5).mean()
    df["GK_RATIO"]=(gk_vol/gk_sma.replace(0,np.nan)).fillna(1.0).clip(0.2,5.0)
    return df

def add_zscore(df: pd.DataFrame) -> pd.DataFrame:
    close=df["close"].astype(float)
    if "EMA20" not in df.columns: df["EMA20"]=close.ewm(span=20,adjust=False).mean()
    dev=close-df["EMA20"]
    df["ZSCORE_EMA"]=(dev/dev.rolling(20,min_periods=5).std().replace(0,np.nan)).fillna(0)
    return df

def prepare_v119_features(m5_ind, strategy, gt_cfg=None):
    from .engine_v108 import prepare_v108_features
    m5=prepare_v108_features(m5_ind,strategy,gt_cfg=gt_cfg)
    m5=add_gk(m5)
    m5=add_zscore(m5)
    return m5

# =====================================================================
# OHLC-only Exit Simulator (when tick data is not available)
# =====================================================================

def _simulate_exit_ohlc(records, i, N, signal, ep, tp_pts, sl_pts,
                        hp_candles=2, hp_th=0.15, be_trigger_pts=250, be_offset=50):
    """Simplified exit simulation using OHLC only (no tick-level data)."""
    pnl = 0
    hit_type = "SL"
    mfe = 0.0
    mae = 0.0
    be_active = False
    be_sl_price = None
    candles_in_trade = 0
    exit_j = i + 1
    be_trigger_atr = max(be_trigger_pts, 300)

    for j in range(i + 1, min(i + 50, N)):
        cj = records[j]
        candles_in_trade += 1
        exit_j = j

        # Calculate MFE/MAE for this candle
        if signal == "BUY":
            bar_mfe = float(cj["high"]) - ep
            bar_mae = ep - float(cj["low"])
        else:
            bar_mfe = ep - float(cj["low"])
            bar_mae = float(cj["high"]) - ep

        mfe = max(mfe, bar_mfe)
        mae = max(mae, bar_mae)

        # Check BE trigger
        if not be_active and mfe >= be_trigger_atr:
            be_active = True
            if signal == "BUY":
                be_sl_price = ep + be_offset
            else:
                be_sl_price = ep - be_offset

        # Determine exit price
        if signal == "BUY":
            # Check SL first
            if float(cj["low"]) <= ep - sl_pts:
                pnl = -sl_pts
                hit_type = "SL"
                break
            # Check BE
            if be_active and float(cj["low"]) <= be_sl_price:
                pnl = int(be_sl_price - ep)
                hit_type = "BE"
                break
            # Check TP (CORRECAO 2026-05-05: usa high real, nao threshold fixo)
            if float(cj["high"]) >= ep + tp_pts:
                pnl = int(float(cj["high"]) - ep)
                hit_type = "TP"
                break
        else:  # SELL
            # Check SL first
            if float(cj["high"]) >= ep + sl_pts:
                pnl = -sl_pts
                hit_type = "SL"
                break
            # Check BE
            if be_active and float(cj["high"]) >= be_sl_price:
                pnl = int(ep - be_sl_price)
                hit_type = "BE"
                break
            # Check TP (CORRECAO 2026-05-05: usa low real, nao threshold fixo)
            if float(cj["low"]) <= ep - tp_pts:
                pnl = int(ep - float(cj["low"]))
                hit_type = "TP"
                break

    # If no exit found, close at last candle close
    if pnl == 0 and hit_type == "SL":
        cj = records[exit_j]
        if signal == "BUY":
            pnl = int(float(cj["close"]) - ep)
        else:
            pnl = int(ep - float(cj["close"]))
        hit_type = "HSTAG"

    return pnl, hit_type, mfe, mae, exit_j


# =====================================================================
# Modified Exit Simulator (BE at 1.0xATR + H-Progress Inertia)
# =====================================================================

def _simulate_exit_v119(records, bid_arr, ask_arr, tick_idx, i, N,
                         signal, ep, tp_pts, sl_pts, be_structural, be_offset,
                         mode, hard_stop, atr_val,
                         hp_candles=2, hp_th=0.15, tp30_pct=0.30, grace_candles=2, be_trigger_pts=250,
                         entry_slope=None, slope_decay_pct=0.50, trailing_pct=0.50,
                         decay_factor=0.50, min_tp_pct=0.20, use_dynamic_decay=False):
    """V139 exit: BE, TP30, BE Progress, Slope Decay, Trailing Stop.

    Returns: pnl, hit_type, mfe, mae, exit_j, candles_in_trade, be_triggered, tp30_triggered, slope_decay_triggered, progressed_flag, trailing_triggered
    """
    pnl=0; hit_type="SL"; mfe=0.0; mae=0.0; be_active=False; be_sl_price=None
    candles_in_trade=0; tp30_active=False; grace_count=0; progressed=False; slope_decayed=False
    be_trigger_atr=max(be_trigger_pts, atr_val * 1.0)
    current_tp = tp_pts
    exit_j = i + 1

    # V7.4.6: Flags for diagnostics
    be_triggered_flag = False
    tp30_triggered_flag = False
    slope_decay_triggered_flag = False
    progressed_flag = False
    trailing_triggered_flag = False
    trailing_sl_price = None

    for j in range(i+1, min(i+50, N)):
        cj=records[j]; candles_in_trade+=1; exit_j = j
        bid_bar=bid_arr[tick_idx[j][0]:tick_idx[j][1]]
        ask_bar=ask_arr[tick_idx[j][0]:tick_idx[j][1]]

        if signal=="BUY":
            bar_mfe=float(cj["high"])-ep; bar_mae=ep-float(cj["low"])
        else:
            bar_mfe=ep-float(cj["low"]); bar_mae=float(cj["high"])-ep
        mfe=max(mfe,bar_mfe); mae=max(mae,bar_mae)

        # ── DYNAMIC SLOPE DECAY (Momentum-Based) ───────────────────────────
        # Mt = max(min_tp_pct, 1.0 - decay_factor * (S0 - St) / S0)
        # TP_effective = TP_original * Mt
        # Recalculated every M5 candle based on EMA20_SLOPE momentum
        # ────────────────────────────────────────────────────────────────────
        if use_dynamic_decay and entry_slope is not None:
            S0 = entry_slope
            St = float(cj.get("EMA20_SLOPE", 0) or 0)
            if abs(S0) > 1e-9:
                # Calculate momentum decay ratio
                # (S0 - St) / S0: how much momentum has decayed
                # For BUY: S0>0, if St drops → ratio positive → TP shrinks
                # For SELL: S0<0, if St rises (less negative) → ratio positive → TP shrinks
                # If St accelerates (BUY: St>S0, SELL: St<S0) → ratio negative → TP expands
                decay_ratio = (S0 - St) / S0
                Mt = max(min_tp_pct, 1.0 - (decay_factor * decay_ratio))
                # Update current_tp dynamically (can expand or shrink)
                current_tp = max(3, int(round(tp_pts * Mt)))
            # If |S0| ≈ 0, keep current_tp unchanged (no momentum reference)

        # BE structural: trigger at 1.0x ATR profit, move SL to entry+15
        if not be_active and mfe >= be_trigger_atr:
            be_active=True
            be_triggered_flag = True
            if signal=="BUY":
                be_sl_price=ep+15
            else:
                be_sl_price=ep-15

        # TRAILING STOP: after BE active, move SL to lock in x% of current profit
        # Only moves in favorable direction (never widens)
        if be_active and trailing_pct > 0:
            trail_distance = mfe * trailing_pct
            if signal == "BUY":
                new_trailing_sl = ep + trail_distance
                if trailing_sl_price is None or new_trailing_sl > trailing_sl_price:
                    trailing_sl_price = new_trailing_sl
                    trailing_triggered_flag = True
            else:
                new_trailing_sl = ep - trail_distance
                if trailing_sl_price is None or new_trailing_sl < trailing_sl_price:
                    trailing_sl_price = new_trailing_sl
                    trailing_triggered_flag = True

        # TP30: after hp_candles, check progress ratio
        if not tp30_active and candles_in_trade >= hp_candles:
            if signal=="BUY":
                profit_now=float(cj["close"])-ep
            else:
                profit_now=ep-float(cj["close"])
            prog_ratio = profit_now / tp_pts if tp_pts > 0 else 999
            if prog_ratio < hp_th:
                tp30_active = True
                tp30_triggered_flag = True
                current_tp = max(3, int(round(tp_pts * tp30_pct)))
                grace_count = 0
                hit_type = "TP30"

        # Slope Decay BE: if EMA5 slope dropped below threshold, move SL to BE
        if not slope_decayed and entry_slope is not None and abs(entry_slope) > 0:
            ema5_slope = float(cj.get("EMA5_SLOPE", 0) or 0)
            entry_sign = 1 if entry_slope > 0 else -1
            decay_threshold = abs(entry_slope) * slope_decay_pct
            if ema5_slope * entry_sign < decay_threshold:
                slope_decayed = True
                slope_decay_triggered_flag = True
                if signal == "BUY":
                    be_sl_price = ep + be_offset
                else:
                    be_sl_price = ep - be_offset
                # Continue without returning — trade continues with reduced TP

        # BE Progress: after TP30 + grace_candles, move SL to BE
        if tp30_active and not progressed:
            grace_count += 1
            if grace_count >= grace_candles:
                progressed = True
                progressed_flag = True
                if signal == "BUY":
                    be_sl_price = ep + be_offset
                else:
                    be_sl_price = ep - be_offset
                if be_sl_price is not None:
                    if signal == "BUY":
                        effective_sl = max(ep-sl_pts, be_sl_price)
                    else:
                        effective_sl = min(ep+sl_pts, be_sl_price)
                    # Force SL move on next tick check

        if len(bid_bar)>0 and len(ask_bar)>0:
            s_tick, e_tick = tick_idx[j]
            if signal=="BUY":
                hard_stop_price=ep-hard_stop
                if be_active and be_sl_price is not None:
                    effective_sl=max(ep-sl_pts,be_sl_price,hard_stop_price)
                elif progressed and be_sl_price is not None:
                    effective_sl=max(ep-sl_pts,be_sl_price,hard_stop_price)
                else:
                    effective_sl=max(ep-sl_pts,hard_stop_price)
                # Apply trailing stop (tightest SL wins)
                if trailing_sl_price is not None:
                    effective_sl = max(effective_sl, trailing_sl_price)
                # Tick-by-tick: primeiro tick que cruza TP ou SL
                # CORRECAO 2026-05-05: TP agora usa preco real do tick (bt - ep),
                # nao threshold fixo (current_tp). O tick pode cruzar ACIMA do TP,
                # capturando slippage favoravel. SL ja usava tick real (bt - ep).
                for t in range(s_tick, e_tick):
                    bt = bid_arr[t]
                    # FILTRO 2026-05-05: ignora ticks invalidos (<=0 ou fora do range da candle)
                    if bt <= 0 or bt < float(cj["low"]) - 1000 or bt > float(cj["high"]) + 1000:
                        continue
                    if bt >= ep + current_tp:
                        pnl = round(bt - ep); hit_type="TP"; return pnl, hit_type, mfe, mae, j, candles_in_trade, be_triggered_flag, tp30_triggered_flag, slope_decay_triggered_flag, progressed_flag, trailing_triggered_flag
                    if bt <= effective_sl:
                        pnl = max(round(bt - ep), -hard_stop); hit_type="SL"; return pnl, hit_type, mfe, mae, j, candles_in_trade, be_triggered_flag, tp30_triggered_flag, slope_decay_triggered_flag, progressed_flag, trailing_triggered_flag
                # FALLBACK 2026-05-05: se nenhum tick valido capturou o cruzamento,
                # usar high/low da candle como ground truth (~12% das candles).
                if float(cj["high"]) >= ep + current_tp:
                    pnl = round(float(cj["high"]) - ep); hit_type="TP"; return pnl, hit_type, mfe, mae, j, candles_in_trade, be_triggered_flag, tp30_triggered_flag, slope_decay_triggered_flag, progressed_flag, trailing_triggered_flag
                if float(cj["low"]) <= effective_sl:
                    pnl = max(round(float(cj["low"]) - ep), -hard_stop); hit_type="SL"; return pnl, hit_type, mfe, mae, j, candles_in_trade, be_triggered_flag, tp30_triggered_flag, slope_decay_triggered_flag, progressed_flag, trailing_triggered_flag
            else:
                hard_stop_price=ep+hard_stop
                if be_active and be_sl_price is not None:
                    effective_sl=min(ep+sl_pts,be_sl_price,hard_stop_price)
                elif progressed and be_sl_price is not None:
                    effective_sl=min(ep+sl_pts,be_sl_price,hard_stop_price)
                else:
                    effective_sl=min(ep+sl_pts,hard_stop_price)
                # Apply trailing stop (tightest SL wins)
                if trailing_sl_price is not None:
                    effective_sl = min(effective_sl, trailing_sl_price)
                # Tick-by-tick: primeiro tick que cruza TP ou SL
                # CORRECAO 2026-05-05: TP agora usa preco real do tick (ep - at),
                # nao threshold fixo (current_tp). SL ja usava tick real (ep - at).
                for t in range(s_tick, e_tick):
                    at = ask_arr[t]
                    # FILTRO 2026-05-05: ignora ticks invalidos (<=0 ou fora do range da candle)
                    if at <= 0 or at < float(cj["low"]) - 1000 or at > float(cj["high"]) + 1000:
                        continue
                    if at <= ep - current_tp:
                        pnl = round(ep - at); hit_type="TP"; return pnl, hit_type, mfe, mae, j, candles_in_trade, be_triggered_flag, tp30_triggered_flag, slope_decay_triggered_flag, progressed_flag, trailing_triggered_flag
                    if at >= effective_sl:
                        pnl = max(round(ep - at), -hard_stop); hit_type="SL"; return pnl, hit_type, mfe, mae, j, candles_in_trade, be_triggered_flag, tp30_triggered_flag, slope_decay_triggered_flag, progressed_flag, trailing_triggered_flag
                # FALLBACK 2026-05-05: se nenhum tick valido capturou o cruzamento,
                # usar high/low da candle como ground truth.
                if float(cj["low"]) <= ep - current_tp:
                    pnl = round(ep - float(cj["low"])); hit_type="TP"; return pnl, hit_type, mfe, mae, j, candles_in_trade, be_triggered_flag, tp30_triggered_flag, slope_decay_triggered_flag, progressed_flag, trailing_triggered_flag
                if float(cj["high"]) >= effective_sl:
                    pnl = max(round(ep - float(cj["high"])), -hard_stop); hit_type="SL"; return pnl, hit_type, mfe, mae, j, candles_in_trade, be_triggered_flag, tp30_triggered_flag, slope_decay_triggered_flag, progressed_flag, trailing_triggered_flag

    return pnl, hit_type, mfe, mae, exit_j, candles_in_trade, be_triggered_flag, tp30_triggered_flag, slope_decay_triggered_flag, progressed_flag, trailing_triggered_flag

# =====================================================================
# V119 Engine
# =====================================================================

def run_backtest_v119_v2(
    ticks_raw: pd.DataFrame, m5_ind: pd.DataFrame,
    strategy: Strategy, instrument: InstrumentConfig,
    entry_slippage_pts: int = 30, exit_slippage_pts: int = 30,
    gt_cfg=None,
) -> tuple[list[dict], pd.DataFrame, pd.DataFrame, dict]:
    """V119: V109 pipeline + GK ignition + Z-Score gate + improved BE/H-Progress."""
    from .engine_v99 import run_backtest_v993
    s=strategy; cfg=instrument
    m5=prepare_v119_features(m5_ind,s,gt_cfg=gt_cfg)
    records=m5.to_dict("records"); N=len(records)

    # ── Params ──────────────────────────────────────────
    sniper_adx=float(getattr(s,"sniper_adx_min",22) or 22)
    sniper_slope=float(getattr(s,"sniper_slope_min",18) or 18)
    hunter_adx=float(getattr(s,"hunter_adx_min",18) or 18)
    hunter_slope=float(getattr(s,"hunter_slope_min",15) or 15)
    hunter_tp=float(getattr(s,"hunter_tp_mult",1.8) or 1.8)
    hunter_sl=float(getattr(s,"hunter_sl_mult",1.0) or 1.0)
    scalper_tp=float(getattr(s,"scalper_tp_mult",1.0) or 1.0)
    scalper_sl_fb=float(getattr(s,"scalper_sl_mult_fallback",0.8) or 0.8)
    sniper_tp=float(getattr(s,"sniper_tp_mult",3.0) or 3.0)
    sniper_sl=float(getattr(s,"sniper_sl_mult",1.11) or 1.11)
    use_sd=bool(getattr(s,"use_slope_delta_gate",True))
    sd_min=float(getattr(s,"slope_delta_min",0) or 0)
    pa_eng=bool(getattr(s,"pa_enable_engulfing",True))
    pa_obo=bool(getattr(s,"pa_enable_outside_bar",False))
    pa_bo=bool(getattr(s,"pa_enable_breakout",True))
    be_struct=bool(getattr(s,"be_structural",True))
    be_off=int(getattr(s,"be_offset",25) or 25)
    hard_hs=int(getattr(s,"hard_stop_hunter_scalper",150) or 150)
    hard_sn=int(getattr(s,"hard_stop_sniper",400) or 400)
    hs_use_atr=bool(getattr(s,"hard_stop_use_atr_cap",True))
    hs_atr_h=float(getattr(s,"hard_stop_atr_mult_hunter",1.2) or 1.2)
    hs_atr_s=float(getattr(s,"hard_stop_atr_mult_sniper",1.5) or 1.5)
    cb_en=bool(getattr(s,"cb_enable",True))
    cb_dl=int(getattr(s,"cb_daily_loss_limit",-600) or -600)
    cb_cl=int(getattr(s,"cb_consecutive_loss_limit",4) or 4)
    cb_cm=int(getattr(s,"cb_cooldown_minutes",60) or 60)
    sniper_lot=float(getattr(s,"sniper_lot_mult",1.0) or 1.0)
    hunter_lot=float(getattr(s,"hunter_lot_mult",1.0) or 1.0)
    scalper_lot=float(getattr(s,"scalper_lot_mult",1.0) or 1.0)
    vol_en=bool(getattr(s,"vol_filter_enable",False))

    # V119 specific
    gk_th=float(getattr(s,"gk_regime_threshold",1.3) or 1.3)
    zscore_th=float(getattr(s,"zscore_exhaustion",2.2) or 2.2)
    hstag_candles=int(getattr(s,"h_stagnation_candles",6) or 6)
    hstag_profit_th=float(getattr(s,"h_stagnation_profit_th",40.0) or 40.0)
    be_trigger_pts=int(getattr(s,"be_trigger_points",250) or 250)

    # ── V993 for Sniper candidates ──────────────────────
    trades_v993,_,_,_=run_backtest_v993(ticks_raw,m5_ind,s,instrument,entry_slippage_pts,gt_cfg)

    # ── Build lookups ───────────────────────────────────
    m5_idx=m5.set_index("dt")
    adx_col=s.adx_col()
    adx_l=m5_idx[adx_col] if adx_col in m5_idx.columns else None
    slope_l=m5_idx["EMA5_SLOPE"] if "EMA5_SLOPE" in m5_idx.columns else None
    sd_l=m5_idx["SLOPE_DELTA"] if "SLOPE_DELTA" in m5_idx.columns else None
    gk_l=m5_idx["GK_RATIO"] if "GK_RATIO" in m5_idx.columns else None
    zs_l=m5_idx["ZSCORE_EMA"] if "ZSCORE_EMA" in m5_idx.columns else None

    bid_arr=ticks_raw["bid"].values.astype(float) if "bid" in ticks_raw.columns else ticks_raw["last"].values.astype(float)
    ask_arr=ticks_raw["ask"].values.astype(float) if "ask" in ticks_raw.columns else bid_arr
    tick_idx=_build_tick_index(ticks_raw,m5)

    # Vol filter
    vol_mask=None
    if vol_en:
        ranges=m5["high"].values.astype(float)-m5["low"].values.astype(float)
        vol_avg=pd.Series(ranges).rolling(10,min_periods=1).mean().values
        vol_mask=ranges<=(vol_avg*2.5)

    # ── Circuit breaker state ───────────────────────────
    daily_pnl={}; consec_loss=0; cb_cooldown=None

    trades=[]; cooldown_until=0; used_entries=set()
    sniper_excluded_gk=0; sniper_excluded_zs=0
    hstag_exits=0; be_exits=0

    for i in range(20,N-1):
        c=records[i]; hora_c=float(c["hora"]); entry_dt=c["dt"]
        if hora_c<cfg.hora_start or hora_c>=cfg.hora_limit: continue
        if i<=cooldown_until: continue
        if cb_en and cb_cooldown is not None and entry_dt<cb_cooldown: continue
        if cb_en:
            dk=entry_dt.date()
            if daily_pnl.get(dk,0)<=cb_dl: continue

        adx_val=float(c.get(adx_col,0) or 0) if adx_l is None else (float(adx_l.loc[entry_dt]) if entry_dt in adx_l.index else 0)
        slope_val=float(c.get("EMA5_SLOPE",0) or 0) if slope_l is None else (float(slope_l.loc[entry_dt]) if entry_dt in slope_l.index else 0)
        ema20_slope_val=float(c.get("EMA20_SLOPE",0) or 0) if slope_l is None else (float(slope_l.loc[entry_dt]) if entry_dt in slope_l.index else 0)
        abs_slope=abs(slope_val)
        atr_val=float(c.get("ATR",300) or 300)

        gk_val=float(gk_l.loc[entry_dt]) if gk_l is not None and entry_dt in gk_l.index else 1.0
        zs_val=float(zs_l.loc[entry_dt]) if zs_l is not None and entry_dt in zs_l.index else 0.0

        if vol_en and vol_mask is not None and not vol_mask[i]: continue

        # ── Mode determination ──────────────────────────
        if adx_val>=sniper_adx and abs_slope>=sniper_slope:
            mode="SNIPER"

            # V119 GK ignition gate
            if gk_val<gk_th:
                sniper_excluded_gk+=1
                continue

            # V119 Z-Score exhaustion gate
            signal_v993="BUY"
            for trv in trades_v993:
                if trv.get("entry_dt")==entry_dt:
                    signal_v993=trv.get("signal","BUY"); break
            if signal_v993=="BUY" and zs_val>zscore_th: sniper_excluded_zs+=1; continue
            if signal_v993=="SELL" and zs_val<-zscore_th: sniper_excluded_zs+=1; continue

        elif adx_val>=hunter_adx and abs_slope>=hunter_slope:
            mode="HUNTER"
        else:
            mode="SCALPER"

        # ── SNIPER: from V993 trades ────────────────────
        if mode=="SNIPER":
            tr_v993_found=None
            for trv in trades_v993:
                if trv.get("entry_dt")==entry_dt:
                    tr_v993_found=trv; break
            if tr_v993_found is None: continue
            if entry_dt in used_entries: continue

            signal=tr_v993_found.get("signal","BUY")

            # Slope Delta
            if use_sd and sd_l is not None and entry_dt in sd_l.index:
                sd_v=float(sd_l.loc[entry_dt])
                if signal=="BUY" and sd_v<sd_min: continue
                if signal=="SELL" and sd_v>-sd_min: continue

            tp_pts=int(round(atr_val*sniper_tp))
            sl_pts=int(round(atr_val*sniper_sl))
            if hs_use_atr: sl_pts=min(sl_pts,int(round(atr_val*hs_atr_s)))
            sl_pts=min(sl_pts,hard_sn)

            t_s,t_e=tick_idx[i]
            ep_raw=ask_arr[t_s] if t_s<t_e and ask_arr[t_s]>0 else float(c["open"]) if signal=="BUY" else bid_arr[t_s] if t_s<t_e and bid_arr[t_s]>0 else float(c["open"])
            ep=ep_raw+entry_slippage_pts if signal=="BUY" else ep_raw-entry_slippage_pts

            pnl,hit_type,mfe,mae,exit_j,candles_in_trade,be_triggered,tp30_triggered,slope_decay_triggered,progressed,trailing_triggered=_simulate_exit_v119(
                records,bid_arr,ask_arr,tick_idx,i,N,
                signal,ep,tp_pts,sl_pts,be_struct,be_off,mode,hard_sn,atr_val,
                hstag_candles,hstag_profit_th,be_trigger_pts,
                entry_slope=ema20_slope_val, slope_decay_pct=0.50, trailing_pct=0.0,
                decay_factor=0.50, min_tp_pct=0.20, use_dynamic_decay=True)

            pnl-=exit_slippage_pts
            tr=_make_trade(Position(signal=signal,mode="SNIPER",entry=ep,tp_pts=tp_pts,sl_pts=sl_pts,
                entry_hora=c["dt"].strftime("%H:%M"),entry_slope=ema20_slope_val,entry_dt=entry_dt,be_offset=be_off),
                entry_dt,entry_dt.strftime("%H:%M"),hit_type,pnl)
            tr["mfe"]=round(mfe); tr["mae"]=round(mae)
            tr["be_triggered"]=be_triggered; tr["tp30_triggered"]=tp30_triggered
            tr["slope_decay_triggered"]=slope_decay_triggered; tr["progressed"]=progressed
            tr["trailing_triggered"]=trailing_triggered; tr["candles_held"]=candles_in_trade
            if hit_type=="HSTAG": hstag_exits+=1
            if tr.get("be_reason"): be_exits+=1
            trades.append(tr); used_entries.add(entry_dt); cooldown_until=i+1
            if cb_en:
                dk=entry_dt.date(); daily_pnl[dk]=daily_pnl.get(dk,0)+pnl
                if pnl<0: consec_loss+=1
                else: consec_loss=0
                if consec_loss>=cb_cl: cb_cooldown=entry_dt+timedelta(minutes=cb_cm)

        # ── HUNTER / SCALPER: PA-based ──────────────────
        else:
            is_eng=bool(c.get("PA_ENGULFING",False))
            is_obo_=bool(c.get("PA_OUTSIDE_BAR",False))
            is_bb=bool(c.get("PA_BREAKOUT_BUY",False))
            is_bs=bool(c.get("PA_BREAKOUT_SELL",False))
            sig_dir=int(c.get("PA_SIGNAL_DIR",0) or 0)
            if sig_dir==0: continue
            if is_eng and not pa_eng: continue
            if is_obo_ and not pa_obo: continue
            if (is_bb or is_bs) and not pa_bo: continue
            if entry_dt in used_entries: continue

            signal="BUY" if sig_dir>0 else "SELL"

            if mode=="HUNTER":
                tp_pts=int(round(atr_val*hunter_tp))
                sl_pts=int(round(atr_val*hunter_sl))
                if hs_use_atr: sl_pts=min(sl_pts,int(round(atr_val*hs_atr_h)))
                sl_pts=min(sl_pts,hard_hs)
                # GK TP modulation for Hunter
                if gk_val>gk_th: tp_pts=int(round(atr_val*3.0))
            else:
                tp_pts=int(round(atr_val*scalper_tp))
                if signal=="BUY": sl_pts=int(round(float(c["open"])-float(c["low"])))
                else: sl_pts=int(round(float(c["high"])-float(c["open"])))
                sl_pts=max(20,int(round(atr_val*scalper_sl_fb))); sl_pts=min(sl_pts,hard_hs)

            t_s,t_e=tick_idx[i]
            ep_raw=ask_arr[t_s] if t_s<t_e and ask_arr[t_s]>0 else float(c["open"]) if signal=="BUY" else bid_arr[t_s] if t_s<t_e and bid_arr[t_s]>0 else float(c["open"])
            ep=ep_raw+entry_slippage_pts if signal=="BUY" else ep_raw-entry_slippage_pts

            pnl,hit_type,mfe,mae,exit_j,candles_in_trade,be_triggered,tp30_triggered,slope_decay_triggered,progressed,trailing_triggered=_simulate_exit_v119(
                records,bid_arr,ask_arr,tick_idx,i,N,
                signal,ep,tp_pts,sl_pts,be_struct,be_off,mode,
                hard_sn if mode=="SNIPER" else hard_hs, atr_val,
                hstag_candles,hstag_profit_th,be_trigger_pts,
                entry_slope=ema20_slope_val, slope_decay_pct=0.50, trailing_pct=0.0,
                decay_factor=0.50, min_tp_pct=0.20, use_dynamic_decay=True)

            pnl-=exit_slippage_pts
            tr=_make_trade(Position(signal=signal,mode=mode,entry=ep,tp_pts=tp_pts,sl_pts=sl_pts,
                entry_hora=c["dt"].strftime("%H:%M"),entry_slope=ema20_slope_val,entry_dt=entry_dt,be_offset=be_off),
                entry_dt,entry_dt.strftime("%H:%M"),hit_type,pnl)
            tr["mfe"]=round(mfe); tr["mae"]=round(mae)
            tr["be_triggered"]=be_triggered; tr["tp30_triggered"]=tp30_triggered
            tr["slope_decay_triggered"]=slope_decay_triggered; tr["progressed"]=progressed
            tr["trailing_triggered"]=trailing_triggered; tr["candles_held"]=candles_in_trade
            tr["mfe"]=round(mfe); tr["mae"]=round(mae)
            if hit_type=="HSTAG": hstag_exits+=1
            if tr.get("be_reason"): be_exits+=1
            trades.append(tr); used_entries.add(entry_dt); cooldown_until=i+1
            if cb_en:
                dk=entry_dt.date(); daily_pnl[dk]=daily_pnl.get(dk,0)+pnl
                if pnl<0: consec_loss+=1
                else: consec_loss=0
                if consec_loss>=cb_cl: cb_cooldown=entry_dt+timedelta(minutes=cb_cm)

    metrics={"engine":"v119_v2","sniper_gk_blocked":sniper_excluded_gk,
             "sniper_zs_blocked":sniper_excluded_zs,"hstag_exits":hstag_exits,
             "be_exits":be_exits}
    return trades, m5, pd.DataFrame(), metrics
