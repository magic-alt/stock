import unittest
from unittest.mock import patch, MagicMock
import pandas as pd


class TestYFinanceDataSource(unittest.TestCase):
    def setUp(self):
        from src.data_sources.yfinance_source import YFinanceDataSource
        self.YFinanceDataSource = YFinanceDataSource

    @patch('src.data_sources.yfinance_source.yf')
    def test_get_stock_history_success(self, mock_yf):
        # 模拟 yf.download 返回 DataFrame
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2022-01-01', '2022-01-02']),
            'Open': [10, 11], 'Close': [11, 12], 'High': [11.5, 12.5], 'Low': [9.5, 10.5], 'Volume': [1000, 1200]
        })
        mock_yf.download.return_value = df.set_index('Date')
        ds = self.YFinanceDataSource()
        ds._ready = True
        out = ds.get_stock_history('600519.SH', '2022-01-01', '2022-01-02')
        self.assertFalse(out.empty)
        self.assertIn('成交额', out.columns)

    @patch('src.data_sources.yfinance_source.yf')
    def test_get_stock_realtime_fast_info(self, mock_yf):
        # 模拟 Ticker.fast_info
        ticker_mock = MagicMock()
        ticker_mock.fast_info = {'last_price': 100.0, 'previous_close': 99.0}
        mock_yf.Ticker.return_value = ticker_mock

        ds = self.YFinanceDataSource()
        ds._ready = True
        rt = ds.get_stock_realtime('600519.SH')
        self.assertIsNotNone(rt)
        self.assertEqual(rt['最新价'], 100.0)


if __name__ == '__main__':
    unittest.main()
