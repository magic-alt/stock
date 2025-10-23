# Changelog

All notable changes to this project will be documented in this file.

## [V2.5.1] - 2025-01-XX - Bug Fixes & Stability Improvements

### 🐛 Bug Fixes

#### Critical Fixes:
1. **StopIteration Error Fix**
   - **Issue**: Empty `data_map` caused `StopIteration` exception in `strategy_modules.py`
   - **Fix**: Added comprehensive empty data validation
     - `add_data()` method now checks for empty data_map
     - `_rerun_top_n()` validates data before processing
     - `_run_single()` returns flat NAV instead of crashing
   - **Impact**: Prevents crashes during auto pipeline execution

2. **AKShare Symbol Format Error**
   - **Issue**: AKShare API requires pure numeric symbols (e.g., `'600519'`), but code passed full format (e.g., `'600519.SH'`)
   - **Fix**: Strip exchange suffix before API calls
   ```python
   ak_symbol = symbol.replace(".SH", "").replace(".SZ", "")
   df = ak.stock_zh_a_hist(symbol=ak_symbol, ...)
   ```
   - **Impact**: All AKShare data loading now works correctly

3. **Timezone Mismatch Error**
   - **Issue**: `TypeError: Cannot join tz-naive with tz-aware DatetimeIndex`
   - **Fix**: Force all DatetimeIndex to timezone-naive
     - Updated `_standardize_stock_frame()`
     - Updated `_standardize_index_frame()`
     - Updated `_standardize_yf()`
     - Added timezone cleanup in benchmark comparison
   - **Impact**: Eliminates pandas timezone conflicts

### 🔧 Improvements

- **Enhanced Error Messages**: Added diagnostic logging throughout data loading pipeline
- **Better Empty Data Handling**: Graceful fallback to flat NAV when data unavailable
- **Improved Cache Validation**: Detect and handle corrupted cache files

### 📝 Files Modified

- `src/data_sources/providers.py`
  - Fixed AKShare symbol format conversion
  - Added timezone normalization to all standardization functions
  - Enhanced error logging with traceback

- `src/backtest/engine.py`
  - Added empty data_map validation in `_rerun_top_n()`
  - Added timezone cleanup in benchmark comparison
  - Enhanced diagnostic output for data loading

- `src/backtest/strategy_modules.py`
  - Added empty data_map check in `add_data()` method
  - Improved error messages with strategy context

### 🧪 Testing

- ✅ Tested with 10 symbols (600519.SH, 000333.SZ, etc.)
- ✅ Tested with 8 strategies (adx_trend, macd, triple_ma, etc.)
- ✅ Tested with 4 parallel workers
- ✅ Confirmed 3-year date range (2022-2025) works correctly
- ✅ All auto pipeline features functional

### 📊 Test Results

```bash
# Successful execution:
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ 600036.SH 601318.SH 600276.SH \
            600104.SH 600031.SH 000651.SZ 000725.SZ 600887.SH \
  --start 2022-01-01 --end 2025-01-01 \
  --benchmark 000300.SS \
  --strategies adx_trend macd triple_ma donchian zscore keltner bollinger rsi \
  --hot_only --min_trades 1 --top_n 6 --workers 4 \
  --use_benchmark_regime --regime_scope trend \
  --out_dir reports_bulk_10

Output:
- 📊 Loaded data for 10 symbols successfully
- ⚡ Evaluated 124 parameter configurations
- 🏆 Generated Pareto frontier analysis
- 📈 Exported heatmaps and NAV curves
- ⏱️ Completed in 26.4 seconds
```

---

## [V2.5.0] - 2024 - Complete Modularization (Phase 1 + Phase 2)

### 🎉 Phase 2 Completed - Advanced Features Modularization

