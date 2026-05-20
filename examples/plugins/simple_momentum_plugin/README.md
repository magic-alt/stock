# Simple Momentum Plugin

This example shows the minimal V6 SDK shape for a strategy plugin. It can be
tested without installing the package:

```bash
python -m src.cli.main plugin test simple_momentum_plugin:MANIFEST --path examples/plugins/simple_momentum_plugin
```

When packaged, the plugin exposes the strategy through the
`quant_platform.strategy` entry-point group.
