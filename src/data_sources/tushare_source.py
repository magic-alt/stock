# -*- coding: utf-8 -*-
"""
TuShare 数据源模块
------------------
功能：
1) get_stock_history：通过 TuShare Pro 拉取日线历史（复权可选，默认 qfq）
2) get_stock_realtime：使用 tushare 的实时行情接口（若不可用则退化为最近一日收盘）
3) get_index_realtime：使用 index_basic + index_daily 获取指数最近价（近似实时）

注意：
- 需在 config.py 中配置 TUSHARE_TOKEN（或环境变量 TUSHARE_TOKEN）。
- TuShare 的“实时”接口在不同账号权限下可用性不同；已内置多重兜底。
- 返回字段遵循项目统一规范：'代码','名称','最新价','涨跌幅','涨跌额','成交量','成交额','振幅','最高','最低','今开','昨收','换手率'
  其中不存在的字段会以 0 / 合理兜底返回。
"""
from __future__ import annotations
import os
import time
import math
from typing import Optional, Dict

import pandas as pd

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except Exception:
    TUSHARE_AVAILABLE = False

try:
    from .config import TUSHARE_TOKEN
except Exception:
    TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")

try:
    # 与现有体系尽量对齐；若不存在基类，则提供兜底定义
    from .base import DataSource
except Exception:
    class DataSource:  # type: ignore
        pass


# ----------------- 小工具 -----------------
def _safe_float(x, default: float = 0.0) -> float:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except Exception:
        return default

