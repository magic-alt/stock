import unittest
from unittest.mock import patch, MagicMock
import pandas as pd


class TestTuShareDataSource(unittest.TestCase):
    def setUp(self):
        # Import under test
        from src.data_sources.tushare_source import TuShareDataSource
        self.TuShareDataSource = TuShareDataSource

    @patch('src.data_sources.tushare_source.ts')
    def test_get_stock_history_success(self, mock_ts):
        # 模拟 pro_bar 返回
        df = pd.DataFrame({
            'trade_date': ['20220101', '20220102'],
            'open': [10, 11],
            'close': [11, 12],
            'high': [11.5, 12.5],
            'low': [9.5, 10.5],
            'vol': [1000, 1200],
            'amount': [100.0, 120.0]
        })
        mock_ts.pro_bar.return_value = df
        mock_ts.pro_api.return_value = MagicMock()

        ds = self.TuShareDataSource()
        ds._ready = True
        ds._pro = mock_ts
        out = ds.get_stock_history('600519', '20220101', '20220102')
        self.assertFalse(out.empty)
        self.assertIn('成交额', out.columns)

    @patch('src.data_sources.tushare_source.ts')
    def test_get_stock_realtime_fallback(self, mock_ts):
        # 模拟 get_realtime_quotes 失败，pro.daily 返回最近一日
        mock_ts.get_realtime_quotes.side_effect = Exception('no realtime')
        mock_daily = pd.DataFrame([{'trade_date': '20220102', 'close': 12.0, 'pre_close': 11.0, 'vol': 1000, 'amount': 120.0}])
        mock_ts.pro_api.return_value = MagicMock()
        ds = self.TuShareDataSource()
        ds._ready = True
        ds._pro = mock_ts
        mock_ts.pro_api.return_value.daily.return_value = mock_daily

        with patch.object(ds, '_pro', mock_ts.pro_api.return_value):
            rt = ds.get_stock_realtime('600519')
            self.assertIsNotNone(rt)
            self.assertEqual(rt['最新价'], 12.0)


if __name__ == '__main__':
    unittest.main()
