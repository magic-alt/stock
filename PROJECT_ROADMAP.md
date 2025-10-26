# 项目路线图 | Project Roadmap

**项目**: 量化回测系统 (Quantitative Backtesting Platform)  
**当前版本**: V2.10.2.0  
**更新日期**: 2025-10-26  
**状态**: 🟢 Active Development

---

## 📋 目录

- [版本历史](#版本历史)
- [当前状态](#当前状态)
- [开发路线图](#开发路线图)
- [已完成功能](#已完成功能)
- [进行中任务](#进行中任务)
- [未来计划](#未来计划)

---

## 📅 版本历史

### V2.10.2.0 (2025-10-26) ✅ 当前版本
**主题**: 企业级重构 + 报告系统 + CI/CD

**核心更新**:
- ✅ Markdown回测报告系统
- ✅ GitHub CI/CD持续集成
- ✅ 项目目录结构标准化
- ✅ Pre-commit钩子和代码质量检查
- ✅ 完善文档和示例代码

**详细**: 查看 [CHANGELOG.md](CHANGELOG.md#v21020---2025-10-26)

---

### V2.10.1.2 (2025-01-26)
**主题**: 数据库优化 + 复权文档

- ✅ 数据库增加公司名称字段
- ✅ 复权类型详细文档 (230+行)
- ✅ 自动保存报告到report目录
- ✅ 双格式保存 (PNG + Pickle)

---

### V2.10.1.1 (2025-01-26)
**主题**: 数据库结构优化

- ✅ Per-Symbol独立表架构
- ✅ 国际指数支持
- ✅ CSV批量导入功能
- ✅ 13/13测试通过

---

### V2.8.5
**主题**: ML策略集成

- ✅ 机器学习走步训练策略
- ✅ XGBoost/RandomForest/PyTorch支持
- ✅ 自动特征工程
- ✅ 多空独立阈值

---

### V2.5.1
**主题**: 关键Bug修复

- ✅ 修复StopIteration错误
- ✅ 修复AKShare符号格式问题
- ✅ 修复时区不匹配错误

---

### V2.5.0 - Phase 2 完成
**主题**: 模块化重构

- ✅ 分析、绘图、自动化模块分离
- ✅ 代码从2138行精简到214行
- ✅ Pareto前沿分析
- ✅ 风险平价策略

---

## 🎯 当前状态

### 项目成熟度
| 模块 | 状态 | 完成度 | 说明 |
|------|------|--------|------|
| **数据源** | 🟢 稳定 | 95% | 支持AKShare/YFinance/TuShare |
| **策略库** | 🟢 稳定 | 90% | 15+策略，包含ML策略 |
| **回测引擎** | 🟢 稳定 | 95% | 单次/批量/自动化流程 |
| **可视化** | 🟢 稳定 | 90% | 7种指标图表 + Markdown报告 |
| **GUI界面** | 🟡 完善中 | 80% | tkinter界面，功能完整 |
| **文档** | 🟢 完善 | 95% | 完整文档 + 示例代码 |
| **测试** | 🟢 完善 | 85% | 单元测试 + 集成测试 |
| **CI/CD** | 🟢 就绪 | 100% | GitHub Actions全流程 |

### 技术债务
- 🟡 GUI界面需要重构（考虑使用更现代的框架）
- 🟡 测试覆盖率需要提升到90%+
- 🟡 文档需要添加英文版本
- 🟡 ML策略需要更多实盘验证

---

## 🗺️ 开发路线图

### Phase 3: 实盘交易集成 (规划中)
**目标**: 将回测系统扩展到实盘交易

#### 3.1 交易接口层 🔴 未开始
- [ ] 设计统一的交易接口 (`TradingGateway`)
- [ ] 支持模拟交易（虚拟盘）
- [ ] 支持实盘交易（通过经纪商API）
- [ ] 订单管理系统 (Order Management System)

**支持的经纪商**:
- [ ] 东方财富API
- [ ] 富途API (FutuOpenD)
- [ ] 雪球API
- [ ] Interactive Brokers (IBKR)

#### 3.2 风险管理系统 🔴 未开始
- [ ] 仓位管理 (Position Sizing)
- [ ] 风险限额 (Risk Limits)
- [ ] 实时风控监控
- [ ] 自动止损/止盈

#### 3.3 实时数据流 🔴 未开始
- [ ] WebSocket实时行情
- [ ] 分钟级K线数据
- [ ] Tick级数据支持
- [ ] 实时信号生成

---

### Phase 4: Web平台 (规划中)
**目标**: 构建基于Web的量化平台

#### 4.1 Web后端 🔴 未开始
- [ ] FastAPI/Flask REST API
- [ ] 用户认证和权限管理
- [ ] 策略市场 (Strategy Marketplace)
- [ ] 云端回测服务

#### 4.2 Web前端 🔴 未开始
- [ ] React/Vue前端界面
- [ ] 可视化拖拽策略编辑器
- [ ] 实时监控仪表板
- [ ] 移动端支持

#### 4.3 云部署 🔴 未开始
- [ ] Docker容器化
- [ ] Kubernetes编排
- [ ] 微服务架构
- [ ] 分布式回测集群

---

### Phase 5: 高级功能 (未来)
**目标**: 企业级高级功能

#### 5.1 机器学习增强 🟡 进行中
- [x] 基础ML策略 (V2.8.5)
- [ ] 深度学习模型 (LSTM, Transformer)
- [ ] 强化学习 (RL)
- [ ] 自动化特征选择
- [ ] 模型集成 (Ensemble)

#### 5.2 大数据支持 🔴 未开始
- [ ] 分布式数据存储 (ClickHouse)
- [ ] 流式处理 (Kafka/Flink)
- [ ] 大规模并行回测
- [ ] 云端存储集成 (OSS/S3)

#### 5.3 社区功能 🔴 未开始
- [ ] 策略分享平台
- [ ] 社区论坛
- [ ] 策略评级系统
- [ ] 知识库和教程

---

## ✅ 已完成功能

### 核心功能
- [x] 统一回测框架 (V2.0)
- [x] 多数据源支持 (V2.1)
- [x] 15+ 交易策略 (V2.4)
- [x] 参数优化 (网格搜索) (V2.3)
- [x] Pareto前沿分析 (V2.5)
- [x] 自动化流程 (auto_pipeline) (V2.5)
- [x] GUI图形界面 (V2.8.1)
- [x] 机器学习策略 (V2.8.5)
- [x] 数据库优化 (Per-Symbol表) (V2.10.1.1)
- [x] Markdown报告系统 (V2.10.2.0)
- [x] CI/CD集成 (V2.10.2.0)

### 数据源
- [x] AKShare (中国A股，免费)
- [x] YFinance (全球市场，免费)
- [x] TuShare (专业数据，需Token)
- [x] SQLite3数据库缓存
- [x] CSV导入/导出

### 策略库
- [x] 趋势跟踪: SMA/EMA Cross, MACD, ADX, Donchian
- [x] 均值回归: Bollinger, RSI, Z-Score, Keltner
- [x] 多指标: Triple MA
- [x] 组合策略: Risk Parity
- [x] 机器学习: ML Walk-Forward

### 可视化
- [x] K线图表 (Candlestick/Line)
- [x] 7种技术指标叠加
- [x] 买卖信号标注
- [x] 中文配色方案
- [x] PNG/Pickle双格式导出
- [x] Markdown报告生成
- [x] JSON数据导出

### 工程化
- [x] 模块化架构 (src/)
- [x] 单元测试 (tests/)
- [x] 集成测试
- [x] 文档完善 (docs/)
- [x] 示例代码 (examples/)
- [x] GitHub CI/CD
- [x] Pre-commit钩子
- [x] 代码质量检查

---

## 🚧 进行中任务

### 高优先级
- [ ] 提升测试覆盖率到90%+
- [ ] 添加更多ML策略示例
- [ ] 优化GUI界面响应速度
- [ ] 完善英文文档

### 中优先级
- [ ] 添加更多国际市场数据源
- [ ] 策略回测结果对比功能
- [ ] 策略组合优化工具
- [ ] Web API接口设计

### 低优先级
- [ ] 移动端支持
- [ ] 多语言支持
- [ ] 主题切换功能

---

## 🔮 未来计划

### 2025 Q2
- [ ] Phase 3.1: 模拟交易接口
- [ ] 测试覆盖率 >90%
- [ ] 性能优化（大规模回测）

### 2025 Q3
- [ ] Phase 3.2: 风险管理系统
- [ ] 实盘交易Demo
- [ ] Web API Beta版

### 2025 Q4
- [ ] Phase 4.1: Web平台后端
- [ ] Docker部署
- [ ] 策略市场Alpha版

### 2026
- [ ] Phase 4.2: Web前端
- [ ] Phase 5: 高级功能
- [ ] 社区平台

---

## 📊 开发统计

### 代码量
- **总代码行数**: ~15,000 lines
- **核心模块**: ~8,000 lines
- **测试代码**: ~2,000 lines
- **文档**: ~5,000 lines

### 提交记录
- **总提交数**: 150+ commits
- **贡献者**: 2
- **开发周期**: 12个月

### 性能指标
- **单次回测**: <5秒 (1年日线数据)
- **网格搜索**: 10-30秒 (100组参数)
- **自动化流程**: 1-5分钟 (5股票×5策略)

---

## 🤝 贡献指南

欢迎贡献代码、报告Bug、提出建议！

### 如何贡献
1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 开发规范
- 遵循 PEP 8 代码风格
- 添加单元测试（覆盖率>80%）
- 更新相关文档
- 通过CI/CD检查

### 联系方式
- **Issues**: https://github.com/magic-alt/stock/issues
- **Discussions**: https://github.com/magic-alt/stock/discussions
- **Email**: your-email@example.com

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

### 主要依赖
- [Backtrader](https://www.backtrader.com/) - 回测框架
- [AKShare](https://github.com/akfamily/akshare) - 中国金融数据
- [yfinance](https://github.com/ranaroussi/yfinance) - 全球市场数据
- [pandas](https://pandas.pydata.org/) - 数据分析
- [matplotlib](https://matplotlib.org/) - 数据可视化

### 参考资料
- [Quantopian Lectures](https://www.quantopian.com/lectures)
- [QuantConnect](https://www.quantconnect.com/)
- [Zipline](https://github.com/quantopian/zipline)

---

**最后更新**: 2025-10-26  
**维护者**: magic-alt  
**项目状态**: 🟢 Active Development
