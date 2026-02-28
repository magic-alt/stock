# Gateway SDK Setup Guide

This guide covers installation and configuration for the three trading gateway SDKs supported by the platform.

---

## Overview

| Gateway | SDK | Status | Notes |
|---------|-----|--------|-------|
| XtQuant/QMT | xtquant | Production | Bundled with QMT client |
| XTP | xtp-api | Stub mode | Requires broker SDK license |
| Hundsun UFT | hundsun-uft-sdk | Stub mode | Requires broker SDK license |

All gateways support **stub mode** for development and testing when the real SDK is unavailable. Stub mode simulates order lifecycle callbacks with synthetic data.

---

## 1. XtQuant (QMT) Gateway

### Prerequisites
- QMT client installed (provided by your broker, e.g., Guotai Junan, Haitong)
- Python 3.10+ (same version as QMT's embedded Python)

### Installation

XtQuant is bundled with the QMT client. Locate the SDK path:

```
# Typical QMT installation paths
C:\国金QMT交易端\bin.x64\Lib\site-packages\xtquant
C:\海通QMT\bin.x64\Lib\site-packages\xtquant
```

### Configuration

Use `GatewayConfig.sdk_path` to add the SDK to the Python path:

```python
from src.gateways.base_live_gateway import GatewayConfig

config = GatewayConfig(
    account_id="YOUR_ACCOUNT",
    broker="xtquant",
    sdk_path=r"C:\国金QMT交易端\bin.x64\Lib\site-packages",
    # XtQuant-specific
    terminal_type="mini",          # "mini" for miniQMT, "gui" for full QMT
    terminal_path=r"C:\国金QMT交易端\bin.x64\XtMiniQmt.exe",
)
```

### Verification

```python
from src.gateways import create_gateway
from queue import Queue

gw = create_gateway("xtquant", config, Queue())
print(f"Stub mode: {gw._stub_mode}")  # Should be False if SDK loaded
gw.connect()
print(gw.query_account())
gw.disconnect()
```

---

## 2. XTP Gateway

### Prerequisites
- XTP SDK binary (`.pyd` / `.so`) from your broker (e.g., ZTS)
- XTP test environment credentials

### Installation

1. Obtain the XTP Python SDK from your broker:
   - `xtpquoteapi.pyd` (Windows) or `xtpquoteapi.so` (Linux)
   - `xtptraderapi.pyd` / `xtptraderapi.so`

2. Place SDK files in a directory:
   ```
   /path/to/xtp_sdk/
   ├── xtpquoteapi.pyd
   └── xtptraderapi.pyd
   ```

### Configuration

```python
config = GatewayConfig(
    account_id="YOUR_XTP_ACCOUNT",
    broker="xtp",
    password="YOUR_PASSWORD",
    sdk_path=r"/path/to/xtp_sdk",
    sdk_log_path=r"/var/log/xtp",
    # XTP connection settings
    trade_server="tcp://120.27.164.138:6001",
    quote_server="tcp://120.27.164.138:6002",
    client_id=1,
    auto_reconnect=True,
    max_orders_per_second=5.0,
)
```

### Test Environment

XTP provides a public test environment:

| Parameter | Value |
|-----------|-------|
| Trade server | `tcp://120.27.164.138:6001` |
| Quote server | `tcp://120.27.164.138:6002` |
| Account | Apply via broker |
| Client ID | 1-99 (unique per connection) |

---

## 3. Hundsun UFT Gateway

### Prerequisites
- Hundsun UFT SDK (typically `ufx_*.pyd` / `ufx_*.so`)
- UFT test environment credentials from broker

### Installation

1. Obtain the Hundsun UFT Python SDK from your broker
2. Place SDK files:
   ```
   /path/to/uft_sdk/
   ├── ufx_trade.pyd
   └── ufx_config.ini
   ```

### Configuration

```python
config = GatewayConfig(
    account_id="YOUR_UFT_ACCOUNT",
    broker="hundsun",  # or "uft"
    password="YOUR_PASSWORD",
    sdk_path=r"/path/to/uft_sdk",
    sdk_log_path=r"/var/log/uft",
    # UFT connection settings
    td_front="tcp://192.168.1.100:7001",
    md_front="tcp://192.168.1.100:7002",
    auto_reconnect=True,
)
```

---

## SDK Path Configuration

The `GatewayConfig.sdk_path` field automatically adds the directory to `sys.path` at initialization:

```python
# In GatewayConfig.__post_init__:
if self.sdk_path and self.sdk_path not in sys.path:
    sys.path.insert(0, self.sdk_path)
```

You can also set `sdk_log_path` to control where SDK log files are written.

### Environment Variable Alternative

Set the SDK path via environment variable before importing:

```bash
# Windows
set PYTHONPATH=%PYTHONPATH%;C:\path\to\sdk

# Linux
export PYTHONPATH=$PYTHONPATH:/path/to/sdk
```

---

## Stub Mode

When the SDK is not available, gateways automatically enter stub mode:

- `connect()` returns `True` with simulated session
- `send_order()` generates synthetic order IDs and simulates acceptance callbacks
- `query_account()` returns mock account data (cash=1,000,000)
- `query_positions()` returns mock position data

Stub mode is useful for:
- Development and UI testing
- CI/CD pipelines
- Unit and integration testing

### Detecting Stub Mode

```python
from src.gateways.xtp_gateway import XtpGateway, XTP_AVAILABLE

print(f"XTP SDK available: {XTP_AVAILABLE}")

gw = XtpGateway(config, event_queue)
print(f"Running in stub mode: {gw._stub_mode}")
```

---

## Troubleshooting

### SDK Import Fails

**Symptom**: `WARNING: XTP SDK not available: No module named 'xtpquoteapi'`

**Fix**:
1. Verify SDK files exist at the configured path
2. Check Python version matches SDK build (e.g., cp310 for Python 3.10)
3. On Windows, ensure Visual C++ Redistributable is installed
4. Try importing directly: `python -c "import xtpquoteapi"`

### Connection Timeout

**Symptom**: `connect()` hangs or returns `False`

**Fix**:
1. Verify server address and port are correct
2. Check firewall rules allow outbound TCP connections
3. Verify credentials with your broker
4. Check if the test environment is online (business hours only for some brokers)

### Rate Limiting

The gateway enforces `max_orders_per_second` (default: 10). If you see order rejections:

```python
config = GatewayConfig(
    # ...
    max_orders_per_second=5.0,  # Reduce if broker has strict limits
)
```

### Auto-Reconnect

Enable automatic reconnection for production:

```python
config = GatewayConfig(
    # ...
    auto_reconnect=True,
    reconnect_interval=5.0,    # seconds between attempts
    max_reconnect_attempts=10,
    heartbeat_interval=30.0,   # seconds
)
```
