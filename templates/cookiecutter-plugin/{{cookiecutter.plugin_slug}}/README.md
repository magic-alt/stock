# {{ cookiecutter.project_name }}

V6 SDK plugin scaffold for `quant-stock`.

Test locally before packaging:

```bash
python -m src.cli.main plugin test {{ cookiecutter.package_name }}:MANIFEST --path .
```

After installing the package, the host discovers it through the
`quant_platform.{{ cookiecutter.plugin_kind }}` entry-point group.
