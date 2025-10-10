# 🚀 快速参考卡片

## 当前版本
**V2.2.3** (2025-10-10)

---

## 启动命令

### 标准启动
```powershell
conda activate base
cd D:\Project\data
python main.py
```

### 清理缓存启动（推荐）
```powershell
python start_monitor.py
```

---

## 功能菜单

1. **实时监控** - 查看股票/指数实时行情
2. **策略回测** - 测试交易策略效果
3. **查看分组** - 查看股票分组信息
4. **系统说明** - 查看帮助文档

---

## 监控方案

| 方案 | 包含内容 |
|------|---------|
| 默认方案 | AI+芯片+黄金+优质股 |
| AI芯片主题 | 宁德时代、中芯国际等 |
| 黄金主题 | 山东黄金、紫金矿业等 |
| 新能源汽车 | 卧龙电驱等 |
| 优质蓝筹 | 茅台、平安、招行等 |
| 科技综合 | 科技股组合 |

---

## 回测引擎

### 简单回测引擎（快速）
- 双均线交叉
- 三均线策略
- RSI超买超卖
- MACD信号/零轴

### Backtrader引擎（专业）
- 完整回测框架
- 可视化图表
- 专业指标

---

## 常见问题

### Q1: 成交额显示异常？
**A:** 已在V2.2.1修复。如果仍显示错误，请重启终端。

### Q2: 网络错误信息太多？
**A:** 已在V2.2.3完全修复。
- 控制台：只显示1条友好提示
- 详细日志：保存在 `monitor.log` 文件
- 查看日志：`Get-Content monitor.log` (PowerShell)

### Q3: 非交易时间无数据？
**A:** 正常现象。系统会显示下次交易时间和友好提示。

### Q4: 如何应用代码更新？
**A:** 
- **方法1（推荐）**：关闭终端 → 打开新终端 → 重新运行
- **方法2**：运行 `python start_monitor.py`

---

## 数据说明

### 成交额单位
- **输入**：API返回（个股=万元，指数=亿元）
- **内部**：统一转换为"元"
- **显示**：自动选择"万"或"亿"

### 更新频率
- **实时监控**：默认30秒刷新
- **缓存有效期**：5秒（避免频繁请求）
- **错误提示**：60秒显示一次

---

## 项目结构

```
D:\Project\data\
├── main.py                    # 主程序入口
├── start_monitor.py           # 清理缓存启动脚本
├── src/
│   ├── config.py             # 配置文件
│   ├── data_sources/         # 数据源模块
│   ├── strategies/           # 策略模块
│   ├── indicators/           # 技术指标
│   ├── backtest/             # 回测引擎
│   ├── monitors/             # 实时监控
│   └── utils/                # 工具函数
│       ├── formatters.py     # 格式化工具
│       ├── safe_cast.py      # 类型转换
│       └── timebox.py        # 交易时间
├── docs/                     # 文档目录
└── test_*.py                 # 测试脚本
```

---

## 测试验证

### 验证成交额修复
```powershell
python verify_fresh_import.py
```

### 验证错误日志优化
```powershell
python test_error_logging.py
```

### 端到端测试
```powershell
python test_amount_e2e.py
```

### 工具函数测试
```powershell
python test_utils.py
```

---

## 技术支持

### 文档资源
- `README.md` - 项目概览
- `CHANGELOG.md` - 版本历史
- `HOTFIX_AMOUNT_CACHE.md` - 缓存问题解决方案
- `docs/FIX_AMOUNT_UNIT.md` - 成交额修复详解
- `docs/OPTIMIZE_ERROR_LOGGING.md` - 日志优化说明

### 调试技巧
1. 查看日志：设置 `logging.DEBUG` 级别
2. 清理缓存：删除 `src/**/__pycache__`
3. 验证模块：运行 `verify_fresh_import.py`
4. 网络测试：检查 AKShare API 连通性

---

## 版本历史

| 版本 | 日期 | 主要更新 |
|------|------|---------|
| V2.2.3 | 2025-10-10 | 日志系统优化 |
| V2.2.2 | 2025-10-10 | 网络错误日志优化 |
| V2.2.1 | 2025-10-10 | 成交额单位修复 |
| V2.2 | 2025-10-10 | 工具模块重构 |
| V2.1.1 | 2025-10-09 | NaN错误修复 |
| V2.1 | 2025-10-09 | 三大核心修复 |
| V2.0 | - | 初始模块化版本 |

---

**最后更新：** 2025-10-10  
**维护者：** GitHub Copilot + 用户
