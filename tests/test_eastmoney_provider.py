import json

from src.data_sources.providers import EastmoneyProvider, normalize_a_share_symbol


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        payload = {
            "data": {
                "klines": [
                    "2024-01-02,10.00,10.40,10.80,9.90,1200000,0,0,0,0,0",
                    "2024-01-03,10.40,10.20,10.60,10.10,1100000,0,0,0,0,0",
                ]
            }
        }
        return json.dumps(payload).encode("utf-8")


def test_normalize_a_share_symbol_pads_short_code():
    assert normalize_a_share_symbol("60036") == "600036.SH"
    assert normalize_a_share_symbol("000001") == "000001.SZ"


def test_eastmoney_provider_parses_web_kline_response(monkeypatch, tmp_path):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _FakeResponse()

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
