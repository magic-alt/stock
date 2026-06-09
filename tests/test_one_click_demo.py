from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_one_click_demo_generates_expected_artifacts(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "examples/one_click_demo.py",
            "--out-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert (tmp_path / "platform_console_demo.json").exists()
    assert (tmp_path / "web_console_echarts.json").exists()
    assert (tmp_path / "demo_report.md").exists()
    assert (tmp_path / "analysis_demo.json").exists()
    assert (tmp_path / "analysis_report.md").exists()

    report = json.loads((tmp_path / "platform_console_demo.json").read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["summary"]["gateway_connected"] is True

    echarts = json.loads((tmp_path / "web_console_echarts.json").read_text(encoding="utf-8"))
    assert "600519.SH" in echarts["series"]
    assert "000001.SZ" in echarts["series"]

    analysis = json.loads((tmp_path / "analysis_demo.json").read_text(encoding="utf-8"))
    assert analysis["symbol"] == "600519.SH"
    assert analysis["data_quality"]["source"] == "sample"
