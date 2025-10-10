# -*- coding: utf-8 -*-
"""
yfinance 数据源模块
-------------------
功能：
1) get_stock_history：通过 yfinance 下载历史（自动前复权可选）
2) get_stock_realtime：使用 fast_info / 1m 历史获取最近价
3) get_index_realtime：同上（指数需传入 yfinance 支持的代码，如 ^GSPC、^HSI、000001.SS 等）

适配：
- A股：将 '600519.SH' 转换为 yfinance 的 '600519.SS'，'000001.SZ' -> '000001.SZ'（yfinance 已支持 .SZ）
- 返回字段统一中文、成交额单位为元（若 yfinance 无成交额，则返回 0）
"""
from __future__ import annotations
import math
import time
from typing import Optional, Dict

import pandas as pd

try:
    import yfinance as yf
    YF_AVAILABLE = True
except Exception:
    yf = None
    YF_AVAILABLE = False

try:
    from .base import DataSource
except Exception:
    class DataSource:  # type: ignore
        pass


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

def _yf_symbol(code: str) -> str:
    """
    将本项目常用代码转换为 yfinance 代码。
    - 600xxx.SH -> 600xxx.SS
    - 000xxx.SZ -> 000xxx.SZ（不变）
    - 指数若传 ^XXXX 或 000001.SS 等，直接返回
    """
    if code.startswith("^"):
        return code
    if code.endswith(".SZ") or code.endswith(".SS") or code.endswith(".KS") or code.endswith(".HK"):
        return code
    if code.endswith(".SH"):
        # yfinance 上海交易所使用 .SS
        return code.replace(".SH", ".SS")
    if "." not in code:
        # 无后缀的 A 股代码推断：6xxxx -> .SS；其他 -> .SZ
        return f"{code}.SS" if code.startswith("6") else f"{code}.SZ"
    return code


class YFinanceDataSource(DataSource):
    """yfinance 数据源"""
    def __init__(self):
        super().__init__()
        self._ready = YF_AVAILABLE

    # ------- 历史 -------
    def get_stock_history(self, stock_code: str, start_date: str, end_date: str,
                          adjust: str = 'qfq') -> pd.DataFrame:
        """
        返回列：['日期','开盘','收盘','最高','最低','成交量','成交额']
        yfinance 的 download 会返回 USD 或本地货币计价的 OHLCV；无成交额则以 0 兜底。
        adjust: 'qfq'/'hfq' 均使用 yfinance 的 'auto_adjust' 进行前复权（近似处理）
        """
        if not self._ready:
            return pd.DataFrame()
        sym = _yf_symbol(stock_code)
        auto_adjust = True if adjust in ('qfq', 'hfq') else False
        try:
            df = yf.download(sym, start=pd.to_datetime(start_date).strftime("%Y-%m-%d"),
                             end=(pd.to_datetime(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                             auto_adjust=auto_adjust, progress=False)
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={
                'Open': '开盘', 'Close': '收盘', 'High': '最高', 'Low': '最低', 'Volume': '成交量'
            })
            df.reset_index(inplace=True)
            df.rename(columns={'Date': '日期'}, inplace=True)
            out = df[['日期', '开盘', '收盘', '最高', '最低', '成交量']].copy()
            # yfinance 不直接给成交额；可粗略以 收盘*量 估算（注意不同市场货币与小数）
            out['成交额'] = out['收盘'].astype(float) * out['成交量'].astype(float)
            return out
        except Exception:
            return pd.DataFrame()

    # ------- 实时个股 -------
    def get_stock_realtime(self, stock_code: str) -> Optional[Dict]:
        if not self._ready:
            return None
        sym = _yf_symbol(stock_code)
        try:
            t = yf.Ticker(sym)
            # 尝试 fast_info
            latest = None
            pre_close = None
            try:
                fi = getattr(t, "fast_info", None)
                if fi:
                    latest = _safe_float(fi.get('last_price', None))
                    pre_close = _safe_float(fi.get('previous_close', None))
            except Exception:
                pass
            if latest is None:
                # fallback: 取1天1分钟历史的最后一根
                hist = t.history(period='1d', interval='1m')
                if hist is not None and not hist.empty:
                    latest = _safe_float(hist['Close'].iloc[-1])
                    if len(hist) >= 2:
                        pre_close = _safe_float(hist['Close'].iloc[-2])
            if latest is None:
                return None
            change = latest - (pre_close or latest)
            pct = (change / pre_close * 100.0) if pre_close else 0.0
            return {
                '代码': stock_code,
                '名称': sym,
                '最新价': latest,
                '涨跌幅': pct,
                '涨跌额': change,
                '成交量': 0,
                '成交额': 0.0,
                '振幅': 0.0,
                '最高': latest,
                '最低': latest,
                '今开': pre_close or latest,
                '昨收': pre_close or latest,
                '换手率': 0.0,
                '更新时间': time.strftime('%H:%M:%S'),
                '数据源': 'yfinance'
            }
        except Exception:
            return None

    # ------- 指数“实时” -------
    def get_index_realtime(self, index_code: str) -> Optional[Dict]:
        """
        传入 yfinance 支持的指数代码（如 '^GSPC', '^NDX', '^DJI', '^HSI', '000300.SS' 等）
        """
        if not self._ready:
            return None
        sym = _yf_symbol(index_code)
        try:
            t = yf.Ticker(sym)
            hist = t.history(period='1d', interval='1m')
            if hist is None or hist.empty:
                return None
            latest = _safe_float(hist['Close'].iloc[-1])
            pre = _safe_float(hist['Close'].iloc[-2]) if len(hist) >= 2 else latest
            change = latest - pre
            pct = (change / pre * 100.0) if pre else 0.0
            return {
                '代码': index_code,
                '名称': sym,
                '最新价': latest,
                '涨跌幅': pct,
                '涨跌额': change,
                '成交量': 0,
                '成交额': 0.0,
                '振幅': 0.0,
                '最高': latest,
                '最低': latest,
                '今开': pre,
                '昨收': pre,
                '换手率': 0.0,
                '更新时间': time.strftime('%H:%M:%S'),
                '数据源': 'yfinance'
            }
        except Exception:
            return None

    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        try:
            return self.get_stock_realtime(stock_code)
        except Exception:
            return None
