# Strategy Reference

Complete parameter reference for all 41 strategies registered in `BACKTRADER_STRATEGY_REGISTRY`.

---

## Table of Contents

- [Mean Reversion Strategies](#mean-reversion-strategies)
- [Trend Following Strategies](#trend-following-strategies)
- [Futures Strategies](#futures-strategies)
- [Multi-Factor Strategies](#multi-factor-strategies)
- [Intraday Strategies](#intraday-strategies)
- [Special Strategies](#special-strategies)
- [Enhanced Strategies (V3.0.0)](#enhanced-strategies-v300)
- [ML Strategies](#ml-strategies)
- [Strategy Aliases](#strategy-aliases)

---

## Mean Reversion Strategies

### ema (EMA Crossover)

Simple EMA-based trend signal.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| period | int | 20 | [5, 10, 15, 20, 30, 40, 60, 80, 100, 120] |

**Aliases**: `ema_crossover`

---

### macd (MACD Signal Crossover)

Classic MACD line/signal crossover.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| fast | int | 12 | [4, 6, 8, 10, 12, 14, 16, 18, 20] |
| slow | int | 26 | [10, 15, 20, 26, 30, 35, 40] |
| signal | int | 9 | [9] |

**Aliases**: `macd_basic`

---

### macd_e (MACD Enhanced)

MACD with EMA trend filter, cooldown period, and stop-loss/take-profit.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| fast | int | 12 | [8, 10, 12, 14] |
| slow | int | 26 | [20, 26, 30] |
| signal | int | 9 | [9] |
| ema_trend_period | int | 200 | [100, 150, 200] |
| trend_filter | bool | True | [True] |
| cooldown | int | 5 | [3, 5, 8] |
| min_hold | int | 3 | [3, 5] |
| stop_loss_pct | float | 0.05 | [0.03, 0.05, 0.08] |
| take_profit_pct | float | 0.10 | [0.08, 0.10, 0.15] |

**Aliases**: `macd_enhanced`

---

### macd_r (MACD Regime + Pullback)

MACD with regime detection, pullback entry, ATR-based stops.

| Parameter | Type | Default |
|-----------|------|---------|
| fast | int | 12 |
| slow | int | 26 |
| signal | int | 9 |
| ema_trend_period | int | 200 |
| roc_period | int | 20 |
| trend_filter | bool | True |
| trend_logic | str | "ema" |
| ema_entry_period | int | 10 |
| pullback_k | float | 0.5 |
| max_lag | int | 5 |
| atr_period | int | 14 |
| atr_sl_mult | float | 2.0 |
| atr_trail_mult | float | 3.0 |
| min_hold | int | 3 |
| cooldown | int | 5 |
| tp1_R | float | 2.0 |
| tp1_frac | float | 0.5 |
| tp2_R | float | 4.0 |

**Aliases**: `macd_regime`

---

### macd_zero (MACD Zero Line Crossover)

Enters on MACD crossing above/below zero line.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| fast | int | 12 | [8, 10, 12, 16] |
| slow | int | 26 | [20, 26, 30] |
| signal | int | 9 | [9] |

**Aliases**: `macd_zero_cross`

---

### macd_hist (MACD Histogram Momentum)

Trades based on MACD histogram direction and threshold.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| fast | int | 12 | [8, 10, 12, 16] |
| slow | int | 26 | [20, 26, 30] |
| signal | int | 9 | [9] |
| threshold | float | 0.0 | [0.0, 0.5, 1.0] |

**Aliases**: `macd_histogram`

---

### bollinger (Bollinger Bands Mean Reversion)

Enters on price touching/piercing lower band, exits at mid or upper band.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| period | int | 20 | [10, 15, 20, 30, 40] |
| devfactor | float | 2.0 | [1.5, 2.0, 2.5, 3.0] |
| entry_mode | str | "pierce" | ["pierce", "close_below"] |
| below_pct | float | 0.0 | [0.0, 0.005, 0.01] |
| exit_mode | str | "mid" | ["mid", "upper"] |

**Aliases**: `bollinger_basic`

---

### boll_e (Bollinger Enhanced)

Bollinger with ATR stop-loss, multi-target profit taking, and pullback exit.

| Parameter | Type | Default |
|-----------|------|---------|
| period | int | 20 |
| devfactor | float | 2.0 |
| atr_period | int | 14 |
| atr_mult_sl | float | 2.0 |
| tp1_pct | float | 0.03 |
| tp1_frac | float | 0.5 |
| tp2_pct | float | 0.06 |
| tp2_frac | float | 0.3 |
| trail_drop_pct | float | 0.02 |
| min_hold | int | 3 |
| cooldown | int | 3 |
| warmup_bars | int | 50 |
| rebound_lookback | int | 3 |
| max_hold | int | 30 |
| trend_filter | bool | True |

**Aliases**: `bollinger_enhanced`

---

### rsi (RSI Threshold)

Buys on RSI oversold, sells on RSI overbought.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| period | int | 14 | [7, 10, 14, 21, 28] |
| upper | float | 70.0 | [65, 70, 75, 80] |
| lower | float | 30.0 | [20, 25, 30, 35] |

**Aliases**: `rsi_basic`

---

### rsi_ma_filter (RSI + MA Trend Filter)

RSI oversold signal filtered by price above long-term MA.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| rsi_period | int | 14 | [7, 14, 21] |
| oversold | float | 30.0 | [20, 25, 30] |
| ma_period | int | 200 | [100, 150, 200] |

**Aliases**: `rsi_ma`

---

### rsi_divergence (RSI Divergence)

Detects bullish/bearish divergence between price and RSI.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| period | int | 14 | [7, 14, 21] |
| lookback | int | 5 | [3, 5, 8, 10] |

**Aliases**: `rsi_div`

---

### keltner (Keltner Channel Mean Reversion)

Enters on price touching lower Keltner channel.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| ema_period | int | 20 | [10, 15, 20, 30] |
| atr_period | int | 14 | [10, 14, 20] |
| kc_mult | float | 2.0 | [1.5, 2.0, 2.5] |
| entry_mode | str | "pierce" | ["pierce", "close_below"] |
| below_pct | float | 0.0 | [0.0, 0.005] |
| exit_mode | str | "mid" | ["mid", "upper"] |

**Aliases**: `keltner_basic`

---

### zscore (Z-Score Mean Reversion)

Enters on extreme negative Z-score, exits when Z-score normalizes.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| period | int | 20 | [10, 15, 20, 30, 40] |
| z_entry | float | -2.0 | [-3.0, -2.5, -2.0, -1.5] |
| z_exit | float | -0.5 | [-1.0, -0.5, 0.0] |

**Aliases**: `zscore_basic`

---

## Trend Following Strategies

### donchian (Donchian Channel Breakout)

Classic Donchian channel breakout system.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| upper | int | 20 | [10, 15, 20, 30, 40, 55] |
| lower | int | 10 | [5, 10, 15, 20] |

**Aliases**: `donchian_basic`

---

### triple_ma (Triple Moving Average)

Three-MA system: fast crosses mid for signal, slow for trend confirmation.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| fast | int | 5 | [3, 5, 8, 10] |
| mid | int | 20 | [15, 20, 30] |
| slow | int | 60 | [40, 60, 80, 100] |

**Aliases**: `triple_ma_basic`

---

### adx_trend (ADX Trend Filter)

Uses ADX to confirm strong trend before entering.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| adx_period | int | 14 | [7, 10, 14, 20] |
| adx_th | float | 25.0 | [20, 25, 30, 35] |

**Aliases**: `adx_basic`

---

### sma_cross (SMA Crossover)

Simple dual-SMA crossover system.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| fast_period | int | 10 | [5, 8, 10, 15, 20] |
| slow_period | int | 30 | [20, 30, 40, 50, 60] |

**Aliases**: `sma_basic`

---

### kama (Kaufman Adaptive MA)

Kaufman Adaptive Moving Average adjusts smoothing to market noise.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| period | int | 10 | [5, 10, 15, 20] |
| fast_ema | int | 2 | [2] |
| slow_ema | int | 30 | [20, 30, 40] |

**Aliases**: `kama_basic`

---

## Futures Strategies

### futures_ma_cross (Futures EMA Crossover)

Dual EMA crossover for futures with long/short support.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| short_period | int | 9 | [5, 7, 9, 12] |
| long_period | int | 34 | [21, 26, 34, 55] |

**Aliases**: `futures_ma`

---

### futures_grid (Futures Grid Trading)

Grid trading for futures with layered entries.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| grid_pct | float | 0.004 | [0.002, 0.003, 0.004, 0.006] |
| layers | int | 6 | [4, 6, 8] |
| max_pos | int | 3 | [2, 3, 4] |

**Aliases**: `futures_grid_basic`

---

### futures_market_making (Futures Market Making)

Market making with inventory management.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| band_pct | float | 0.003 | [0.002, 0.003, 0.005] |
| inventory_limit | int | 2 | [1, 2, 3] |
| ma_period | int | 50 | [20, 50, 100] |

**Aliases**: `futures_mm`

---

### turtle_futures (Turtle Trading System)

Classic turtle breakout system for futures.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| entry_period | int | 20 | [10, 15, 20, 30, 55] |
| exit_period | int | 10 | [5, 10, 15, 20] |

**Aliases**: `turtle`

---

## Multi-Factor Strategies

### multifactor_selection (Multi-Factor Selection)

Composite factor scoring for stock selection.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| buy_threshold | float | 0.0 | [-0.5, 0.0, 0.5, 1.0] |
| score_window | int | 60 | [20, 40, 60, 120] |

**Aliases**: `multifactor_basic`

---

### index_enhancement (Index Enhancement)

Index-tracking with momentum tilt.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| ma_period | int | 100 | [60, 80, 100, 120] |
| mom_period | int | 20 | [10, 20, 30] |

**Aliases**: `index_enhance`

---

### industry_rotation (Industry Rotation)

Sector rotation based on momentum.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| ma_period | int | 60 | [40, 60, 80] |
| momentum_period | int | 20 | [10, 20, 30] |

**Aliases**: `industry_rotate`

---

## Intraday Strategies

### auction_open (Auction Open Selection)

Selects stocks based on auction gap and volume ratio.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| gap_min | float | 2.0 | [1.0, 1.5, 2.0, 3.0] |
| vol_ratio_min | float | 1.5 | [1.0, 1.5, 2.0, 2.5] |

**Aliases**: `auction`

---

### intraday_reversion (Intraday Mean Reversion)

Intraday mean reversion on percentage threshold.

| Parameter | Type | Default | Grid Search |
|-----------|------|---------|-------------|
| threshold_pct | float | 0.8 | [0.5, 0.8, 1.0, 1.5] |
| allow_short | bool | False | [False] |

**Aliases**: `intraday_basic`

---

## Enhanced Strategies (V3.0.0)

### kama_opt (KAMA Optimized)

KAMA with SMA200 trend filter and ATR trailing stop.

| Parameter | Type | Default |
|-----------|------|---------|
| period | int | 10 |
| fast_ema | int | 2 |
| slow_ema | int | 30 |
| trend_ma_period | int | 200 |
| atr_period | int | 14 |
| atr_mult | float | 2.5 |

**Aliases**: `kama_enhanced`

---

### futures_grid_atr (ATR Dynamic Grid)

Futures grid with ATR-adaptive spacing and account-level stop loss.

| Parameter | Type | Default |
|-----------|------|---------|
| atr_period | int | 14 |
| atr_mult | float | 0.5 |
| layers | int | 6 |
| max_pos | int | 3 |
| account_stop_pct | float | 0.05 |

**Aliases**: `futures_grid_enhanced`

---

### intraday_opt (Intraday Optimized)

Intraday reversion with time filter and ATR-adaptive threshold.

| Parameter | Type | Default |
|-----------|------|---------|
| atr_period | int | 14 |
| atr_mult | float | 1.5 |
| allow_short | bool | False |
| start_hour | int | 10 |
| end_hour | int | 14 |

**Aliases**: `intraday_enhanced`

---

### bollinger_rsi (Bollinger + RSI Combo)

Bollinger band signal confirmed by RSI oversold/overbought.

| Parameter | Type | Default |
|-----------|------|---------|
| bb_period | int | 20 |
| bb_dev | float | 2.0 |
| rsi_period | int | 14 |
| rsi_lower | float | 30.0 |
| rsi_upper | float | 70.0 |

**Aliases**: `bollinger_rsi_combo`

---

### donchian_atr (Donchian + ATR Confirmation)

Donchian breakout with ATR volatility confirmation.

| Parameter | Type | Default |
|-----------|------|---------|
| entry_period | int | 20 |
| exit_period | int | 10 |
| atr_period | int | 14 |
| vol_threshold | float | 1.0 |

**Aliases**: `donchian_enhanced`

---

### trend_pullback_enhanced (Trend Pullback)

Institutional-grade trend following with pullback entry, volatility-based position sizing, and chandelier exit.

| Parameter | Type | Default |
|-----------|------|---------|
| trend_period | int | 50 |
| pullback_period | int | 10 |
| atr_period | int | 14 |
| risk_pct | float | 0.01 |
| atr_sl_mult | float | 3.0 |
| chandelier_mult | float | 3.0 |

**Aliases**: `trend_pullback`

---

### zscore_enhanced (Z-Score + RSI Filter)

Z-Score mean reversion filtered by RSI and ATR-based stop.

| Parameter | Type | Default |
|-----------|------|---------|
| period | int | 20 |
| z_entry | float | -2.0 |
| z_exit | float | -0.5 |
| rsi_period | int | 14 |
| rsi_filter | float | 40.0 |
| atr_period | int | 14 |
| atr_sl_mult | float | 2.0 |

---

### rsi_trend (RSI Pullback in Uptrend)

RSI pullback strategy with hook pattern detection in confirmed uptrend.

| Parameter | Type | Default |
|-----------|------|---------|
| rsi_period | int | 14 |
| oversold | float | 30.0 |
| ma_period | int | 200 |
| hook_bars | int | 3 |

**Aliases**: `rsi_trend_filter`

---

### keltner_adaptive (Adaptive Keltner Breakout)

Keltner breakout with volatility-based position sizing and chandelier exit.

| Parameter | Type | Default |
|-----------|------|---------|
| ema_period | int | 20 |
| atr_period | int | 14 |
| kc_mult | float | 2.0 |
| risk_pct | float | 0.01 |
| chandelier_mult | float | 3.0 |

**Aliases**: `keltner_enhanced`

---

### triple_ma_adx (Triple MA + ADX Filter)

Triple EMA crossover with ADX trend strength confirmation.

| Parameter | Type | Default |
|-----------|------|---------|
| fast | int | 5 |
| mid | int | 20 |
| slow | int | 60 |
| adx_period | int | 14 |
| adx_threshold | float | 25.0 |

**Aliases**: `triple_ma_enhanced`

---

### macd_impulse (MACD Zero-Line Bias)

MACD zero-line bias with momentum filter for trend confirmation.

| Parameter | Type | Default |
|-----------|------|---------|
| fast | int | 12 |
| slow | int | 26 |
| signal | int | 9 |
| momentum_period | int | 10 |
| momentum_threshold | float | 0.0 |

---

### sma_trend_following (SMA Trend with Slope)

SMA crossover with slope confirmation for trend quality.

| Parameter | Type | Default |
|-----------|------|---------|
| fast_period | int | 10 |
| slow_period | int | 30 |
| slope_period | int | 5 |
| min_slope | float | 0.0 |

**Aliases**: `sma_enhanced`

---

### multifactor_robust (Robust Multi-Factor)

Trend-filtered multi-factor composite with regime filter.

| Parameter | Type | Default |
|-----------|------|---------|
| score_window | int | 60 |
| buy_threshold | float | 0.0 |
| ma_period | int | 200 |
| regime_filter | bool | True |

**Aliases**: `multifactor_enhanced`

---

## ML Strategies

### qlib_registry (Qlib Registered Model)

Runs signals from a model registered in the Qlib model registry.

| Parameter | Type | Default |
|-----------|------|---------|
| model_id | str | "" |
| model_name | str | "" |
| provider_uri | str | "./qlib_data" |
| region | str | "cn" |
| threshold | float | 0.0 |
| allow_short | bool | False |
| position_pct | float | 0.1 |
| lot_size | int | 100 |
| min_hold_bars | int | 1 |
| cooldown_bars | int | 0 |

---

## Strategy Aliases

All strategies support canonical aliases for readability:

| Alias | Resolves To |
|-------|-------------|
| ema_crossover | ema |
| macd_basic | macd |
| macd_enhanced | macd_e |
| macd_regime | macd_r |
| macd_zero_cross | macd_zero |
| macd_histogram | macd_hist |
| bollinger_basic | bollinger |
| bollinger_enhanced | boll_e |
| bollinger_rsi_combo | bollinger_rsi |
| rsi_basic | rsi |
| rsi_ma | rsi_ma_filter |
| rsi_div | rsi_divergence |
| rsi_trend_filter | rsi_trend |
| keltner_basic | keltner |
| keltner_enhanced | keltner_adaptive |
| zscore_basic | zscore |
| donchian_basic | donchian |
| donchian_enhanced | donchian_atr |
| sma_basic | sma_cross |
| sma_enhanced | sma_trend_following |
| triple_ma_basic | triple_ma |
| triple_ma_enhanced | triple_ma_adx |
| adx_basic | adx_trend |
| kama_basic | kama |
| kama_enhanced | kama_opt |
| futures_ma | futures_ma_cross |
| futures_grid_basic | futures_grid |
| futures_grid_enhanced | futures_grid_atr |
| futures_mm | futures_market_making |
| turtle | turtle_futures |
| intraday_basic | intraday_reversion |
| intraday_enhanced | intraday_opt |
| multifactor_basic | multifactor_selection |
| multifactor_enhanced | multifactor_robust |
| index_enhance | index_enhancement |
| industry_rotate | industry_rotation |
| auction | auction_open |
| trend_pullback | trend_pullback_enhanced |

Use `list-strategies` CLI command to see all available strategies:

```bash
python unified_backtest_framework.py list-strategies
```
