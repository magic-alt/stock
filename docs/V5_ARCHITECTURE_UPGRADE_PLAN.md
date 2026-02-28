# V5.0 架构升级计划 — 全方位对标评估与功能升级路线

**日期**: 2026-02-28
**当前版本**: V5.0（V5.0-A 实施中）
**目标版本**: V5.0-GA
**代码规模**: 42,000+ 行 Python + Vue3 前端（101 个 .py 模块 + Vue3 SPA）
**测试规模**: 59 个测试文件，782+ 测试用例

### 实施进度

| 阶段 | 状态 | 通过测试 | 说明 |
|------|------|----------|------|
| **V5.0-A** 现代 Web 前端与可视化 | ✅ 完成 | 782 passed | 交互式报告生成器 + Strategy API v2 + Vue3 SPA |
| **V5.0-B** 高性能回测引擎 | 🔲 待实施 | - | DuckDB + 多频率 + 向量化 + 流式行情 |
| **V5.0-C** 安全加固与合规升级 | 🔲 待实施 | - | FastAPI + TLS + OWASP + SBOM |

---

## 第一部分：竞品对标分析

### 1.1 开源平台对标

| 维度 | 本系统 (V4.0) | Backtrader | Zipline | vnpy | LEAN (QuantConnect) | Rqalpha | QLib |
|------|---------------|------------|---------|------|---------------------|---------|------|
| **架构模式** | 事件驱动 + DAG编排 | 事件驱动 (Cerebro) | 事件+向量化混合 | 事件驱动 + 插件 | 事件驱动 (C#) | 事件驱动 | 研究框架 (无交易) |
| **语言** | Python | Python | Python/Cython | Python | C#/Python | Python | Python |
| **策略数量** | 41 个内置 | 0 (纯框架) | 0 (纯框架) | 30+ 模板 | 0 (纯框架) | 0 (纯框架) | 0 (模型为主) |
| **实盘网关** | 3 (XtQuant/XTP/UFT) | 1 (IB) | 0 | 20+ (CTP/Mini/XTP等) | 10+ (IB/OANDA等) | 0 | 0 |
| **回测引擎** | 日线+向量化+网格 | Bar/Tick 级 | Bar 级+Pipeline | Tick+Bar 级 | Tick 级多资产 | Bar 级 | Alpha 研究 |
| **数据源** | 4 (AKShare/YF/TuShare/QLib) | 自定义 Feed | Quandl/Bundle | 交易所直连 | 多市场Bundle | 官方数据包 | QLib数据 |
| **风控** | V2 (订单/仓位/回撤/止损) | 无内置 | 无内置 | 基础 | 基础 | 无内置 | 无 |
| **审计/合规** | 哈希链+HMAC签名+归档 | 无 | 无 | 无 | 无 | 无 | 无 |
| **多账户** | RBAC+AccountManager | 无 | 无 | 有 | 有 (云端) | 无 | 无 |
| **分布式** | Ray/Dask/ProcessPool | 无 | 无 | 无 | 云原生 | 无 | 分布式训练 |
| **Web UI** | 单页交易控制台 | 无 | 无 | Qt GUI | 云IDE | 无 | 无 |
| **ML/AI** | MLOps全栈(QLib/FinRL) | 无 | 无 | 无 | 部分 | 无 | 核心能力 |
| **灾备** | 主备切换+DR演练 | 无 | 无 | 无 | 云端 | 无 | 无 |
| **API** | REST+WS+RBAC | 无 | 无 | RPC | REST/WS | 无 | 无 |

### 1.2 商业平台对标

| 维度 | 本系统 (V4.0) | 聚宽 JoinQuant | 米筐 RiceQuant | 掘金 Myquant | Wind 万得 | 通达信 |
|------|---------------|----------------|----------------|--------------|-----------|--------|
| **部署模式** | 本地私有部署 | SaaS 云端 | SaaS 云端 | 本地+云端 | 终端+API | 终端 |
| **策略开发** | Python API | 在线 IDE | 在线 IDE | 本地 IDE+SDK | 公式系统 | 公式系统 |
| **数据覆盖** | A 股日线 | 全品种分钟级 | 全品种分钟级 | 全品种Tick级 | 全品种Tick+基本面 | 全品种分钟级 |
| **实时行情** | AKShare HTTP轮询 | 推送流 | 推送流 | 推送流 | 推送流+Level2 | 推送流+Level2 |
| **回测精度** | 日线+滑点模型 | 分钟级 | 分钟级 | Tick级 | 分钟级 | 分钟级 |
| **策略市场** | 无 | 有 | 有 | 无 | 无 | 有 (指标) |
| **社区/论坛** | 无 | 活跃社区 | 活跃社区 | 中等 | 机构用户 | 大量用户 |
| **多因子框架** | 15技术+7基本面 | 完整因子库 | 完整因子库 | 完整因子库 | 完整因子库 | 基础 |
| **组合管理** | PortfolioManager | 有 | 有 | 有 | 专业级 | 无 |
| **报表导出** | Markdown/JSON/PNG | PDF/Excel | PDF/Excel | PDF/Excel | Excel/PDF | 无 |
| **移动端** | 无 | 微信小程序 | 无 | 无 | APP | APP |
| **合规审计** | 完整 | 基础 | 基础 | 基础 | 专业级 | 无 |
| **价格** | 免费 (MIT) | 免费+付费 | 免费+付费 | 付费 | 高价终端 | 付费 |

### 1.3 核心竞争力总结

**本系统优势**:
1. **合规审计体系** - 超越所有开源方案，接近机构级（哈希链、HMAC签名、归档保留、DR演练）
2. **MLOps 集成** - QLib/FinRL 全栈适配，超越大部分竞品
3. **多账户 RBAC** - 开源方案中少有的完整 RBAC + 账户隔离
4. **A 股特化** - T+1/涨跌停/整手/手续费完整建模
5. **灾备能力** - FailoverManager + DrillRunner，开源方案中独有
6. **私有部署** - 不依赖云端服务，数据完全自主可控

**本系统劣势**:
1. **数据时间粒度** - 仅支持日线级别，缺少分钟/Tick级回测
2. **行情实时性** - HTTP轮询而非推送流，延迟大
3. **Web UI 成熟度** - 单页原生JS，无现代前端框架
4. **策略开发体验** - 无在线IDE、无策略调试器、无可视化编排
5. **数据覆盖** - 仅A股日线，缺少期货/期权/基金/债券
6. **社区生态** - 无策略市场、无社区论坛、无教程体系
7. **性能天花板** - 纯Python实现，缺少C/Rust加速层
8. **网关可用性** - 2/3网关仍为stub模式，依赖SDK对接

---

## 第二部分：六维深度评估

### 2.1 安全性评估 (Security) — 评分: 72/100

| 子项 | 现状 | 评分 | 差距 |
|------|------|------|------|
| 认证鉴权 | Bearer Token + RBAC 5角色 | 8/10 | 缺少 OAuth2/OIDC、JWT刷新令牌、MFA |
| 授权控制 | 9权限 + tenant/account隔离 | 8/10 | 缺少细粒度资源级ACL、动态权限策略 |
| 数据加密 | 无传输加密、无静态加密 | 3/10 | 缺少 TLS、数据库加密、配置加密 |
| 密钥管理 | 环境变量 + config.yaml | 4/10 | 缺少 Vault/KMS 集成、密钥轮换 |
| 输入验证 | RequestValidator JSON Schema | 7/10 | 缺少 SQL注入/XSS 全链路防护 |
| 审计追踪 | 哈希链+HMAC+归档+保留策略 | 9/10 | 缺少不可篡改存储（区块链/WORM） |
| 网络安全 | HTTPServer 无TLS | 3/10 | 缺少 HTTPS、CORS、CSP、HSTS |
| 速率限制 | 令牌桶 RateLimiter | 7/10 | 缺少分布式限流、IP黑名单、DDoS防护 |
| 会话管理 | 无状态 Token | 6/10 | 缺少会话过期、强制登出、并发控制 |
| 依赖安全 | 无扫描 | 2/10 | 缺少 Dependabot/Snyk、SBOM |

**关键安全风险**:
- `api_server.py` 使用 `http.server.ThreadingHTTPServer`，无 TLS 支持
- 配置文件中 API Token 明文存储
- 无 CORS 策略，Web 前端面临 CSRF 风险
- 无依赖漏洞扫描流程

### 2.2 可用性评估 (Usability) — 评分: 58/100

| 子项 | 现状 | 评分 | 差距 |
|------|------|------|------|
| 策略开发体验 | Python API + BaseStrategy | 7/10 | 无IDE支持、无实时调试、无自动补全提示 |
| 安装部署 | pip install + config.yaml | 6/10 | 无Docker镜像、无一键部署、无配置向导 |
| 文档体系 | 10+ 文档文件 | 7/10 | 缺少交互式教程、视频教程、Cookbook |
| 错误提示 | 统一异常体系+结构化日志 | 8/10 | 缺少用户友好错误消息、修复建议 |
| 数据管理 | DataPortal + 自动缓存 | 6/10 | 缺少数据浏览器、数据导入向导 |
| 报告导出 | Markdown/JSON/PNG | 5/10 | 缺少 PDF/Excel/交互式HTML报告 |
| CLI 体验 | run/grid/auto/combo/list | 6/10 | 缺少自动补全、交互模式、进度条 |
| API 文档 | API_REFERENCE.md | 5/10 | 缺少 OpenAPI/Swagger、Postman集合 |
| 多语言 | 中英混合 | 4/10 | 缺少完整国际化(i18n)方案 |
| 新手引导 | quick_start 示例 | 5/10 | 缺少 Wizard、Playground、Notebook模板 |

**关键可用性问题**:
- 策略开发无实时反馈循环（编写→运行→查看需手动流程）
- 回测结果查看需打开本地文件，无统一仪表板
- 无 Docker 容器化支持，环境配置依赖手动操作
- 参数调优无可视化界面

### 2.3 可扩展性评估 (Extensibility) — 评分: 73/100

| 子项 | 现状 | 评分 | 差距 |
|------|------|------|------|
| 策略插件 | BaseStrategy + StrategyRegistry | 8/10 | 缺少版本化策略包、热加载 |
| 数据源插件 | DataProvider 协议 | 7/10 | 缺少 Provider SDK、自动发现 |
| 网关插件 | BaseLiveGateway 协议 | 8/10 | 待更多网关实现 |
| 指标扩展 | technical.py 88行 | 5/10 | 缺少自定义指标注册、TA-Lib集成 |
| 中间件链 | APIRouter + Middleware | 7/10 | 缺少插件市场、第三方中间件生态 |
| 因子框架 | factor_engine + pipeline | 7/10 | 缺少自定义因子编写向导 |
| 存储后端 | SQLite + Parquet + JSON | 6/10 | 缺少 PostgreSQL/ClickHouse/Redis 原生支持 |
| 消息系统 | EventEngine 进程内 | 5/10 | 缺少跨进程消息（Kafka/RabbitMQ/ZMQ） |
| Webhook/回调 | 告警外发(邮件/微信/钉钉) | 7/10 | 缺少通用 Webhook 框架 |
| SDK/客户端 | 无 | 2/10 | 缺少 Python/JS/Go 客户端库 |

**关键扩展性问题**:
- EventEngine 仅限进程内，无法跨节点传播事件
- 存储层硬编码 SQLite，缺少抽象层（Repository Pattern）
- 无插件打包/发布/版本管理机制
- 策略无法热加载或动态切换

### 2.4 性能评估 (Performance) — 评分: 65/100

| 子项 | 现状 | 评分 | 差距 |
|------|------|------|------|
| 回测吞吐 | 日线级 <5s/年 | 6/10 | 分钟级/Tick级回测无法支持 |
| 数据加载 | SQLite + TTLCache | 6/10 | 缺少列式存储查询优化、内存映射 |
| 并行计算 | ProcessPool + ThreadPool | 6/10 | 缺少 GPU加速、SIMD优化 |
| 分布式 | Ray/Dask适配器 | 7/10 | 适配器未经大规模验证 |
| 内存管理 | MemoryManager基础优化 | 5/10 | 缺少零拷贝、共享内存、内存池 |
| 网络延迟 | HTTP轮询 5s间隔 | 3/10 | 缺少低延迟推送、ZMQ/gRPC |
| 数据库性能 | SQLite单文件 | 4/10 | 缺少连接池、读写分离、分片 |
| 缓存策略 | L1内存+L2 SQLite | 7/10 | 缺少分布式缓存（Redis Cluster） |
| 向量化计算 | 部分Numba+Numpy | 6/10 | 缺少Polars/Arrow替代Pandas |
| 基准测试 | benchmark_platform.py | 7/10 | 缺少持续性能追踪大盘(Dashboard) |

**关键性能问题**:
- Pandas DataFrame 是主要性能瓶颈，大数据集内存占用高
- SQLite 单文件数据库在并发写入时锁竞争
- 回测引擎逐日迭代，未利用向量化批处理
- HTTP API 使用 ThreadingHTTPServer，并发能力有限

### 2.5 使用性评估 (Developer Experience) — 评分: 62/100

| 子项 | 现状 | 评分 | 差距 |
|------|------|------|------|
| 项目结构 | 清晰分层 | 8/10 | 部分模块职责重叠 |
| 类型安全 | 部分 dataclass + type hints | 6/10 | 缺少完整 mypy strict 通过 |
| API 一致性 | 内部API风格不统一 | 5/10 | 缺少统一返回值/错误/命名规范 |
| 调试支持 | structlog + error_handler | 6/10 | 缺少 debug模式、断点回测 |
| 测试辅助 | pytest + fixtures | 7/10 | 缺少 test factories、snapshot testing |
| 代码生成 | 无 | 2/10 | 缺少策略/因子脚手架工具 |
| 版本兼容 | 无 | 3/10 | 缺少 API 版本弃用策略、迁移工具 |
| 配置验证 | Pydantic schema | 7/10 | 缺少配置 diff、配置迁移 |
| 依赖管理 | requirements.txt | 5/10 | 缺少 poetry/pdm、锁文件、可选依赖组 |
| CI/CD | GitHub Actions | 7/10 | 缺少自动发布、Docker构建、Helm Chart |

### 2.6 UI/交互评估 (UI/UX) — 评分: 42/100

| 子项 | 现状 | 评分 | 差距 |
|------|------|------|------|
| Web Dashboard | 单页HTML+原生JS | 4/10 | 缺少现代SPA框架、组件化、响应式 |
| 桌面GUI | Tkinter backtest_gui | 4/10 | 缺少现代UI框架（Electron/Tauri） |
| 图表可视化 | ECharts K线+Matplotlib | 6/10 | 缺少交互式Portfolio分析、实时图表 |
| 策略编辑器 | 无 | 1/10 | 缺少在线代码编辑器、语法高亮 |
| 仪表板 | 无 | 1/10 | 缺少系统监控大盘、交易大盘 |
| 回测报告 | Markdown + 静态PNG | 4/10 | 缺少交互式HTML报告 |
| 工作流编排 | API调用 | 3/10 | 缺少可视化DAG编辑器 |
| 移动端 | 无 | 0/10 | 缺少响应式布局、PWA |
| 通知中心 | 告警外发 | 5/10 | 缺少Web内通知、消息中心 |
| 主题/风格 | 暗色CSS主题 | 5/10 | 缺少浅色主题切换、自定义主题 |

**关键UI问题**:
- Web前端使用原生JS(ES5语法)，无模块化、无组件复用
- 无统一的数据可视化仪表板
- Tkinter GUI 过时，不支持现代UI交互模式
- 无策略回测结果的交互式浏览

---

## 第三部分：V5.0 综合评分与优先级

### 3.1 六维雷达图评分

```
        安全性 (72)
          │
    UI (42) ────── 可用性 (58)
          │
  使用性 (62) ──── 可扩展性 (73)
          │
      性能 (65)

综合评分: 62/100
```

### 3.2 V5.0 升级优先级矩阵

| 优先级 | 目标领域 | 影响范围 | V5.0 目标评分 |
|--------|----------|----------|---------------|
| **P0** | UI/交互 (42→75) | 用户获取、首次体验 | 75/100 |
| **P1** | 性能 (65→85) | 回测能力天花板 | 85/100 |
| **P2** | 安全性 (72→90) | 生产部署合规 | 90/100 |
| **P3** | 可用性 (58→80) | 开发者体验 | 80/100 |
| **P4** | 可扩展性 (73→85) | 生态建设 | 85/100 |
| **P5** | 使用性 (62→80) | 内部工程效率 | 80/100 |

---

## 第四部分：V5.0 架构升级计划

### 目标架构 (V5.0)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Presentation Layer (V5.0)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Vue3 SPA │  │ Strategy │  │ Terminal │  │ Mobile   │           │
│  │ Dashboard│  │   IDE    │  │  CLI v2  │  │  PWA     │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
├─────────────────────────────────────────────────────────────────────┤
│                     Gateway Layer (V5.0)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ FastAPI  │  │ gRPC     │  │ WebSocket│  │ GraphQL  │           │
│  │ REST v2  │  │ Internal │  │ Realtime │  │ Query    │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
├─────────────────────────────────────────────────────────────────────┤
│                     Service Layer (V5.0)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Backtest │  │ Trading  │  │ Data     │  │ MLOps    │           │
│  │ Service  │  │ Service  │  │ Service  │  │ Service  │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
├─────────────────────────────────────────────────────────────────────┤
│                     Domain Layer (Enhanced)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │Strategy  │  │Risk/OMS  │  │Portfolio │  │ Factor   │           │
│  │  Engine  │  │  Engine  │  │  Engine  │  │ Engine   │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
├─────────────────────────────────────────────────────────────────────┤
│                     Infrastructure Layer (V5.0)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │TimeSeries│  │ Message  │  │ Cache    │  │ Object   │           │
│  │  DB      │  │   Bus    │  │ Cluster  │  │ Storage  │           │
│  │(DuckDB)  │  │  (ZMQ)   │  │ (Redis)  │  │(Parquet) │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第五部分：功能升级计划（详细模块拆解）

### V5.0-A：现代 Web 前端与可视化平台 (UI/交互 42→75)

**目标**: 使用 Vue3 + TypeScript 重构 Web 前端为模块化 SPA，提供策略开发 IDE、回测仪表板、实时交易监控。

#### A-1：Vue3 SPA 基础框架

**新建目录**: `frontend/`
```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/index.ts
│   ├── stores/              # Pinia 状态管理
│   │   ├── auth.ts
│   │   ├── trading.ts
│   │   └── backtest.ts
│   ├── api/                 # API 客户端
│   │   ├── client.ts        # Axios + 拦截器
│   │   └── types.ts         # TypeScript 类型定义
│   ├── components/          # 通用组件
│   │   ├── Layout/
│   │   ├── Charts/
│   │   └── Common/
│   ├── views/               # 页面视图
│   │   ├── Dashboard.vue
│   │   ├── Backtest.vue
│   │   ├── Trading.vue
│   │   ├── Strategy.vue
│   │   ├── Data.vue
│   │   ├── Monitor.vue
│   │   └── Settings.vue
│   └── utils/
├── public/
└── tests/
```

**技术选型**:
- 框架: Vue 3 + Composition API + TypeScript
- 构建: Vite
- 状态管理: Pinia
- UI组件库: Element Plus 或 Naive UI
- 图表: ECharts 5 + vue-echarts
- HTTP: Axios
- 路由: Vue Router 4

**关键页面**:

| 页面 | 功能 | 对标 |
|------|------|------|
| Dashboard | 系统概览、账户摘要、实时P&L、告警 | QuantConnect Overview |
| Backtest | 策略选择、参数配置、运行回测、查看报告 | JoinQuant 回测页 |
| Trading | 实盘/模拟交易控制台、订单管理、持仓 | vnpy VnTrader |
| Strategy | 策略列表、在线编辑器、参数模板 | RiceQuant 策略编辑 |
| Data | 数据浏览器、数据源管理、数据质量 | Wind 终端数据浏览 |
| Monitor | 系统指标、Trace查看、告警管理 | Grafana Dashboard |
| Settings | 用户/账户/权限/配置/密钥管理 | 通用后台管理 |

#### A-2：交互式回测报告

**文件修改**: `src/backtest/report_generator.py`（新建 ~300行）

- 生成交互式 HTML 报告（自包含单文件，无需服务器）
- 包含: 资金曲线、回撤图、交易记录表、绩效指标仪表板
- 对标 Backtrader Analyzers + QuantStats 报告
- 技术: Jinja2 模板 + 内联 ECharts

**核心组件**:
```python
class InteractiveReportGenerator:
    def generate(self, backtest_result) -> str:  # 返回 HTML 字符串
    def save(self, backtest_result, path: str) -> None
    def to_pdf(self, backtest_result, path: str) -> None  # WeasyPrint
```

#### A-3：策略在线编辑器

**前端组件**: `frontend/src/views/StrategyEditor.vue`

- 集成 Monaco Editor（VS Code 内核）
- Python 语法高亮 + 自动补全（基于策略API Schema）
- 实时语法检查（通过 API 调用后端 AST 解析）
- 一键运行回测 + 结果预览
- 策略模板库（从内置41个策略生成模板）

**后端API**: `src/platform/api/strategy_api.py`（新建 ~200行）
```
POST /api/v2/strategies/validate    # 语法检查
POST /api/v2/strategies/run         # 运行回测
GET  /api/v2/strategies/templates   # 策略模板列表
POST /api/v2/strategies/save        # 保存策略
```

#### A-4：实时交易监控仪表板

**前端组件**: `frontend/src/views/TradingDashboard.vue`

- WebSocket 实时推送（账户、持仓、订单、行情）
- 实时 P&L 曲线（秒级更新）
- 订单流可视化（时间线 + 状态流转图）
- 风控指标仪表盘（VaR、回撤、集中度实时计算）
- 一键紧急平仓按钮

---

### V5.0-B：高性能回测引擎 (性能 65→85)

**目标**: 支持分钟级/Tick级回测，引入 DuckDB 时序存储，实现向量化批处理，大幅提升回测吞吐。

#### B-1：多时间粒度回测引擎

**文件修改**: `src/backtest/engine.py`（扩展 ~400行）

**新增能力**:
- `BarFrequency` 枚举: `DAILY`, `MINUTE_1`, `MINUTE_5`, `MINUTE_15`, `MINUTE_30`, `MINUTE_60`, `TICK`
- `BacktestEngine.run()` 支持 `frequency` 参数
- 分钟级数据切片 + 日内Bar聚合
- Tick级回测: 基于 OrderBook 的逐笔撮合
- 多频率混合回测: 日线信号 + 分钟执行

**关键设计**:
```python
class MultiFreqBacktestEngine:
    def run(self, config: BacktestConfig) -> BacktestResult:
        """
        config.frequency = BarFrequency.MINUTE_5
        config.signal_frequency = BarFrequency.DAILY  # 信号产生频率
        config.execution_frequency = BarFrequency.MINUTE_1  # 执行频率
        """
```

**对标**: LEAN 的 Resolution 系统、vnpy 的 BarGenerator

#### B-2：DuckDB 时序存储引擎

**文件新建**: `src/data_sources/duckdb_store.py`（~300行）

**选型理由**: DuckDB vs ClickHouse vs TimescaleDB
- DuckDB: 嵌入式、零配置、列式存储、SQL兼容、单文件部署
- 适合本系统定位（私有部署、单机为主）
- OLAP查询性能远超SQLite（10-100x）

**核心API**:
```python
class DuckDBTimeSeriesStore:
    def __init__(self, db_path: str): ...
    def ingest(self, symbol: str, df: pd.DataFrame, freq: str): ...
    def query(self, symbol: str, start: str, end: str, freq: str) -> pd.DataFrame: ...
    def query_multiple(self, symbols: List[str], ...) -> Dict[str, pd.DataFrame]: ...
    def aggregate(self, symbol: str, from_freq: str, to_freq: str) -> pd.DataFrame: ...
    def vacuum(self): ...  # 压缩优化
```

**数据分区策略**:
- 按品种 + 年份分区
- 支持 Parquet 文件批量导入
- 自动数据压缩（Snappy/ZSTD）

#### B-3：向量化计算层

**文件新建**: `src/core/vectorized.py`（~250行）

- 使用 Polars 替代 Pandas 关键路径（回测引擎内部）
- Numba JIT 加速绩效指标计算
- NumPy 向量化信号生成
- 共享内存 (multiprocessing.shared_memory) 大数据集传递

**性能目标**:
| 场景 | V4.0 | V5.0 目标 | 提升 |
|------|------|-----------|------|
| 日线回测 1年1股 | <5s | <0.5s | 10x |
| 日线网格100组 | 10-30s | <3s | 10x |
| 分钟线回测 1年1股 | 不支持 | <10s | N/A |
| 分钟线网格100组 | 不支持 | <60s | N/A |
| 多股票批量 (50只×1年) | 60-90s | <10s | 6-9x |

#### B-4：流式行情引擎

**文件修改**: `src/core/realtime_data.py`（重构 ~400行）

- 替换 HTTP 轮询为 WebSocket/ZMQ 推送
- 实现 BarBuilder: Tick→分钟→小时 自动聚合
- 行情快照缓存 + 增量更新
- 支持 Level2 深度行情（OrderBook 快照）
- 对接数据源: 新浪 WebSocket、东方财富 WebSocket、CTP行情

**对标**: vnpy 的 GatewayEvent + BarGenerator

---

### V5.0-C：安全加固与合规升级 (安全性 72→90)

**目标**: 实现企业级安全基线，支持 TLS、密钥管理、完整审计链、合规导出。

#### C-1：API 框架升级 (HTTPServer → FastAPI)

**文件修改**: `src/platform/api_server.py`（重写 ~600行）

**选型**: FastAPI
- 原生 async/await 支持
- 自动 OpenAPI/Swagger 文档
- Pydantic 请求/响应验证
- 原生 WebSocket 支持
- OAuth2 内置支持
- 性能远超 ThreadingHTTPServer

**迁移策略**:
- 保持所有 `/api/v1/*` 路由兼容
- 新增 `/api/v2/*` 路由（FastAPI原生）
- 旧 `api_server.py` 保留为 legacy（6个月弃用期）

**新增能力**:
```python
# FastAPI 路由示例
@router.post("/api/v2/backtest/run", response_model=BacktestResponse)
async def run_backtest(
    config: BacktestConfig,
    subject: Subject = Depends(get_current_subject),
):
    auth.require(Permission.BACKTEST_RUN, subject, ResourceScope(...))
    ...
```

#### C-2：TLS + 密钥管理

**文件新建**: `src/core/security.py`（~200行）

- TLS 证书管理（自签名 + Let's Encrypt）
- 密钥轮换策略（API Token 定期刷新）
- 配置文件加密（Fernet 对称加密）
- 环境变量封装（防止日志泄露）

**文件新建**: `src/core/vault.py`（~150行）

- 抽象密钥存储接口
- 本地文件 Backend（加密文件）
- 可选 HashiCorp Vault 集成
- 可选 AWS KMS / Azure Key Vault

#### C-3：OWASP 安全加固

**文件修改**: `src/platform/api/middleware.py`（扩展 ~100行）

新增中间件:
- `CORSMiddleware` — Cross-Origin 策略
- `CSPMiddleware` — Content Security Policy
- `HSTSMiddleware` — HTTP Strict Transport Security
- `XSSProtectionMiddleware` — X-XSS-Protection / X-Content-Type-Options
- `SQLInjectionGuard` — SQL参数化查询审计

**文件新建**: `src/core/input_sanitizer.py`（~100行）
- 统一输入清洗函数
- Symbol 格式验证（正则白名单）
- 数值范围检查
- 文件路径遍历防护

#### C-4：依赖安全与 SBOM

**文件新建**: `.github/workflows/security.yml`

- Dependabot 依赖更新自动 PR
- Snyk / Safety 安全扫描
- SBOM 生成（CycloneDX 格式）
- 许可证合规检查

**文件新建**: `pyproject.toml`（替代 requirements.txt）
- Poetry/PDM 锁文件
- 可选依赖组: `[ml]`, `[live]`, `[dev]`, `[all]`

---

### V5.0-D：开发者体验升级 (可用性 58→80)

**目标**: 提供流畅的策略开发工作流，完善文档体系，支持 Docker 一键部署。

#### D-1：Docker 容器化

**文件新建**:
```
Dockerfile              # 基础镜像
docker-compose.yml      # 完整栈（API + Frontend + DuckDB + Redis）
docker-compose.dev.yml  # 开发环境
.dockerignore
```

**镜像层级**:
```dockerfile
# 基础镜像: Python 3.12 slim
FROM python:3.12-slim AS base
# 数据层: + DuckDB + Parquet tools
FROM base AS data
# 完整镜像: + ML dependencies (optional)
FROM data AS full
```

**编排**:
```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    volumes: ["./data:/app/data"]
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

#### D-2：CLI v2 (Rich + Click)

**文件新建**: `src/cli/`（~500行）

- 使用 Click + Rich 重写 CLI
- 交互式参数选择（InquirerPy）
- 彩色输出 + 进度条 + 表格
- 自动补全（shell completion）
- Jupyter Notebook 集成

**命令结构**:
```bash
quant backtest run --strategy macd --symbols 600519.SH --start 2024-01-01
quant backtest report --id <backtest_id> --format html
quant strategy list
quant strategy new --template ml_factor
quant data fetch --symbols 600519.SH --start 2024-01-01
quant data browse --symbol 600519.SH
quant trading connect --broker paper
quant trading order buy 600519.SH 100 --price 1800
quant monitor status
quant monitor alerts
```

#### D-3：OpenAPI 文档 + SDK 生成

**自动生成**: FastAPI → OpenAPI 3.0 JSON

**客户端 SDK 生成**:
- Python SDK: `quant-client` 包（openapi-generator）
- TypeScript SDK: 前端自动类型（openapi-typescript）
- Postman 集合自动导出

**文件新建**: `src/platform/api/openapi.py`（~80行）
- OpenAPI Schema 增强（示例值、描述、标签分组）
- Redoc / Swagger UI 双文档端点

#### D-4：Jupyter Notebook 集成

**文件新建**: `src/notebook/`（~200行）

```python
# notebook/magic.py — IPython Magic Commands
%load_ext quant_magic

# 在 Notebook 中直接使用
%quant_backtest --strategy macd --symbols 600519.SH
%quant_plot portfolio  # 交互式图表
%quant_factors correlation  # 因子相关性矩阵
```

**Notebook 模板**:
- `notebooks/01_quick_start.ipynb` — 快速入门
- `notebooks/02_strategy_development.ipynb` — 策略开发
- `notebooks/03_factor_research.ipynb` — 因子研究
- `notebooks/04_ml_pipeline.ipynb` — ML流水线
- `notebooks/05_portfolio_analysis.ipynb` — 组合分析

---

### V5.0-E：可扩展性与生态建设 (可扩展性 73→85)

**目标**: 建立插件系统、支持跨进程消息、数据库抽象、策略热加载。

#### E-1：插件系统

**文件新建**: `src/core/plugin.py`（~200行）

```python
class PluginManager:
    def discover(self, paths: List[str]): ...  # 自动发现插件
    def load(self, plugin_id: str): ...        # 加载插件
    def unload(self, plugin_id: str): ...      # 卸载插件
    def list_plugins(self) -> List[PluginInfo]: ...

class PluginBase:
    """所有插件的基类"""
    name: str
    version: str
    plugin_type: str  # "strategy" | "datasource" | "gateway" | "indicator" | "report"

    def on_load(self): ...
    def on_unload(self): ...
```

**插件类型**:
| 类型 | 接口 | 示例 |
|------|------|------|
| strategy | BaseStrategy | 自定义策略 |
| datasource | DataProvider | Binance数据源 |
| gateway | BaseLiveGateway | 自定义网关 |
| indicator | IndicatorPlugin | 自定义技术指标 |
| report | ReportPlugin | 自定义报告格式 |
| factor | FactorPlugin | 自定义因子 |

**打包格式**: 标准 Python wheel + `quant-plugin.yaml` 元数据

#### E-2：消息总线 (ZMQ)

**文件新建**: `src/core/message_bus.py`（~250行）

- 替代进程内 EventEngine 的跨进程版本
- 使用 ZeroMQ PUB/SUB 模式
- 支持进程内 fallback（无 ZMQ 时降级为 EventEngine）
- 事件序列化: msgpack/protobuf

```python
class MessageBus:
    def __init__(self, mode: str = "inprocess"):  # "inprocess" | "zmq" | "redis"
    def publish(self, topic: str, message: Any): ...
    def subscribe(self, topic: str, handler: Callable): ...
    def unsubscribe(self, topic: str, handler: Callable): ...
```

**使用场景**:
- 回测引擎 → 前端实时进度
- 交易引擎 → 风控引擎（跨进程）
- 行情服务 → 多策略广播

#### E-3：存储抽象层 (Repository Pattern)

**文件新建**: `src/core/repository.py`（~200行）

```python
class Repository(Protocol):
    def get(self, id: str) -> Optional[dict]: ...
    def list(self, filters: dict) -> List[dict]: ...
    def save(self, entity: dict) -> str: ...
    def delete(self, id: str) -> bool: ...

class SQLiteRepository(Repository): ...  # 现有
class DuckDBRepository(Repository): ...  # V5.0 新增
class PostgresRepository(Repository): ...  # V5.0 新增 (可选)
class RedisRepository(Repository): ...    # V5.0 新增 (缓存层)
```

**迁移计划**:
- `db_manager.py` → `SQLiteRepository` 适配
- `data_lake_parquet.py` → `DuckDBRepository` 适配
- `job_queue.py` → Repository 抽象

#### E-4：策略热加载

**文件新建**: `src/core/strategy_loader.py`（~150行）

```python
class StrategyHotLoader:
    def __init__(self, watch_dirs: List[str]): ...
    def load_from_file(self, path: str) -> Type[BaseStrategy]: ...
    def load_from_string(self, code: str) -> Type[BaseStrategy]: ...
    def reload(self, strategy_name: str): ...
    def watch(self, callback: Callable): ...  # 文件变更自动重载
```

- 基于 `importlib.reload` + `ast.parse` 安全检查
- 沙箱执行（限制 import、文件操作、网络访问）
- 版本化策略快照

---

### V5.0-F：工程效率升级 (使用性 62→80)

**目标**: 完善类型系统、统一 API 规范、引入代码生成工具。

#### F-1：完整类型系统

**文件修改**: 全局（渐进式）

- 所有公开 API 添加完整 type hints
- 启用 `mypy --strict` 并逐步修复
- 关键 DTO 迁移到 Pydantic v2 BaseModel
- 添加 `py.typed` 标记文件

**目标**: mypy strict 通过率 > 90%

#### F-2：项目构建现代化

**文件新建/修改**:
- `pyproject.toml` — 替代 setup.py + requirements.txt
- 使用 PDM 或 Poetry 管理依赖
- 可选依赖组:
  ```toml
  [project.optional-dependencies]
  ml = ["torch", "qlib", "finrl"]
  live = ["xtquant"]
  dev = ["pytest", "mypy", "black", "ruff"]
  docs = ["mkdocs", "mkdocs-material"]
  all = ["quant-stock[ml,live,dev,docs]"]
  ```

#### F-3：策略脚手架生成器

**文件新建**: `src/cli/scaffold.py`（~200行）

```bash
# 生成新策略骨架
quant strategy new my_strategy --template trend_following
# 生成:
#   strategies/my_strategy.py (带完整docstring和参数说明)
#   tests/test_my_strategy.py (带测试骨架)
#   notebooks/research_my_strategy.ipynb (研究notebook)

# 生成新因子骨架
quant factor new pe_adjusted --template fundamental

# 生成新数据源骨架
quant datasource new binance --template websocket
```

#### F-4：MkDocs 文档站

**文件新建**: `mkdocs.yml` + `docs/` 重组

- MkDocs Material 主题
- 自动 API 文档（mkdocstrings）
- 搜索功能
- 版本化文档
- 中文/英文双语

**文档结构**:
```
docs/
├── index.md              # 首页
├── getting-started/
│   ├── installation.md
│   ├── quick-start.md
│   └── configuration.md
├── guides/
│   ├── strategy-dev.md
│   ├── factor-research.md
│   ├── backtesting.md
│   ├── live-trading.md
│   └── ml-pipeline.md
├── api/
│   ├── rest-api.md       # 自动生成
│   ├── python-sdk.md
│   └── strategy-api.md
├── architecture/
│   ├── overview.md
│   ├── data-flow.md
│   └── security.md
├── operations/
│   ├── deployment.md
│   ├── monitoring.md
│   └── troubleshooting.md
└── changelog.md
```

---

## 第六部分：实施路线与里程碑

### Phase 1: 基础设施现代化 (V5.0-alpha)

| 步骤 | 模块 | 依赖 | 产出 |
|------|------|------|------|
| 1 | F-2 项目构建 (pyproject.toml) | 无 | 依赖管理现代化 |
| 2 | C-1 FastAPI 迁移 | F-2 | API v2 + OpenAPI |
| 3 | B-2 DuckDB 存储 | F-2 | 时序数据引擎 |
| 4 | D-1 Docker 容器化 | C-1, B-2 | 一键部署 |

### Phase 2: 前端与体验 (V5.0-beta)

| 步骤 | 模块 | 依赖 | 产出 |
|------|------|------|------|
| 5 | A-1 Vue3 SPA 框架 | C-1 | 前端基础 |
| 6 | A-2 交互式报告 | B-2 | HTML报告 |
| 7 | D-2 CLI v2 | F-2 | 现代CLI |
| 8 | D-3 OpenAPI + SDK | C-1 | 客户端SDK |

### Phase 3: 性能突破 (V5.0-rc1)

| 步骤 | 模块 | 依赖 | 产出 |
|------|------|------|------|
| 9 | B-1 多时间粒度引擎 | B-2 | 分钟级回测 |
| 10 | B-3 向量化计算 | B-1 | 10x性能提升 |
| 11 | B-4 流式行情 | E-2 | 实时推送 |
| 12 | E-2 消息总线 | 无 | 跨进程事件 |

### Phase 4: 安全与合规 (V5.0-rc2)

| 步骤 | 模块 | 依赖 | 产出 |
|------|------|------|------|
| 13 | C-2 TLS+密钥管理 | C-1 | 传输加密 |
| 14 | C-3 OWASP加固 | C-1 | 安全中间件 |
| 15 | C-4 依赖安全 | F-2 | SBOM+扫描 |

### Phase 5: 高级功能 (V5.0-GA)

| 步骤 | 模块 | 依赖 | 产出 |
|------|------|------|------|
| 16 | A-3 策略编辑器 | A-1, C-1 | 在线IDE |
| 17 | A-4 交易监控 | A-1, B-4 | 实时仪表板 |
| 18 | E-1 插件系统 | F-1 | 可扩展架构 |
| 19 | E-3 存储抽象 | B-2, E-2 | Repository |
| 20 | E-4 策略热加载 | E-1 | 运行时重载 |

### Phase 6: 文档与生态 (V5.0-GA+)

| 步骤 | 模块 | 依赖 | 产出 |
|------|------|------|------|
| 21 | F-4 MkDocs 文档站 | 全部 | 文档网站 |
| 22 | D-4 Jupyter 集成 | B-2, A-2 | Notebook模板 |
| 23 | F-1 完整类型系统 | 全部 | mypy strict |
| 24 | F-3 脚手架生成器 | E-1 | 代码生成 |

---

## 第七部分：技术决策记录

### 7.1 为什么选择 FastAPI 而不是 Flask/Django

| 因素 | FastAPI | Flask | Django |
|------|---------|-------|--------|
| 性能 | 高 (Starlette/uvicorn) | 中 | 低 |
| 异步支持 | 原生 async/await | 需扩展 | 部分 |
| 类型安全 | Pydantic 原生 | 无 | 部分 |
| OpenAPI | 自动生成 | 需插件 | 需插件 |
| WebSocket | 原生 | 需 Socket.IO | Channels |
| 学习曲线 | 低 | 低 | 高 |
| 适合场景 | API + 实时 | 简单API | 全栈CMS |

**结论**: FastAPI 最契合本系统需求（高性能API + WebSocket + 类型安全）

### 7.2 为什么选择 DuckDB 而不是 ClickHouse/TimescaleDB

| 因素 | DuckDB | ClickHouse | TimescaleDB |
|------|--------|------------|-------------|
| 部署 | 嵌入式(无服务器) | 独立服务 | PostgreSQL扩展 |
| 配置 | 零配置 | 复杂 | 中等 |
| 列式存储 | 是 | 是 | 混合 |
| OLAP性能 | 优秀 | 最佳 | 良好 |
| Python集成 | pip install | 需客户端 | psycopg2 |
| 适合规模 | 单机TB级 | 集群PB级 | 单机TB级 |
| Parquet兼容 | 原生读写 | 需导入 | 无 |
| 内存占用 | 低 | 高 | 中 |

**结论**: DuckDB 最适合本系统定位（私有部署、单机为主、嵌入式优先）

### 7.3 为什么选择 Vue3 而不是 React/Svelte

| 因素 | Vue 3 | React | Svelte |
|------|-------|-------|--------|
| 中文生态 | 最佳 | 良好 | 一般 |
| 组件库 | Element Plus/Naive UI | MUI/Ant Design | 较少 |
| 学习曲线 | 低 | 中 | 低 |
| TypeScript | 良好 | 最佳 | 良好 |
| 状态管理 | Pinia (简洁) | Redux/Zustand | 内置 |
| 性能 | 优秀 | 优秀 | 最佳 |
| 适合场景 | 中型SPA | 大型SPA | 小型应用 |

**结论**: Vue 3 中文生态最好，配合 Element Plus 可快速构建金融级 UI

### 7.4 为什么选择 ZMQ 而不是 Kafka/RabbitMQ

| 因素 | ZeroMQ | Kafka | RabbitMQ |
|------|--------|-------|----------|
| 部署 | 库 (pip install) | 独立集群 | 独立服务 |
| 延迟 | 微秒级 | 毫秒级 | 毫秒级 |
| 持久化 | 无 (可选) | 持久化 | 持久化 |
| 吞吐 | 百万/秒 | 十万/秒 | 万/秒 |
| 模式 | PUB/SUB/REQ/REP | PUB/SUB | Exchange |
| 适合场景 | 低延迟行情 | 日志/事件 | 任务队列 |

**结论**: ZMQ 延迟最低、无外部依赖，最适合实时行情分发。任务队列保留现有 JobQueue。

---

## 第八部分：风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| FastAPI 迁移破坏现有 API | 中 | 高 | 双版本并行运行6个月，完整契约测试 |
| DuckDB 在极端场景不稳定 | 低 | 中 | 保留 SQLite fallback，数据双写 |
| Vue3 前端增加维护复杂度 | 中 | 中 | 组件库降低自研量，保留旧 HTML 控制台 |
| 分钟级数据量存储压力 | 中 | 中 | DuckDB 分区 + Parquet 冷存归档 |
| ML 依赖版本冲突 | 高 | 低 | 可选依赖组隔离，Docker 多阶段构建 |
| 性能回归 | 低 | 高 | 保持现有 benchmark 体系，新增分钟级基准 |

---

## 第九部分：成功指标

### V5.0 GA 发布标准

| 指标 | 目标 | 验证方法 |
|------|------|----------|
| 六维综合评分 | ≥ 80/100 (当前62) | 重新评估 |
| 测试通过率 | 100% (0 failures) | pytest |
| 测试覆盖率 | ≥ 90% | pytest --cov |
| API 响应延迟 P99 | < 100ms | 压测验证 |
| 日线回测吞吐 | ≥ 10x 提升 | benchmark |
| 分钟级回测 | 可用 | 功能测试 |
| Web UI 可用率 | 所有核心页面可访问 | E2E 测试 |
| Docker 部署 | docker compose up 一键启动 | 集成测试 |
| OpenAPI 覆盖率 | 100% API 有文档 | 自动检查 |
| mypy strict | ≥ 90% 通过 | CI 门禁 |
| 安全扫描 | 0 高危漏洞 | Snyk/Safety |

---

## 附录：文件变更预估

### 新增文件 (~35个)
```
frontend/                     # Vue3 SPA（完整前端项目）
src/cli/                      # CLI v2 (Click + Rich)
src/core/security.py          # TLS + 密钥管理
src/core/vault.py             # 密钥存储抽象
src/core/plugin.py            # 插件系统
src/core/message_bus.py       # ZMQ 消息总线
src/core/repository.py        # 存储抽象层
src/core/vectorized.py        # 向量化计算
src/core/input_sanitizer.py   # 输入清洗
src/core/strategy_loader.py   # 策略热加载
src/data_sources/duckdb_store.py  # DuckDB 时序存储
src/backtest/report_generator.py  # 交互式报告
src/platform/api/strategy_api.py  # 策略API
src/platform/api/openapi.py   # OpenAPI增强
src/notebook/                  # Jupyter 集成
Dockerfile
docker-compose.yml
pyproject.toml
mkdocs.yml
notebooks/                     # Notebook 模板
```

### 重写/重构文件 (~8个)
```
src/platform/api_server.py     # → FastAPI
src/core/realtime_data.py      # → 流式行情
src/platform/web/*             # → frontend/ (Vue3)
src/backtest/engine.py         # 扩展多频率
src/data_sources/providers.py  # + DuckDB集成
```

### 扩展文件 (~15个)
```
src/core/monitoring.py         # + 新指标
src/core/auth.py              # + OAuth2
src/platform/api/middleware.py # + OWASP
src/backtest/analysis.py      # + 分钟级指标
src/platform/distributed.py   # + ZMQ后端
全部已有测试文件               # + 新测试
```

### 预估代码量
- 新增 Python: ~5,000-8,000 行
- 新增前端 (Vue3+TS): ~8,000-12,000 行
- 总增量: ~15,000-20,000 行
- V5.0 总代码量预估: ~60,000-65,000 行

---

**文档版本**: 1.0
**编制日期**: 2026-02-28
**适用范围**: Unified Quant Platform V5.0 架构升级
