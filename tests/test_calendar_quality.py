import pandas as pd

from src.data_sources.trading_calendar import TradingCalendar, align_frame_to_calendar
from src.data_sources.quality import run_quality_checks


def test_trading_calendar_sessions_weekdays():
    calendar = TradingCalendar()
    sessions = calendar.sessions("2024-01-01", "2024-01-07")
    assert len(sessions) == 5
    assert all(sessions.dayofweek < 5)


def test_align_frame_fill_suspensions():
    dates = pd.to_datetime(["2024-01-01", "2024-01-03"])
    df = pd.DataFrame(
        {
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.8],
            "close": [10.2, 11.2],
            "volume": [100, 120],
        },
        index=dates,
    )
    calendar = TradingCalendar()
    sessions = calendar.sessions("2024-01-01", "2024-01-03")
    aligned = align_frame_to_calendar(df, sessions, fill_suspensions=True)
    assert len(aligned) == 3
    assert aligned.loc[pd.Timestamp("2024-01-02"), "volume"] == 0.0
    assert aligned.loc[pd.Timestamp("2024-01-02"), "close"] == aligned.loc[pd.Timestamp("2024-01-01"), "close"]
    assert aligned.loc[pd.Timestamp("2024-01-02"), "suspended"] == True


def test_quality_report_missing_sessions():
    dates = pd.to_datetime(["2024-01-01", "2024-01-03"])
    df = pd.DataFrame(
        {
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.8],
            "close": [10.2, 11.2],
            "volume": [100, 120],
        },
        index=dates,
    )
    report = run_quality_checks({"AAA": df}, start="2024-01-01", end="2024-01-03")
    assert report["per_symbol"]["AAA"]["missing_sessions"] == 1
