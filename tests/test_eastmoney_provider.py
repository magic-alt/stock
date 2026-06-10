import json

from src.data_sources.providers import EastmoneyProvider, SinaProvider, TencentProvider, normalize_a_share_symbol


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_normalize_a_share_symbol_pads_short_code():
    assert normalize_a_share_symbol("60036") == "600036.SH"
    assert normalize_a_share_symbol("600036SH") == "600036.SH"
    assert normalize_a_share_symbol("sh600036") == "600036.SH"
    assert normalize_a_share_symbol("000001") == "000001.SZ"


def test_eastmoney_provider_parses_web_kline_response(monkeypatch, tmp_path):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "data": {
                    "klines": [
                        "2024-01-02,10.00,10.40,10.80,9.90,1200000,0,0,0,0,0",
                        "2024-01-03,10.40,10.20,10.60,10.10,1100000,0,0,0,0,0",
                    ]
                }
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = EastmoneyProvider(cache_dir=str(tmp_path))
    data = provider.load_stock_daily(["60036"], "2024-01-01", "2024-01-31")

    assert "600036.SH" in data
    assert "secid=1.600036" in captured["url"]
    assert captured["timeout"] == 10
    frame = data["600036.SH"]
    assert {"open", "high", "low", "close", "volume"}.issubset(frame.columns)
    assert frame.iloc[0]["open"] == 10.0
    assert frame.iloc[0]["close"] == 10.4


def test_sina_provider_parses_web_kline_response(monkeypatch, tmp_path):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return _FakeResponse(
            [
                {"day": "2024-01-02", "open": "10.00", "high": "10.80", "low": "9.90", "close": "10.40", "volume": "1200000"},
                {"day": "2024-01-03", "open": "10.40", "high": "10.60", "low": "10.10", "close": "10.20", "volume": "1100000"},
            ]
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = SinaProvider(cache_dir=str(tmp_path))
    data = provider.load_stock_daily(["600036SH"], "2024-01-01", "2024-01-31")

    assert "600036.SH" in data
    assert "symbol=sh600036" in captured["url"]
    assert data["600036.SH"].iloc[0]["close"] == 10.4


def test_tencent_provider_parses_web_kline_response(monkeypatch, tmp_path):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return _FakeResponse(
            {
                "data": {
                    "sh600036": {
                        "qfqday": [
                            ["2024-01-02", "10.00", "10.40", "10.80", "9.90", "1200000"],
                            ["2024-01-03", "10.40", "10.20", "10.60", "10.10", "1100000"],
                        ]
                    }
                }
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = TencentProvider(cache_dir=str(tmp_path))
    data = provider.load_stock_daily(["600036.SH"], "2024-01-01", "2024-01-31")

    assert "600036.SH" in data
    assert "sh600036" in captured["url"]
    assert data["600036.SH"].iloc[0]["high"] == 10.8
