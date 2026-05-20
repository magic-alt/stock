# Live Gateway Stub Mode

The platform includes live gateway adapters for XtQuant/QMT, XTP, Hundsun UFT, EastMoney, and paper trading. When a broker SDK is unavailable, adapters use stub or paper paths so CI and local development can still exercise the lifecycle safely.

## What stub mode is for

- Development without broker SDK binaries
- CI smoke tests
- Documentation and demo workflows
- Integration planning before real account credentials are available

Stub mode is not a substitute for broker certification, exchange permissions, or production risk approval.

## References

- [Gateway SDK setup](../GATEWAY_SDK_SETUP.md)
- [Broker account guide](../BROKER_ACCOUNT_GUIDE.md)
- [Live trading API](../LIVE_TRADING_API.md)