#### New Modules Created:
4. **`src/backtest/analysis.py`** (184 lines) - NEW
   - `pareto_front()` - Multi-objective optimization filter (Sharpe, return, drawdown)
   - `save_heatmap()` - Strategy-specific visualization for 10 strategy types
   - Support for EMA, MACD, Bollinger, RSI, ZScore, Donchian, TripleMA, ADX, RiskParity, TurningPoint
   - Zero-trade ratio reporting

5. **`src/backtest/plotting.py`** (149 lines) - NEW
   - `plot_backtest_with_indicators()` - Enhanced backtest visualization
   - `CNPlotScheme` - Chinese market color scheme (red-up/green-down)
   - 7 technical indicators: EMA, WMA, Stochastic, MACD, ATR, RSI, SMA
   - Candlestick and line chart styles
   - High-resolution output support

#### Enhanced Modules:
- **`src/backtest/engine.py`** (+313 lines → 819 lines total)
  - `auto_pipeline()` - Multi-strategy optimization workflow
  - `_hot_grid()` - Strategy-specific optimized parameter ranges
  - `_rerun_top_n()` - Pareto frontier replay with NAV curves
  - `_print_metrics_legend()`, `_print_top_configs()`, `_print_best_per_strategy()`
  - Benchmark regime filtering (EMA200)
  - Flexible strategy scope (trend/all/none)

- **`src/backtest/strategy_modules.py`** (+120 lines → 700 lines total)
  - `RiskParityBT` strategy - Multi-asset risk parity with inverse-volatility weighting
  - `_coerce_rp()` - Parameter validation for risk parity
  - `RISK_PARITY_MODULE` - Complete risk parity configuration
  - Momentum and regime filters
  - Benchmark gating for risk-on/risk-off

- **`src/data_sources/providers.py`** (+3 lines → 497 lines total)
  - Added `PROVIDER_NAMES` export for CLI integration

#### Simplified Main File:
- **`unified_backtest_framework.py`** (2138 → 214 lines, **90% reduction!**)
  - Removed all implementation code
  - Kept only CLI interface (parse_args, main)
  - Clean imports from modularized components
  - Full backward compatibility maintained

### ✨ New Features

#### Auto Pipeline Workflow
```bash
python unified_backtest_framework.py auto \
  --symbols 600519.SH --start 2023-01-01 --end 2023-12-31 \
  --strategies ema macd --top_n 5 --hot_only --use_benchmark_regime
```
- Multi-strategy parallel optimization
- Pareto frontier analysis
- Strategy-specific heatmaps
- Top-N configuration replay
- NAV curve visualization

#### Advanced Plotting
- Technical indicators overlay
- Chinese color scheme
- Multiple chart styles
- Export to PNG

#### Pareto Frontier Analysis
- Multi-objective optimization (Sharpe/Return/Drawdown)
- Automatic identification of Pareto-optimal configurations
- Visual heatmaps for parameter exploration

#### Risk Parity Strategy
- Multi-asset portfolio optimization
- Inverse-volatility weighting
- Periodic rebalancing (21 days default)
- Momentum filter (60-day lookback)
- Regime filter (EMA200)
- Benchmark gating (risk-on/risk-off)

### 🧪 Testing
- ✅ All 5 existing tests passing
- ✅ Manual CLI testing successful
- ✅ Backward compatibility verified
- ✅ No breaking changes

### 📝 Documentation
- Created `docs/PHASE2_COMPLETION_REPORT.md` (detailed Phase 2 report)
- Updated architecture diagrams
- Documented new APIs and workflows
- Added usage examples

### 🚀 Performance
- 90% code reduction in main file
- Improved maintainability
- Better test coverage
- Faster development cycle

---

## [V2.5.0-alpha] - 2024 - Modularization Phase 1

### 🎯 Major Refactoring - Modular Architecture
Successfully modularized the monolithic `unified_backtest_framework.py` (2138 lines) into clean, maintainable modules under `src/` structure.

### ✨ Added

