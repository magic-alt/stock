# Platform Console Demo

本演示用于验证 Web 控制台背后的完整 paper-trading 功能链路，不依赖真实券商 SDK，也不会改动当前运行中的实盘网关连接。

## 演示内容

`scripts/demo_platform_console.py` 会创建隔离的 Paper 网关并执行：

1. 连接 Paper 网关。
2. 提交买入限价单。
3. 推送模拟行情触发成交。
4. 提交卖出限价单。
5. 撤销卖出限价单。
6. 推送盯市价格。
7. 收集账户、持仓、订单、成交与监控摘要。

## 命令行演示

```bash
python scripts/demo_platform_console.py --out report/platform_console_demo.json
```

可选参数：

- `--symbol`：演示标的，默认 `600519.SH`。
- `--quantity`：演示数量，默认 `100`。
- `--entry-price`：买入限价，默认 `100`。
- `--entry-fill-price`：触发成交的模拟行情价格，默认 `99.5`。
- `--mark-price`：最终盯市价格，默认 `101.2`。
- `--exit-limit-price`：待撤销卖出限价，默认 `120`。
- `--out`：JSON 报告输出路径。

## API 演示

FastAPI v2：

```bash
curl "http://127.0.0.1:8080/api/v2/demo/paper-trading?symbol=600519.SH&quantity=100"
```

兼容 API v1：

```bash
curl -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:8080/api/v1/demo/paper-trading?symbol=600519.SH&quantity=100"
```

## Web 展示

Vite 前端 Dashboard 提供 `Run Paper Demo` 操作，会调用 `/api/v2/demo/paper-trading` 并展示步骤、成交、撤单、持仓和监控结果。
