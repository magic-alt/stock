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


def test_cn_calendar_skips_exchange_holidays() -> None:
    calendar = TradingCalendar.for_source("akshare")
    sessions = calendar.sessions("2024-02-05", "2024-02-20")
    assert [str(ts.date()) for ts in sessions] == [
        "2024-02-05",
        "2024-02-06",
        "2024-02-07",
        "2024-02-08",
        "2024-02-19",
        "2024-02-20",
    ]


def test_quality_report_ignores_cn_holiday_gap_when_exchange_calendar_is_used() -> None:
    calendar = TradingCalendar.for_source("akshare")
    dates = pd.to_datetime(["2024-02-05", "2024-02-06", "2024-02-07", "2024-02-08", "2024-02-19", "2024-02-20"])
    df = pd.DataFrame(
        {
            "open": [10.0, 10.2, 10.4, 10.1, 10.5, 10.7],
            "high": [10.3, 10.5, 10.6, 10.4, 10.8, 10.9],
            "low": [9.8, 10.0, 10.2, 9.9, 10.3, 10.5],
            "close": [10.1, 10.3, 10.5, 10.2, 10.7, 10.8],
            "volume": [100, 105, 98, 102, 110, 115],
        },
        index=dates,
    )

    report = run_quality_checks(
        {"AAA": df},
        start="2024-02-05",
        end="2024-02-20",
        calendar=calendar,
    )

    assert report["per_symbol"]["AAA"]["missing_sessions"] == 0
    assert report["per_symbol"]["AAA"]["missing_ratio"] == 0.0
