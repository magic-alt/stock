Run pytest tests/ -v --cov=src --cov-report=xml --cov-report=term-missing
============================= test session starts ==============================
platform linux -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0 -- /opt/hostedtoolcache/Python/3.11.14/x64/bin/python
cachedir: .pytest_cache
rootdir: /home/runner/work/stock/stock
configfile: pytest.ini
plugins: cov-7.0.0, xdist-3.8.0
collecting ... collected 231 items

tests/test_analysis.py::TestParetoFront::test_pareto_front_basic PASSED  [  0%]
tests/test_analysis.py::TestParetoFront::test_pareto_front_empty PASSED  [  0%]
tests/test_analysis.py::TestParetoFront::test_pareto_front_single_best PASSED [  1%]
tests/test_analysis.py::TestParetoFront::test_pareto_front_with_nan PASSED [  1%]
tests/test_analysis.py::TestSaveHeatmap::test_save_heatmap_ema PASSED    [  2%]
tests/test_analysis.py::TestSaveHeatmap::test_save_heatmap_macd PASSED   [  2%]
tests/test_analysis.py::TestAnalysisHelpers::test_calculate_metrics PASSED [  3%]
tests/test_analysis.py::TestAnalysisHelpers::test_max_drawdown_calculation PASSED [  3%]
tests/test_analysis.py::TestAnalysisIntegration::test_full_analysis_pipeline PASSED [  3%]
tests/test_backtest.py::TestBacktestEngine::test_engine_creation PASSED  [  4%]
tests/test_backtest.py::TestBacktestEngine::test_engine_data_loading PASSED [  4%]
tests/test_backtest.py::TestBacktestEngine::test_engine_run_backtest PASSED [  5%]
tests/test_backtest.py::TestBacktestEngine::test_engine_multiple_symbols PASSED [  5%]
tests/test_backtest.py::TestAnalysis::test_pareto_front PASSED           [  6%]
tests/test_backtest.py::TestAnalysis::test_pareto_front_empty PASSED     [  6%]
tests/test_backtest.py::TestAnalysis::test_save_heatmap PASSED           [  6%]
tests/test_backtest.py::TestPlotting::test_generate_backtest_report_exists PASSED [  7%]
tests/test_backtest.py::TestPlotting::test_plot_backtest_with_indicators_exists PASSED [  7%]
tests/test_backtest.py::TestStrategyModules::test_strategy_registry PASSED [  8%]
tests/test_backtest.py::TestStrategyModules::test_strategy_registry_contains_modules PASSED [  8%]
tests/test_backtest.py::TestBacktestIntegration::test_full_backtest_pipeline SKIPPED keyword argument 'strategy_class') [  9%]
tests/test_backtest_gui_builders.py::test_run_command_builder_includes_fee_and_benchmark_source PASSED [  9%]
tests/test_backtest_gui_builders.py::test_grid_command_builder_rejects_bad_json PASSED [  9%]
tests/test_backtest_gui_builders.py::test_auto_command_builder_flags_scope_and_benchmark_source PASSED [ 10%]
tests/test_backtest_gui_builders.py::test_combo_command_builder_handles_allow_short_and_output PASSED [ 10%]
tests/test_calendar_quality.py::test_trading_calendar_sessions_weekdays PASSED [ 11%]
tests/test_calendar_quality.py::test_align_frame_fill_suspensions PASSED [ 11%]
tests/test_calendar_quality.py::test_quality_report_missing_sessions PASSED [ 12%]
tests/test_combo_optimizer.py::test_optimize_prefers_higher_sharpe PASSED [ 12%]
tests/test_combo_optimizer.py::test_optimize_handles_other_objectives PASSED [ 12%]
tests/test_combo_optimizer.py::test_load_nav_series_recovers_nav_column PASSED [ 13%]
tests/test_combo_optimizer.py::test_load_nav_series_missing_column PASSED [ 13%]
tests/test_combo_optimizer.py::test_load_nav_series_fallback_index PASSED [ 14%]
tests/test_combo_optimizer.py::test_optimize_guardrails_and_invalid_objective PASSED [ 14%]
tests/test_core.py::TestCoreObjects::test_enums PASSED                   [ 15%]
tests/test_core.py::TestCoreObjects::test_bar_data_creation PASSED       [ 15%]
tests/test_core.py::TestCoreObjects::test_bar_data_validation PASSED     [ 16%]
tests/test_core.py::TestCoreObjects::test_tick_data PASSED               [ 16%]
tests/test_core.py::TestCoreObjects::test_order_data PASSED              [ 16%]
tests/test_core.py::TestCoreObjects::test_trade_data PASSED              [ 17%]
tests/test_core.py::TestCoreObjects::test_position_data PASSED           [ 17%]
tests/test_core.py::TestCoreObjects::test_account_data PASSED            [ 18%]
tests/test_core.py::TestCoreObjects::test_symbol_parsing PASSED          [ 18%]
tests/test_core.py::TestCoreObjects::test_symbol_formatting PASSED       [ 19%]
tests/test_core.py::TestEventEngine::test_event_engine_start_stop PASSED [ 19%]
tests/test_core.py::TestEventEngine::test_event_registration PASSED      [ 19%]
tests/test_core.py::TestEventEngine::test_event_unregister PASSED        [ 20%]
tests/test_core.py::TestConfig::test_global_config_creation PASSED       [ 20%]
tests/test_core.py::TestConfig::test_global_config_validation PASSED     [ 21%]
tests/test_core.py::TestConfig::test_config_manager PASSED               [ 21%]
tests/test_core.py::TestPaperGateway::test_gateway_connection PASSED     [ 22%]
tests/test_core.py::TestPaperGateway::test_submit_order PASSED           [ 22%]
tests/test_core.py::TestPaperGateway::test_cancel_order PASSED           [ 22%]
tests/test_data.py::TestDataProviders::test_provider_creation PASSED     [ 23%]
tests/test_data.py::TestDataProviders::test_akshare_provider SKIPPEDars') [ 23%]
tests/test_data.py::TestDataProviders::test_tushare_provider SKIPPED     [ 24%]
tests/test_data.py::TestDataProviders::test_provider_interface PASSED    [ 24%]
tests/test_data.py::TestDatabaseManager::test_db_creation PASSED         [ 25%]
tests/test_data.py::TestDatabaseManager::test_save_and_load_data PASSED  [ 25%]
tests/test_data.py::TestDatabaseManager::test_data_update PASSED         [ 25%]
tests/test_data.py::TestDatabaseManager::test_check_data_exists PASSED   [ 26%]
tests/test_data.py::TestDatabaseManager::test_delete_data PASSED         [ 26%]
tests/test_data.py::TestDatabaseManager::test_multiple_symbols PASSED    [ 27%]
tests/test_data.py::TestDataPortal::test_portal_creation PASSED          [ 27%]
tests/test_data.py::TestDataPortal::test_get_bars_with_cache PASSED      [ 28%]
tests/test_data.py::TestDataPortal::test_force_update PASSED             [ 28%]
tests/test_data.py::TestDataPortal::test_batch_download PASSED           [ 29%]
tests/test_data.py::TestDataPortal::test_data_validation PASSED          [ 29%]
tests/test_ml_enhanced_strategy.py::test_ml_enhanced_feature_engineering_columns PASSED [ 29%]
tests/test_ml_enhanced_strategy.py::test_ml_enhanced_generate_signals_dummy_model FAILED [ 30%]
tests/test_ml_enhanced_strategy.py::test_ml_enhanced_generate_signals_no_sklearn PASSED [ 30%]
tests/test_ml_enhanced_strategy.py::test_ml_ensemble_strategy_averages_probabilities PASSED [ 31%]
tests/test_ml_enhanced_strategy.py::test_ml_ensemble_strategy_empty_models_returns_zero_signal PASSED [ 31%]
tests/test_ml_enhanced_strategy.py::test_ml_enhanced_get_model_branches FAILED [ 32%]
tests/test_ml_enhanced_strategy.py::test_ml_enhanced_generate_signals_chinese_columns FAILED [ 32%]
tests/test_ml_enhanced_strategy.py::test_ml_enhanced_get_feature_importance PASSED [ 32%]
tests/test_ml_enhanced_strategy.py::test_ml_enhanced_coerce_casts_types PASSED [ 33%]
tests/test_ml_enhanced_strategy.py::test_ml_enhanced_training_failure_warning FAILED [ 33%]
tests/test_ml_strategies_new.py::test_deep_sequence_strategy_outputs_signal_and_prob PASSED [ 34%]
tests/test_ml_strategies_new.py::test_rl_strategy_generates_actions PASSED [ 34%]
tests/test_ml_strategies_new.py::test_feature_selection_and_ensemble PASSED [ 35%]
tests/test_ml_strategies_new.py::test_regime_adaptive_filters_high_vol PASSED [ 35%]
tests/test_ml_strategies_new.py::test_ml_walkforward_insufficient_data_returns_zero_signal PASSED [ 35%]
tests/test_ml_strategies_new.py::test_ml_walkforward_model_none_returns_zero_signal PASSED [ 36%]
tests/test_ml_strategies_new.py::test_ml_walkforward_dummy_model_generates_signals PASSED [ 36%]
tests/test_ml_strategies_new.py::test_ml_walkforward_ta_accepts_english_columns PASSED [ 37%]
tests/test_ml_strategies_new.py::test_ml_walkforward_partial_fit_path PASSED [ 37%]
tests/test_ml_strategies_new.py::test_ml_walkforward_decision_function_path_and_regime PASSED [ 38%]
tests/test_ml_strategies_new.py::test_ml_walkforward_torch_helpers SKIPPED [ 38%]
tests/test_ml_strategies_new.py::test_ml_walkforward_make_model_branches PASSED [ 38%]
tests/test_ml_strategies_new.py::test_ml_walkforward_torch_mlp_branch PASSED [ 39%]
tests/test_ml_strategies_new.py::test_basic_features_fallback_no_price_columns PASSED [ 39%]
tests/test_ml_strategies_new.py::test_deep_sequence_empty_df_returns_zero PASSED [ 40%]
tests/test_ml_strategies_new.py::test_deep_sequence_no_torch PASSED      [ 40%]
tests/test_ml_strategies_new.py::test_rl_strategy_empty_df_returns_zero PASSED [ 41%]
tests/test_ml_strategies_new.py::test_feature_selection_empty_df_returns_zero PASSED [ 41%]
tests/test_ml_strategies_new.py::test_feature_selection_constant_features_fallback PASSED [ 41%]
tests/test_ml_strategies_new.py::test_ensemble_voting_empty_strategies_returns_zero PASSED [ 42%]
tests/test_ml_strategies_new.py::test_ensemble_voting_majority_vote PASSED [ 42%]
tests/test_ml_strategies_new.py::test_regime_adaptive_empty_df_returns_zero PASSED [ 43%]
tests/test_mlops_data_adapter.py::test_normalize_ohlcv_frame_maps_columns PASSED [ 43%]
tests/test_mlops_data_adapter.py::test_align_to_trading_calendar_fills PASSED [ 44%]
tests/test_mlops_data_adapter.py::test_build_feature_frame_adds_returns PASSED [ 44%]
tests/test_mlops_inference.py::test_inference_service_sets_model_id PASSED [ 45%]
tests/test_mlops_inference.py::test_batch_inference_runner_runs PASSED   [ 45%]
tests/test_mlops_model_registry.py::test_license_policy_default PASSED   [ 45%]
tests/test_mlops_model_registry.py::test_model_registry_register_and_promote PASSED [ 46%]
tests/test_mlops_signals.py::test_normalize_signal_output_scalar PASSED  [ 46%]
tests/test_mlops_signals.py::test_normalize_signal_output_frame PASSED   [ 47%]
tests/test_mlops_signals.py::test_ai_signal_strategy_executes_buy PASSED [ 47%]
tests/test_mlops_validation.py::test_population_stability_index_positive FAILED [ 48%]
tests/test_mlops_validation.py::test_detect_feature_drift_flags_column FAILED [ 48%]
tests/test_mlops_validation.py::test_compare_backtest_live_metrics PASSED [ 48%]
tests/test_monitoring.py::test_heartbeat_emitter_emits PASSED            [ 49%]
tests/test_monitoring.py::test_heartbeat_monitor_timeout PASSED          [ 49%]
tests/test_monitoring.py::test_run_with_heartbeat_monitor_restarts PASSED [ 50%]
tests/test_pipeline.py::TestFactorClasses::test_factor_base_class_exists PASSED [ 50%]
tests/test_pipeline.py::TestFactorClasses::test_returns_factor_exists PASSED [ 51%]
tests/test_pipeline.py::TestFactorClasses::test_momentum_factor_exists PASSED [ 51%]
tests/test_pipeline.py::TestFactorClasses::test_rsi_factor_exists PASSED [ 51%]
tests/test_pipeline.py::TestFactorClasses::test_sma_factor_exists PASSED [ 52%]
tests/test_pipeline.py::TestFactorClasses::test_ema_factor_exists PASSED [ 52%]
tests/test_pipeline.py::TestFactorClasses::test_macd_factor_exists PASSED [ 53%]
tests/test_pipeline.py::TestPipelineClass::test_pipeline_class_exists PASSED [ 53%]
tests/test_pipeline.py::TestPipelineClass::test_create_pipeline_function_exists PASSED [ 54%]
tests/test_pipeline.py::TestPipelineClass::test_pipeline_creation PASSED [ 54%]
tests/test_pipeline.py::TestHandlers::test_pipeline_event_collector_exists PASSED [ 54%]
tests/test_pipeline.py::TestHandlers::test_make_pipeline_handlers_exists PASSED [ 55%]
tests/test_pipeline.py::TestHandlers::test_progress_tracking_collector_exists PASSED [ 55%]
tests/test_pipeline.py::TestHandlers::test_make_progress_handlers_exists PASSED [ 56%]
tests/test_pipeline.py::TestHandlers::test_make_pipeline_handlers PASSED [ 56%]
tests/test_pipeline.py::TestHandlers::test_make_progress_handlers PASSED [ 57%]
tests/test_repro_snapshot.py::test_snapshot_signature_stable PASSED      [ 57%]
tests/test_simulation.py::test_order_creation PASSED                     [ 58%]
tests/test_simulation.py::test_order_properties PASSED                   [ 58%]
tests/test_simulation.py::test_order_book_creation PASSED                [ 58%]
tests/test_simulation.py::test_order_book_limit_orders PASSED            [ 59%]
tests/test_simulation.py::test_order_book_stop_orders PASSED             [ 59%]
tests/test_simulation.py::test_fixed_slippage PASSED                     [ 60%]
tests/test_simulation.py::test_percent_slippage PASSED                   [ 60%]
tests/test_simulation.py::test_volume_share_slippage PASSED              [ 61%]
tests/test_simulation.py::test_matching_engine_market_order PASSED       [ 61%]
tests/test_simulation.py::test_matching_engine_limit_order PASSED        [ 61%]
tests/test_simulation.py::test_matching_engine_stop_order PASSED         [ 62%]
tests/test_simulation.py::test_matching_engine_cancel PASSED             [ 62%]
tests/test_strategy.py::TestStrategyComponents::test_base_strategy_exists PASSED [ 63%]
tests/test_strategy.py::TestStrategyComponents::test_strategy_context_exists PASSED [ 63%]
tests/test_strategy.py::TestStrategyComponents::test_backtrader_adapter_exists PASSED [ 64%]
tests/test_strategy.py::TestStrategyComponents::test_position_info_exists PASSED [ 64%]
tests/test_strategy.py::TestStrategyComponents::test_account_info_exists PASSED [ 64%]
tests/test_strategy.py::TestStrategyComponents::test_bar_data_exists PASSED [ 65%]
tests/test_strategy.py::TestPositionInfo::test_position_creation PASSED  [ 65%]
tests/test_strategy.py::TestPositionInfo::test_position_is_long PASSED   [ 66%]
tests/test_strategy.py::TestPositionInfo::test_position_is_short PASSED  [ 66%]
tests/test_strategy.py::TestPositionInfo::test_position_is_flat PASSED   [ 67%]
tests/test_strategy.py::TestAccountInfo::test_account_creation PASSED    [ 67%]
tests/test_strategy.py::TestBarData::test_bar_data_creation PASSED       [ 67%]
tests/test_strategy.py::TestBaseStrategy::test_strategy_params PASSED    [ 68%]
tests/test_strategy.py::TestBaseStrategy::test_strategy_params_override PASSED [ 68%]
tests/test_system_integration.py::TestSystemDataFlow::test_full_data_pipeline PASSED [ 69%]
tests/test_system_integration.py::TestSystemDataFlow::test_database_persistence PASSED [ 69%]
tests/test_system_integration.py::TestSystemBacktestFlow::test_simple_backtest SKIPPEDyword argument 'strategy_class') [ 70%]
tests/test_system_integration.py::TestSystemBacktestFlow::test_multi_symbol_backtest SKIPPEDted keyword argument
'strategy_class')                                                        [ 70%]
tests/test_system_integration.py::TestSystemBacktestFlow::test_backtest_with_analysis SKIPPEDcted keyword argument
'strategy_class')                                                        [ 70%]
tests/test_system_integration.py::TestSystemCLI::test_cli_run_command SKIPPEDgs=['/opt/hostedtoolcache/Python/3.11.14/x64/bin/python',
'unified_backtest_framework.py', 'run', '--strategy', 'BuyAndHold', '--
symbols', '600519.SH', '--start', '2024-01-01', '--end', '2024-01-31', '
--output-dir', '/tmp/tmpm70um96b'], returncode=2, stdout='',
stderr="usage: unified_backtest_framework.py run [-h]\n
[--strategy {adx_trend,auction_open,boll_e,bollinger,bollinger_rsi,donch
ian,donchian_atr,ema,futures_grid,futures_grid_atr,futures_ma_cross,futu
res_market_making,index_enhancement,industry_rotation,intraday_opt,intra
day_reversion,kama,kama_opt,keltner,keltner_adaptive,macd,macd_e,macd_hi
st,macd_impulse,macd_r,macd_zero,ml_meta,ml_prob_band,ml_walk,multifacto
r_robust,multifactor_selection,risk_parity,rsi,rsi_divergence,rsi_ma_fil
ter,rsi_trend,sma_cross,sma_trend_following,trend_pullback_enhanced,trip
le_ma,triple_ma_adx,turning_point,turtle_futures,zscore,zscore_enhanced}
]\n                                         --symbols SYMBOLS [SYMBOLS
...]\n                                         --start START --end END\n
[--source {akshare,tushare,yfinance}]\n
[--benchmark BENCHMARK]\n
[--benchmark_source BENCHMARK_SOURCE]\n
[--params PARAMS] [--cash CASH]\n
[--commission COMMISSION]\n
[--slippage SLIPPAGE] [--adj ADJ]\n
[--out_dir OUT_DIR]\n
[--cache_dir CACHE_DIR]\n
[--calendar {off,fill}] [--plot]\n
[--fee-config FEE_CONFIG]\n
[--fee-params FEE_PARAMS]\nunified_backtest_framework.py run: error:
argument --strategy: invalid choice: 'BuyAndHold' (choose from
'adx_trend', 'auction_open', 'boll_e', 'bollinger', 'bollinger_rsi',
'donchian', 'donchian_atr', 'ema', 'futures_grid', 'futures_grid_atr',
'futures_ma_cross', 'futures_market_making', 'index_enhancement',
'industry_rotation', 'intraday_opt', 'intraday_reversion', 'kama',
'kama_opt', 'keltner', 'keltner_adaptive', 'macd', 'macd_e',
'macd_hist', 'macd_impulse', 'macd_r', 'macd_zero', 'ml_meta',
'ml_prob_band', 'ml_walk', 'multifactor_robust',
'multifactor_selection', 'risk_parity', 'rsi', 'rsi_divergence',
'rsi_ma_filter', 'rsi_trend', 'sma_cross', 'sma_trend_following',
'trend_pullback_enhanced', 'triple_ma', 'triple_ma_adx',
'turning_point', 'turtle_futures', 'zscore',
'zscore_enhanced')\n").returncode)                                       [ 71%]
tests/test_system_integration.py::TestSystemCLI::test_cli_list_command SKIPPEDompletedProcess(args=['/opt/hostedtoolcache/Python/3.11.14/x64/bin
/python', 'unified_backtest_framework.py', 'list'], returncode=0,
stdout='', stderr='').stdout)                                            [ 71%]
tests/test_system_integration.py::TestSystemGUI::test_gui_imports PASSED [ 72%]
tests/test_system_integration.py::TestSystemGUI::test_gui_config_validation PASSED [ 72%]
tests/test_system_integration.py::TestSystemIntegration::test_end_to_end_workflow SKIPPEDyword argument 'strategy_class') [ 73%]
tests/test_system_integration.py::TestSystemIntegration::test_concurrent_operations PASSED [ 73%]
tests/test_system_integration.py::TestSystemPerformance::test_large_dataset_handling PASSED [ 74%]
tests/test_system_integration.py::TestSystemPerformance::test_memory_efficiency PASSED [ 74%]
tests/test_system_integration.py::TestSystemErrorHandling::test_invalid_symbol_handling PASSED [ 74%]
tests/test_system_integration.py::TestSystemErrorHandling::test_date_range_validation PASSED [ 75%]
tests/test_system_integration.py::TestSystemErrorHandling::test_missing_data_handling PASSED [ 75%]
tests/test_system_integration.py::TestSystemCoverage::test_all_modules_importable PASSED [ 76%]
tests/test_system_integration.py::TestSystemCoverage::test_core_functionality_coverage PASSED [ 76%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_imports PASSED [ 77%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_gateway_config_defaults PASSED [ 77%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_gateway_config_custom PASSED [ 77%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_paper_trading_adapter_initialization PASSED [ 78%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_paper_trading_adapter_connect PASSED [ 78%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_paper_trading_adapter_submit_order PASSED [ 79%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_paper_trading_adapter_market_order_fill PASSED [ 79%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_paper_trading_adapter_position_update PASSED [ 80%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_paper_trading_adapter_sell_order PASSED [ 80%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_paper_trading_adapter_cancel_order PASSED [ 80%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_paper_trading_adapter_query_account PASSED [ 81%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_trading_gateway_initialization PASSED [ 81%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_trading_gateway_connect PASSED [ 82%]
tests/test_trading_infrastructure.py::TestTradingGatewayModule::test_trading_gateway_buy_sell PASSED [ 82%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_imports PASSED [ 83%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_managed_order_creation PASSED [ 83%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_managed_order_properties PASSED [ 83%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_order_manager_initialization PASSED [ 84%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_order_manager_create_order PASSED [ 84%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_order_manager_submit_order PASSED [ 85%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_order_manager_cancel_order PASSED [ 85%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_order_manager_get_active_orders PASSED [ 86%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_order_manager_get_orders_by_symbol PASSED [ 86%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_order_manager_get_order PASSED [ 87%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_order_manager_invalid_order_id PASSED [ 87%]
tests/test_trading_infrastructure.py::TestOrderManagerModule::test_order_manager_cancel_nonexistent PASSED [ 87%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_imports PASSED [ 88%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_risk_config_defaults PASSED [ 88%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_risk_config_factory_conservative PASSED [ 89%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_risk_config_factory_moderate PASSED [ 89%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_risk_config_factory_aggressive PASSED [ 90%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_risk_manager_initialization PASSED [ 90%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_risk_manager_check_order_basic PASSED [ 90%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_risk_manager_check_order_value_limit PASSED [ 91%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_risk_manager_check_position_limit PASSED [ 91%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_risk_check_result PASSED [ 92%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_position_stop_creation PASSED [ 92%]
tests/test_trading_infrastructure.py::TestRiskManagerV2Module::test_daily_risk_stats PASSED [ 93%]
tests/test_trading_infrastructure.py::TestRealtimeDataModule::test_imports PASSED [ 93%]
tests/test_trading_infrastructure.py::TestRealtimeDataModule::test_realtime_quote_creation PASSED [ 93%]
tests/test_trading_infrastructure.py::TestRealtimeDataModule::test_realtime_data_manager_initialization PASSED [ 94%]
tests/test_trading_infrastructure.py::TestRealtimeDataModule::test_bar_builder PASSED [ 94%]
tests/test_trading_infrastructure.py::TestRealtimeDataModule::test_signal_types PASSED [ 95%]
tests/test_trading_infrastructure.py::TestRealtimeDataModule::test_realtime_signal_generator PASSED [ 95%]
tests/test_trading_infrastructure.py::TestRealtimeDataModule::test_signal_rule_creation PASSED [ 96%]
tests/test_trading_infrastructure.py::TestRealtimeDataModule::test_price_breakout_rule PASSED [ 96%]
tests/test_trading_infrastructure.py::TestRealtimeDataModule::test_simulation_data_provider PASSED [ 96%]
tests/test_trading_infrastructure.py::TestIntegration::test_gateway_with_order_manager PASSED [ 97%]
tests/test_trading_infrastructure.py::TestIntegration::test_risk_manager_with_order PASSED [ 97%]
tests/test_trading_infrastructure.py::TestIntegration::test_full_trading_flow PASSED [ 98%]
tests/test_trading_infrastructure.py::TestErrorHandling::test_order_manager_invalid_order_id PASSED [ 98%]
tests/test_trading_infrastructure.py::TestErrorHandling::test_order_manager_cancel_nonexistent PASSED [ 99%]
tests/test_trading_infrastructure.py::TestErrorHandling::test_risk_manager_zero_account PASSED [ 99%]
/opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/coverage/inorout.py:495: CoverageWarning: Module src/strategies/ml_strategies.py was never imported. (module-not-imported); see https://coverage.readthedocs.io/en/7.13.2/messages.html#warning-module-not-imported
  self.warn(f"Module {pkg} was never imported.", slug="module-not-imported")
/opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/coverage/inorout.py:495: CoverageWarning: Module src/strategies/ml_enhanced_strategy.py was never imported. (module-not-imported); see https://coverage.readthedocs.io/en/7.13.2/messages.html#warning-module-not-imported
  self.warn(f"Module {pkg} was never imported.", slug="module-not-imported")
tests/test_trading_infrastructure.py::TestErrorHandling::test_realtime_manager_no_tick PASSED [100%]
ERROR: Coverage failure: total of 33 is less than fail-under=90


=================================== FAILURES ===================================
________________ test_ml_enhanced_generate_signals_dummy_model _________________
tests/test_ml_enhanced_strategy.py:64: in test_ml_enhanced_generate_signals_dummy_model
    res = strat.generate_signals(df)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^
src/strategies/ml_enhanced_strategy.py:276: in generate_signals
    self._scaler = StandardScaler()
                   ^^^^^^^^^^^^^^
E   NameError: name 'StandardScaler' is not defined
_____________________ test_ml_enhanced_get_model_branches ______________________
tests/test_ml_enhanced_strategy.py:124: in test_ml_enhanced_get_model_branches
    monkeypatch.setattr(mes, "GradientBoostingClassifier", lambda **kwargs: DummyModel())
E   AttributeError: <module 'src.strategies.ml_enhanced_strategy' from '/home/runner/work/stock/stock/src/strategies/ml_enhanced_strategy.py'> has no attribute 'GradientBoostingClassifier'
______________ test_ml_enhanced_generate_signals_chinese_columns _______________
tests/test_ml_enhanced_strategy.py:165: in test_ml_enhanced_generate_signals_chinese_columns
    res = strat.generate_signals(df)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^
src/strategies/ml_enhanced_strategy.py:276: in generate_signals
    self._scaler = StandardScaler()
                   ^^^^^^^^^^^^^^
E   NameError: name 'StandardScaler' is not defined
__________________ test_ml_enhanced_training_failure_warning ___________________
tests/test_ml_enhanced_strategy.py:209: in test_ml_enhanced_training_failure_warning
    res = strat.generate_signals(df)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^
src/strategies/ml_enhanced_strategy.py:276: in generate_signals
    self._scaler = StandardScaler()
                   ^^^^^^^^^^^^^^
E   NameError: name 'StandardScaler' is not defined
___________________ test_population_stability_index_positive ___________________
tests/test_mlops_validation.py:12: in test_population_stability_index_positive
    psi = population_stability_index(expected, actual)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
src/mlops/validation.py:26: in population_stability_index
    breakpoints[0] = -np.inf
    ^^^^^^^^^^^^^^
E   ValueError: assignment destination is read-only
____________________ test_detect_feature_drift_flags_column ____________________
tests/test_mlops_validation.py:19: in test_detect_feature_drift_flags_column
    result = detect_feature_drift(ref, cur, threshold=0.1)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
src/mlops/validation.py:51: in detect_feature_drift
    psi = population_stability_index(reference[col], current[col])
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
src/mlops/validation.py:26: in population_stability_index
    breakpoints[0] = -np.inf
    ^^^^^^^^^^^^^^
E   ValueError: assignment destination is read-only
=============================== warnings summary ===============================
src/core/config.py:39
  /home/runner/work/stock/stock/src/core/config.py:39: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    @validator("commission")

src/core/config.py:80
  /home/runner/work/stock/stock/src/core/config.py:80: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    @validator("level")

src/core/config.py:88
  /home/runner/work/stock/stock/src/core/config.py:88: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class GlobalConfig(BaseModel):

tests/test_combo_optimizer.py::test_load_nav_series_fallback_index
  /home/runner/work/stock/stock/src/optimizer/combo_optimizer.py:146: UserWarning: Could not infer format, so each element will be parsed individually, falling back to `dateutil`. To ensure parsing is consistent and as-expected, please specify a format.
    nav.index = pd.to_datetime(df.iloc[:, 0])

tests/test_ml_enhanced_strategy.py::test_ml_enhanced_generate_signals_no_sklearn
  /home/runner/work/stock/stock/src/strategies/ml_enhanced_strategy.py:234: UserWarning: sklearn not installed, returning zero signals
    warnings.warn("sklearn not installed, returning zero signals")

tests/test_ml_strategies_new.py::test_ml_walkforward_insufficient_data_returns_zero_signal
  /home/runner/work/stock/stock/src/strategies/ml_strategies.py:201: UserWarning: 样本不足，返回空信号
    warnings.warn("样本不足，返回空信号")

tests/test_ml_strategies_new.py::test_ml_walkforward_model_none_returns_zero_signal
  /home/runner/work/stock/stock/src/strategies/ml_strategies.py:209: UserWarning: 未找到可用模型，默认空信号
    warnings.warn("未找到可用模型，默认空信号")

tests/test_ml_strategies_new.py::test_feature_selection_constant_features_fallback
  /opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/numpy/lib/_function_base_impl.py:3023: RuntimeWarning: invalid value encountered in divide
    c /= stddev[:, None]

tests/test_ml_strategies_new.py::test_feature_selection_constant_features_fallback
  /opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/numpy/lib/_function_base_impl.py:3024: RuntimeWarning: invalid value encountered in divide
    c /= stddev[None, :]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.11.14-final-0 _______________

Name                                                Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------------
src/__init__.py                                         2      0   100%
src/backtest/analysis.py                              105     32    70%   31, 114-116, 119-121, 126-128, 131-133, 137-139, 142-144, 147-160
src/backtest/engine.py                                531    469    12%   27-28, 89-101, 111-119, 174-193, 197-216, 238-511, 533-569, 598-659, 681-832, 856-954, 959-981, 986-995, 1000-1024, 1029-1047, 1066-1146, 1155-1173
src/backtest/plotting.py                              403    386     4%   17-18, 29-30, 34-61, 71-202, 225-430, 474-874
src/backtest/repro.py                                  93     47    49%   29, 31-34, 45-47, 70-103, 139-143
src/backtest/strategy_modules.py                      665    576    13%   17-18, 46-50, 61-97, 117-137, 149-163, 183-184, 187-197, 207-208, 219, 222-228, 231, 264-282, 285-399, 404-411, 459-475, 479-484, 487-533, 538-546, 598-599, 630-666, 670-671, 675-701, 705-817, 821-838, 887-911, 914-915, 918-933, 936-1003, 1006-1018, 1050-1065, 1068-1069, 1072-1087, 1090-1148, 1151-1162
src/bt_plugins/__init__.py                              4      0   100%
src/bt_plugins/base.py                                 28      6    79%   12-13, 105-106, 124-125
src/bt_plugins/fees_cn.py                              60     48    20%   12-13, 46-48, 54-126, 145, 151-188
src/core/__init__.py                                   14      0   100%
src/core/config.py                                    143     72    50%   42, 82-85, 149-169, 182-215, 224-241, 254-260, 264, 268-270, 290-308, 314, 373-376
src/core/context.py                                   121     87    28%   85-89, 104, 116, 125-126, 138-166, 179-190, 202, 227-260, 285-304, 325-345, 357, 371-372, 376, 391-404, 423-425, 429, 433, 438, 443
src/core/defaults.py                                   27     10    63%   221-230, 235-237
src/core/error_handler.py                             213    153    28%   95-102, 106-109, 113-114, 131-133, 137-138, 194-202, 205, 213-285, 290, 295, 300, 344-374, 397-437, 475-479, 483-489, 493-494, 498-528, 541-563, 568-569, 574-575, 594-598, 610-613
src/core/events.py                                     75      6    92%   84-85, 99, 127-130
src/core/exceptions.py                                188     91    52%   79-95, 99, 122-125, 133-134, 154, 165-166, 180-183, 194-195, 215-220, 228-229, 237-238, 249-250, 270-273, 281-282, 290-293, 304-305, 322-323, 331-332, 343-344, 352-353, 373-374, 385-386, 397-398, 423-424, 435-436, 453-470, 484-487, 507
src/core/gateway.py                                    44     21    52%   169, 189-220, 253, 257, 261
src/core/interfaces.py                                156     10    94%   68, 79, 141, 145-148, 168, 172, 189
src/core/logger.py                                     96     54    44%   32-33, 57-62, 69-132, 139-156, 186, 198, 201, 219, 239-240, 243-245, 248-249, 255, 260, 265, 270
src/core/monitoring.py                                254    115    55%   21-23, 68-83, 87-130, 144-179, 183-191, 195-202, 206-227, 231-238, 242-244, 248, 252-258, 278-280, 285-287, 292-293, 321, 384, 403-404, 407-415, 454-462, 477-479, 483, 489-490
src/core/objects.py                                   218     40    82%   28, 39, 52, 66, 105, 107, 111, 129-133, 194-196, 201-203, 256, 304, 356, 404, 409-411, 415, 452, 485-494, 506-512, 517
src/core/order_manager.py                             307    145    53%   124, 130-131, 136, 140, 261, 264, 272, 297, 337-374, 392-393, 396-397, 419-424, 436-442, 465-466, 479, 485-487, 504-524, 546-593, 643-648, 653, 657, 659, 661, 663, 683-690, 694-699, 707-713, 721-742, 750, 754, 760-763, 767, 790-799, 811-835
src/core/paper_gateway_v3.py                          185    133    28%   39-40, 114, 147-148, 152-153, 180-183, 194, 205, 246-308, 323-346, 358-372, 387-432, 445-471, 494-508, 540-545, 562, 574-588, 601-616, 625-634
src/core/paper_runner_v3.py                           201    168    16%   108-231, 241-266, 302-356, 387-445, 476-494, 516-518, 522-523, 527-530, 534-535, 546-549, 553, 558-576, 597-602
src/core/performance.py                               293    209    29%   61-63, 103-117, 121-136, 140-144, 148-151, 155-162, 167-170, 203-238, 256, 271-274, 278-283, 289-293, 303-304, 313-318, 345-381, 393-411, 416, 458-504, 515-516, 540-541, 545, 549-551, 560, 564, 568-569, 573, 594-606, 630-655, 688-693, 706-709, 728-730, 733-739, 742
src/core/realtime_data.py                             458    236    48%   118, 122-124, 128-130, 134, 206-215, 240, 244-250, 272, 277, 282, 287, 294, 298, 302-309, 313-317, 368-370, 374-380, 386, 391-415, 419, 439-440, 443-445, 448, 451-452, 455-456, 474-477, 482, 487, 492, 496-517, 521-526, 530-535, 539-540, 544-550, 554-559, 563, 567-568, 620-622, 626-628, 632-633, 653-666, 670-677, 685, 695, 699-725, 733-741, 745-751, 754, 766, 770-772, 776-778, 782, 786, 859, 863, 867, 871-873, 877, 881-894, 898-910, 926-958, 971-999
src/core/risk_manager_v2.py                           327    147    55%   143, 193-251, 256-262, 286, 291-293, 299, 400, 403, 462, 486, 512-522, 529-539, 545-547, 560, 596-630, 634-636, 648-672, 676, 680, 694-709, 718-736, 743-752, 756, 760, 768-770, 774-776, 780, 788, 793-796, 799-800, 825-843, 847
src/core/strategy_base.py                             211    155    27%   127, 131, 150, 162, 178, 190, 247-250, 271-278, 286, 290-291, 295-296, 300-301, 305, 336-400, 417-423, 428-430, 441-453, 457-475, 479-494, 504-528, 538-553, 563-579, 584, 588-592, 596-599, 624-625, 629-665
src/core/trading_gateway.py                           329     96    71%   193-194, 245-246, 264-267, 286-304, 310, 392-394, 397-402, 405, 408, 412, 415, 418, 421, 424, 440-441, 444-448, 451, 454, 458, 461, 464, 467, 470, 485-486, 489-490, 493, 496, 500, 503, 506, 509, 512, 528-529, 532-537, 540, 543, 547, 550, 553, 556, 559, 647-652, 660-669, 691, 693-696, 700-702, 705, 709, 755, 776, 797, 809-810, 833, 837, 846
src/data_sources/data_portal.py                       147    116    21%   65, 102-124, 147-175, 214-270, 299-319, 331-348, 374, 378, 386-388, 392, 413-436, 452, 469-485, 511
src/data_sources/db_manager.py                        236    141    40%   82-85, 152-158, 200-214, 235, 314, 322-328, 353-387, 408-437, 538-566, 616-623, 627-629, 661-734, 757-811
src/data_sources/providers.py                         400    344    14%   74, 95, 114, 126-129, 140, 145, 159-172, 181-201, 206-253, 258-262, 288-348, 369-398, 413-455, 474-505, 515-541, 559-598, 608-622, 633-666, 675-689, 703-717, 729-763, 773-795, 806-834, 843-862, 884-889
src/data_sources/quality.py                            95     24    75%   34, 40-45, 75-91, 96, 177-217
src/data_sources/trading_calendar.py                   54     15    72%   22, 27-29, 35, 54, 58, 64, 75, 100-105
src/gateways/__init__.py                               15     15     0%   24-86
src/gateways/base_live_gateway.py                     482    482     0%   32-1164
src/gateways/hundsun_uft_gateway.py                   395    395     0%   64-1023
src/gateways/mappers.py                               165    165     0%   23-465
src/gateways/xtp_gateway.py                           292    292     0%   60-865
src/gateways/xtquant_gateway.py                       204    204     0%   56-689
src/indicators/__init__.py                              2      2     0%   5-7
src/indicators/technical.py                           102    102     0%   5-288
src/mlops/__init__.py                                   8      0   100%
src/mlops/data_adapter.py                              50      8    84%   34, 48-49, 54-55, 59, 77, 92
src/mlops/inference.py                                 44     11    75%   70-80
src/mlops/license_policy.py                            19      1    95%   33
src/mlops/model_registry.py                            92      5    95%   97, 132, 144, 151, 158
src/mlops/signals.py                                   77     19    75%   36, 40, 44, 56, 58-63, 66-67, 82, 118, 124-134, 136-137
src/mlops/strategy_adapter.py                          56     13    77%   27-29, 75, 85, 90-98
src/mlops/validation.py                                44     17    61%   22, 27-36, 50, 52-56, 71-72
src/optimizer/__init__.py                               1      0   100%
src/optimizer/combo_optimizer.py                       77      0   100%
src/pipeline/__init__.py                                3      0   100%
src/pipeline/factor_engine.py                         185    124    33%   44-45, 58, 61-62, 73, 77-80, 87, 91-94, 101, 105-123, 135, 142, 146-149, 157-160, 171, 175-176, 183, 187-188, 195, 199-200, 204-208, 212-216, 223, 227-233, 237-239, 246, 250-266, 277, 281-283, 290, 296, 332-334, 346-390, 402-413, 437-440, 446, 458
src/pipeline/handlers.py                              239    179    25%   26-27, 32-33, 40-41, 86-96, 112-151, 225-236, 240-252, 303-309, 318-346, 354-373, 382, 412-413, 473-485, 497-511, 515-530, 534-546, 550-555, 574-575, 638-653, 666-688, 692-712, 716-733, 737-742, 769-773
src/simulation/__init__.py                              5      0   100%
src/simulation/matching_engine.py                     122     34    72%   99, 112, 118, 123-124, 132, 150, 184-195, 199-202, 237-242, 271, 279-280, 292, 304, 316-319, 323-325
src/simulation/order.py                                75      5    93%   102, 111, 148, 153, 157
src/simulation/order_book.py                           74     27    64%   60, 62, 83, 85-86, 99, 101, 115, 174-178, 187-191, 203-206, 213-215, 219-221
src/simulation/slippage.py                             42      5    88%   119, 170, 174, 188, 200
src/strategies/__init__.py                             12      2    83%   61-62
src/strategies/adx_backtrader_strategy.py              63     52    17%   34-40, 44-46, 49-69, 72-74, 77-112, 117-126
src/strategies/arbitrage_strategies.py                 77     65    16%   21-22, 25-43, 57-58, 61-86, 100-101, 104-123
src/strategies/auction_backtrader_strategy.py          46     38    17%   38-40, 43-45, 49-75, 78-93, 97
src/strategies/backtrader_registry.py                 108     25    77%   868-871, 884-886, 891, 904-911, 921-926, 931-944
src/strategies/base.py                                 18      6    67%   29, 38-40, 44-45
src/strategies/bollinger_backtrader_strategy.py       213    193     9%   43-50, 54-56, 59-76, 79-81, 84-116, 121-166, 204-230, 235-237, 241-248, 251-342, 346-347, 350-356, 359-364
src/strategies/donchian_backtrader_strategy.py         55     44    20%   32-41, 45-47, 50-67, 70-72, 75-96, 101-110
src/strategies/ema_backtrader_strategy.py              90     77    14%   48-68, 72-74, 77-101, 104-106, 110-120, 124, 127-158, 163-178
src/strategies/enhanced_strategies.py                 278    222    20%   55-61, 64-66, 69-81, 84-113, 141-143, 146-148, 151-152, 155-181, 210-213, 216-218, 221-226, 230-236, 239-258, 287-291, 294-296, 299-300, 303-322, 350-357, 360-362, 365-366, 369-394, 421-424, 427-429, 432-433, 436-456, 483-490, 493-495, 498-499, 502-526, 533-540, 544-549, 553-559, 563-566, 570-574, 578-581, 585-588
src/strategies/futures_backtrader_strategy.py         119     94    21%   19-22, 25-31, 34-38, 58-61, 65-66, 70-97, 101-104, 116-117, 120-146, 159-163, 166-187, 190-194, 199, 208, 218, 226
src/strategies/intraday_backtrader_strategy.py         77     66    14%   37-39, 42, 46-47, 51-66, 70-82, 86-133, 136-142, 146
src/strategies/kama_backtrader_strategy.py             51     38    25%   26-36, 39-43, 65-74, 77-90, 94-103, 106-109, 114
src/strategies/keltner_backtrader_strategy.py          94     82    13%   48-61, 65-67, 70-92, 95-97, 101-106, 109-153, 158-171
src/strategies/macd_backtrader_strategy.py            314    274    13%   22-31, 35-37, 40-57, 60-62, 65-75, 93-102, 105-107, 110-113, 116-126, 145-154, 157-159, 162-165, 168-183, 188-230, 270-292, 299-300, 304, 308-315, 318-420, 423-424, 427-432, 435-439, 464-483, 486-488, 492, 495-500, 503-552
src/strategies/ml_enhanced_strategy.py                208     44    79%   25-30, 36-38, 46, 100-115, 270, 277-309, 314, 319, 340-345, 351
src/strategies/ml_strategies.py                       333     60    82%   31-34, 39, 44-45, 155-156, 162, 165, 169-184, 187-193, 239-241, 309-336, 351-354, 449, 455
src/strategies/multifactor_backtrader_strategy.py      92     72    22%   33-49, 53-93, 96-102, 120-122, 126-136, 139-145, 163-165, 169-179, 182-188, 193, 207, 216
src/strategies/optimized_strategies.py                359    308    14%   52-63, 66-70, 111-130, 133-135, 138-147, 150-187, 191-204, 209, 261-267, 270-272, 275-276, 280-318, 323-341, 345-350, 355, 405-410, 413-415, 418-506, 510-518, 523, 579-596, 599-601, 604-609, 612-660, 664-670, 675, 727-736, 739-741, 744-753, 756-795, 799-807, 812
src/strategies/rsi_backtrader_strategy.py             145    122    16%   38-52, 56-58, 61-83, 86-88, 92-97, 100-126, 143-148, 151-153, 156-159, 162-177, 193-199, 202-204, 207-210, 213-244, 249-264
src/strategies/sma_backtrader_strategy.py              35     27    23%   23-27, 30-39, 43-52, 55-58, 63
src/strategies/trend_pullback_enhanced.py              90     78    13%   63-88, 92-94, 97-124, 127-129, 151-162, 166-242, 247-260
src/strategies/triple_ma_backtrader_strategy.py        75     63    16%   37-51, 55-57, 60-82, 85-87, 91-96, 99-130, 135-145
src/strategies/unified_strategies.py                  112    112     0%   22-295
src/strategies/zscore_backtrader_strategy.py           95     83    13%   42-66, 70-72, 75-97, 100-102, 106-111, 114-151, 156-175
---------------------------------------------------------------------------------
TOTAL                                               12712   8504    33%
Coverage XML written to file coverage.xml
FAIL Required test coverage of 90% not reached. Total coverage: 33.10%
=========================== short test summary info ============================
FAILED tests/test_ml_enhanced_strategy.py::test_ml_enhanced_generate_signals_dummy_model - NameError: name 'StandardScaler' is not defined
FAILED tests/test_ml_enhanced_strategy.py::test_ml_enhanced_get_model_branches - AttributeError: <module 'src.strategies.ml_enhanced_strategy' from '/home/runner/work/stock/stock/src/strategies/ml_enhanced_strategy.py'> has no attribute 'GradientBoostingClassifier'
FAILED tests/test_ml_enhanced_strategy.py::test_ml_enhanced_generate_signals_chinese_columns - NameError: name 'StandardScaler' is not defined
FAILED tests/test_ml_enhanced_strategy.py::test_ml_enhanced_training_failure_warning - NameError: name 'StandardScaler' is not defined
FAILED tests/test_mlops_validation.py::test_population_stability_index_positive - ValueError: assignment destination is read-only
FAILED tests/test_mlops_validation.py::test_detect_feature_drift_flags_column - ValueError: assignment destination is read-only
============ 6 failed, 215 passed, 10 skipped, 9 warnings in 11.23s ============
Error: Process completed with exit code 1.