def _safe_int(x, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default

def _safe_str(x, default: str = "") -> str:
    try:
        s = str(x)
        return s if s.strip() != "" else default
    except Exception:
        return default


class TuShareDataSource(DataSource):
    """TuShare 数据源"""
    def __init__(self):
        super().__init__()
        self._ready = False
        self._pro = None
        if TUSHARE_AVAILABLE and TUSHARE_TOKEN:
            try:
                self._pro = ts.pro_api(TUSHARE_TOKEN)
                self._ready = True
            except Exception:
                self._ready = False

    # -------- 历史数据 --------
    def get_stock_history(self, stock_code: str, start_date: str, end_date: str,
                          adjust: str = 'qfq') -> pd.DataFrame:
        """
        返回列：['日期','开盘','收盘','最高','最低','成交量','成交额']
        TuShare ts_code 形如 '600519.SH'；若传入 '600519.SH/600519' 均尝试处理。
        """
        if not self._ready:
            return pd.DataFrame()
        ts_code = stock_code if stock_code.endswith((".SH", ".SZ")) else (
            f"{stock_code}.SH" if stock_code.startswith("6") else f"{stock_code}.SZ"
        )
        # 复权参数：qfq/hfq/None
        adj = adjust if adjust in ('qfq', 'hfq', '', None) else 'qfq'

        # 退避重试
        last_err = None
        for attempt in range(3):
            try:
                # 优先 pro.daily（不含复权）；使用 pro_bar 可做复权处理
                if adj in ('qfq', 'hfq'):
                    df = ts.pro_bar(ts_code=ts_code, adj=adj, start_date=start_date, end_date=end_date, factors=None)
                else:
                    df = self._pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df is None or df.empty:
                    raise ValueError("TuShare 历史数据为空")

                df = df.sort_values('trade_date').reset_index(drop=True)
                out = pd.DataFrame({
                    '日期': pd.to_datetime(df['trade_date']),
                    '开盘': df['open'].astype(float),
                    '收盘': df['close'].astype(float),
                    '最高': df['high'].astype(float),
                    '最低': df['low'].astype(float),
                    '成交量': df['vol'].astype(float) if 'vol' in df else df.get('vol', 0.0),
                    # TuShare 的金额字段为 'amount'（千元？万元？早期版本差异），官方定义为“成交额（千元）”
                    # 为统一到“元”，此处按千元 -> 元 乘以 1,000（若未来版本已为元，则量级会更大，但不影响策略计算的相对性）
                    '成交额': df['amount'].astype(float) * 1000.0 if 'amount' in df else 0.0
                })
                return out
            except Exception as e:
                last_err = e
                time.sleep(0.5 + attempt * 0.5)
        # 失败兜底
        print(f"[TuShare] 获取历史失败: {ts_code}, err={last_err}")
        return pd.DataFrame()

    # -------- 实时个股 --------
    def get_stock_realtime(self, stock_code: str) -> Optional[Dict]:
        """
        使用 tushare 的 get_realtime_quotes（旧接口，部分情况下可用）。
        若失败，回退：以最近一日收盘近似实时（仅兜底）。
        """
        if not self._ready:
            return None
        raw = None
        # 支持兩種传参（'600519' 或 '600519.SS/SZ'）
        code_no_suffix = stock_code.split('.')[0]
        try:
            # 旧接口：返回英文字段
            quotes = ts.get_realtime_quotes(code_no_suffix)
            if quotes is not None and not quotes.empty:
                raw = quotes.iloc[0]
                latest = _safe_float(raw.get('price'))
                pre_close = _safe_float(raw.get('pre_close'))
                change = latest - pre_close if pre_close else 0.0
                pct = (change / pre_close * 100.0) if pre_close else 0.0
                return {
                    '代码': stock_code,
                    '名称': _safe_str(raw.get('name'), stock_code),
                    '最新价': latest,
                    '涨跌幅': pct,
                    '涨跌额': change,
                    '成交量': _safe_int(raw.get('volume')),
                    # get_realtime_quotes 的 'amount' 单位通常为“元”
                    '成交额': _safe_float(raw.get('amount')),
                    '振幅': 0.0,
                    '最高': _safe_float(raw.get('high')),
                    '最低': _safe_float(raw.get('low')),
                    '今开': _safe_float(raw.get('open')),
                    '昨收': pre_close,
                    '换手率': 0.0,
                    '更新时间': time.strftime('%H:%M:%S'),
                    '数据源': 'tushare'
                }
        except Exception:
            pass

        # 兜底：用最近一日收盘近似（不建议依赖，仅在 akshare/sina 不可用时保底）
        try:
            ts_code = stock_code if stock_code.endswith((".SH", ".SZ")) else (
                f"{stock_code}.SH" if stock_code.startswith("6") else f"{stock_code}.SZ"
            )
            df = self._pro.daily(ts_code=ts_code, start_date=None, end_date=None)
            if df is not None and not df.empty:
                df = df.sort_values('trade_date').iloc[-1]
                latest = _safe_float(df['close'])
                pre_close = _safe_float(df['pre_close']) if 'pre_close' in df else _safe_float(df.get('pre_close', 0.0))
                change = latest - pre_close if pre_close else 0.0
                pct = (change / pre_close * 100.0) if pre_close else 0.0
                return {
                    '代码': stock_code,
                    '名称': stock_code,
                    '最新价': latest,
                    '涨跌幅': pct,
                    '涨跌额': change,
                    '成交量': _safe_int(df.get('vol', 0)),
                    '成交额': _safe_float(df.get('amount', 0.0)) * 1000.0,  # 千元->元
                    '振幅': 0.0,
                    '最高': _safe_float(df.get('high', latest)),
                    '最低': _safe_float(df.get('low', latest)),
                    '今开': _safe_float(df.get('open', latest)),
                    '昨收': pre_close,
                    '换手率': 0.0,
                    '更新时间': time.strftime('%H:%M:%S'),
                    '数据源': 'tushare(daily)'
                }
        except Exception:
            pass
        return None

    # -------- 指数“实时”（近似） --------
    def get_index_realtime(self, index_code: str) -> Optional[Dict]:
        """
        TuShare 对指数实时的免费支持有限；此处以最近交易日的 index_daily 近似。
        index_code 建议传 ts_code: 如 '000300.SH'.
        """
        if not self._ready:
            return None

    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """兼容基类：默认为实时信息"""
        try:
            return self.get_stock_realtime(stock_code)
        except Exception:
            return None
        ts_code = index_code if index_code.endswith((".SH", ".SZ")) else (
            f"{index_code}.SH" if index_code.startswith("0") else f"{index_code}.SZ"
        )
        try:
            df = self._pro.index_daily(ts_code=ts_code)
            if df is None or df.empty:
                return None
            row = df.sort_values('trade_date').iloc[-1]
            latest = _safe_float(row['close'])
            pre_close = _safe_float(row.get('pre_close', latest))
            change = latest - pre_close if pre_close else 0.0
            pct = (change / pre_close * 100.0) if pre_close else 0.0
            return {
                '代码': index_code,
                '名称': ts_code,
                '最新价': latest,
                '涨跌幅': pct,
                '涨跌额': change,
                '成交量': 0,
                '成交额': 0.0,
                '振幅': 0.0,
                '最高': _safe_float(row.get('high', latest)),
                '最低': _safe_float(row.get('low', latest)),
                '今开': _safe_float(row.get('open', latest)),
                '昨收': pre_close,
                '换手率': 0.0,
                '更新时间': time.strftime('%H:%M:%S'),
                '数据源': 'tushare(index_daily)'
            }
        except Exception:
            return None