#### New Modules Created:
1. **`src/data_sources/providers.py`** (450 lines)
   - Unified data provider module with factory pattern
   - `DataProvider` abstract base class
   - `AkshareProvider` for Chinese markets (default)
   - `YFinanceProvider` for global markets
   - `TuShareProvider` for Chinese markets with token
   - Data normalization helpers
   - NAV calculation utilities

2. **`src/backtest/strategy_modules.py`** (580 lines)
   - `StrategyModule` dataclass for strategy metadata
   - `GenericPandasData` Backtrader feed
   - `IntentLogger` analyzer for trade tracking
   - `TurningPointBT` strategy implementation
   - Signal computation utilities (`rolling_vwap`, `compute_signal_frame`)
   - Order decision logic
   - Strategy registry integration with backtrader strategies

3. **`src/backtest/engine.py`** (506 lines)
   - `BacktestEngine` class - Core execution engine
   - Data loading and caching
   - Strategy execution with comprehensive metrics
   - Grid search with multiprocessing support
   - Worker process management
   - Metrics calculation (Sharpe, MDD, win rate, profit factor, etc.)

### 📝 Documentation
- Created `docs/MODULARIZATION_PHASE1_COMPLETED.md` with detailed migration report
- Documented new import structure and architecture
- Added testing strategy outline

### 🔧 Improvements
- **Maintainability**: Each module has single responsibility
- **Testability**: Isolated components easier to test
- **Reusability**: Modules can be imported independently
- **Scalability**: Easy to add new providers/strategies
- **Performance**: Lazy imports, optimized caching, process-level data sharing
- **Type Safety**: Comprehensive type hints throughout

### 📊 Metrics
- Lines modularized: 1,536 / 2,138 (72%)
- New files: 3
- Import errors: 0 ✅
- Compile errors: 0 ✅

### 🎯 Next Steps (Phase 2)
- [ ] Extract auto pipeline functionality
- [ ] Complete RiskParity strategy
- [ ] Create `src/backtest/plotting.py`
- [ ] Create `src/backtest/analysis.py`
- [ ] Simplify main file to use new modules
- [ ] Add unit and integration tests

---

## [V2.4.2] - 2024 - Unified Framework Plotting

### ✨ Added
- Added plotting functionality to `unified_backtest_framework.py`
- `--plot` CLI flag for chart generation
- `enable_plot` parameter for programmatic use
- `plot_backtest_with_indicators()` helper function
- 7 technical indicators in charts (EMA, WMA, StochasticSlow, MACD, ATR, RSI, SMA)

### 📝 Documentation
- `docs/UNIFIED_BACKTEST_PLOTTING_GUIDE.md` - Comprehensive guide
- `docs/UNIFIED_PLOT_QUICKSTART.md` - Quick start guide
- Updated README with plotting examples

### 🧪 Testing
- Created `test_unified_plot.py` test script
- Verified plotting with multiple strategies (EMA, Bollinger, Turning Point)
- Generated sample charts in `test_plot_output/`

---

## [V2.4.0] - 2024 - Backtrader Adapter Plotting Enhancement

### ✨ Added
- Enhanced `backtrader_adapter.py` plot() method
- Added 7 technical indicators: EMA(25), WMA(25), StochasticSlow, MACD, ATR, RSI, SMA(10)
- Chinese color scheme (red-up/green-down) via CNPlotScheme
- Customizable figure size and output file support

### 📝 Documentation  
- Detailed docstrings with parameter descriptions
- Reference to Backtrader official docs

### 🧪 Testing
- Created `quick_test_plot.py` for rapid testing
- Verified plotting with sample stock data (600519.SH, 000001.SZ)

---

## [V2.3.0] - Previous Version
- Strategy modularization completed
- Multiple strategy implementations
- Grid search optimization
- Benchmark comparison

---

## Format
- 🎯 Major Refactoring
- ✨ Added
- 🔧 Improvements  
- 🐛 Fixed
- 📝 Documentation
- 🧪 Testing
- 📊 Metrics
