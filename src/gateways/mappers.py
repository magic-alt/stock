"""
Symbol and Order Mappers - 标的代码与订单字段映射

Provides utilities for converting between internal and broker-specific formats:
- Symbol format conversion (600519.SH <-> various broker formats)
- Order field mapping (internal OrderType <-> broker-specific types)
- Exchange code enumeration

V3.2.0: Initial release

Usage:
    >>> from src.gateways.mappers import SymbolMapper, ExchangeCode
    >>> 
    >>> # Convert internal symbol to XTP format
    >>> mapper = SymbolMapper()
    >>> xtp_code, xtp_exchange = mapper.to_xtp("600519.SH")
    >>> # xtp_code = "600519", xtp_exchange = XTPExchange.SH
    >>> 
    >>> # Convert from XTP format to internal
    >>> internal = mapper.from_xtp("600519", XTPExchange.SH)
    >>> # internal = "600519.SH"
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Dict, Optional, Tuple

from src.gateways.base_live_gateway import (
    OrderType, OrderSide, OrderStatus, TimeInForce
)


# ---------------------------------------------------------------------------
# Exchange Codes
# ---------------------------------------------------------------------------

class ExchangeCode(str, Enum):
    """
    Standard exchange codes used internally.
    
    Format: EXCHANGE.SUFFIX
    """
    # A-Share exchanges
    SSE = "SH"      # Shanghai Stock Exchange (上海证券交易所)
    SZSE = "SZ"     # Shenzhen Stock Exchange (深圳证券交易所)
    BSE = "BJ"      # Beijing Stock Exchange (北京证券交易所)
    
    # Index
    INDEX = "IDX"
    
    # Futures
    CFFEX = "CFE"   # 中金所
    SHFE = "SHF"    # 上期所
    DCE = "DCE"     # 大商所
    CZCE = "ZCE"    # 郑商所
    INE = "INE"     # 上期能源


class XTPExchange(IntEnum):
    """XTP exchange enumeration (from XTP API)."""
    SH = 1   # 上交所
    SZ = 2   # 深交所
    BJ = 3   # 北交所 (XTP 2.x)


class QMTExchange(str, Enum):
    """QMT/XtQuant exchange codes."""
    SH = "SH"
    SZ = "SZ"
    BJ = "BJ"


class UFTExchange(str, Enum):
    """Hundsun UFT exchange codes."""
    SSE = "1"   # 上交所
    SZSE = "2"  # 深交所
    BSE = "3"   # 北交所


# ---------------------------------------------------------------------------
# Symbol Mapper
# ---------------------------------------------------------------------------

class SymbolMapper:
    """
    Utility class for symbol format conversion.
    
    Internal format: {code}.{exchange}
        Examples: 600519.SH, 000001.SZ, 430047.BJ
    
    Supports conversion to/from:
    - XtQuant/QMT format
    - XTP format
    - Hundsun UFT format
    """
    
    # Internal exchange to standard mapping
    EXCHANGE_MAP = {
        "SH": ExchangeCode.SSE,
        "SS": ExchangeCode.SSE,  # Alternative
        "SZ": ExchangeCode.SZSE,
        "BJ": ExchangeCode.BSE,
    }
    
    # Regex for parsing internal symbol format
    SYMBOL_PATTERN = re.compile(r"^(\d{6})\.([A-Z]{2,3})$")
    
    @classmethod
    def parse(cls, symbol: str) -> Tuple[str, str]:
        """
        Parse internal symbol format.
        
        Args:
            symbol: Symbol in format "600519.SH"
            
        Returns:
            Tuple of (code, exchange)
            
        Raises:
            ValueError: If format is invalid
        """
        match = cls.SYMBOL_PATTERN.match(symbol.upper())
        if not match:
            raise ValueError(f"Invalid symbol format: {symbol}")
        return match.group(1), match.group(2)
    
    @classmethod
    def normalize(cls, symbol: str) -> str:
        """
        Normalize symbol to internal format.
        
        Handles various input formats:
        - 600519.SH -> 600519.SH
        - SH600519 -> 600519.SH
        - 600519 (with exchange hint) -> 600519.SH
        """
        symbol = symbol.upper().strip()
        
        # Already in correct format
        if cls.SYMBOL_PATTERN.match(symbol):
            return symbol
        
        # Format: SH600519 or SZ000001
        if len(symbol) == 8 and symbol[:2] in ("SH", "SZ", "BJ"):
            return f"{symbol[2:]}.{symbol[:2]}"
        
        # Format: 600519.SS (Yahoo style)
        if ".SS" in symbol:
            return symbol.replace(".SS", ".SH")
        
        # Pure code - try to infer exchange
        if symbol.isdigit() and len(symbol) == 6:
            exchange = cls._infer_exchange(symbol)
            return f"{symbol}.{exchange}"
        
        return symbol
    
    @classmethod
    def _infer_exchange(cls, code: str) -> str:
        """Infer exchange from stock code."""
        if code.startswith(("60", "68")):  # 主板, 科创板
            return "SH"
        elif code.startswith(("00", "30")):  # 主板, 创业板
            return "SZ"
        elif code.startswith(("43", "83", "87")):  # 新三板/北交所
            return "BJ"
        else:
            return "SH"  # Default to Shanghai
    
    # ---------------------------------------------------------------------------
    # XtQuant/QMT Conversion
    # ---------------------------------------------------------------------------
    
    @classmethod
    def to_xtquant(cls, symbol: str) -> str:
        """
        Convert to XtQuant/QMT format.
        
        XtQuant uses: "600519.SH" or "000001.SZ"
        Same as internal format.
        """
        return cls.normalize(symbol)
    
    @classmethod
    def from_xtquant(cls, symbol: str) -> str:
        """Convert from XtQuant/QMT format to internal."""
        return cls.normalize(symbol)
    
    # ---------------------------------------------------------------------------
    # XTP Conversion
    # ---------------------------------------------------------------------------
    
    @classmethod
    def to_xtp(cls, symbol: str) -> Tuple[str, XTPExchange]:
        """
        Convert to XTP format.
        
        XTP uses: (code, market_id)
        - code: "600519"
        - market_id: XTPExchange.SH (1) or XTPExchange.SZ (2)
        
        Returns:
            Tuple of (code, XTPExchange)
        """
        code, exchange = cls.parse(cls.normalize(symbol))
        
        if exchange == "SH":
            return code, XTPExchange.SH
        elif exchange == "SZ":
            return code, XTPExchange.SZ
        elif exchange == "BJ":
            return code, XTPExchange.BJ
        else:
            raise ValueError(f"Unknown exchange for XTP: {exchange}")
    
    @classmethod
    def from_xtp(cls, code: str, exchange: XTPExchange) -> str:
        """Convert from XTP format to internal."""
        if exchange == XTPExchange.SH:
            return f"{code}.SH"
        elif exchange == XTPExchange.SZ:
            return f"{code}.SZ"
        elif exchange == XTPExchange.BJ:
            return f"{code}.BJ"
        else:
            raise ValueError(f"Unknown XTP exchange: {exchange}")
    
    # ---------------------------------------------------------------------------
    # Hundsun UFT Conversion
    # ---------------------------------------------------------------------------
    
    @classmethod
    def to_uft(cls, symbol: str) -> Tuple[str, str]:
        """
        Convert to Hundsun UFT format.
        
        UFT uses: (code, exchange_id)
        - code: "600519"
        - exchange_id: "1" (SH), "2" (SZ), "3" (BJ)
        
        Returns:
            Tuple of (code, exchange_id)
        """
        code, exchange = cls.parse(cls.normalize(symbol))
        
        if exchange == "SH":
            return code, UFTExchange.SSE.value
        elif exchange == "SZ":
            return code, UFTExchange.SZSE.value
        elif exchange == "BJ":
            return code, UFTExchange.BSE.value
        else:
            raise ValueError(f"Unknown exchange for UFT: {exchange}")
    
    @classmethod
    def from_uft(cls, code: str, exchange_id: str) -> str:
        """Convert from Hundsun UFT format to internal."""
        if exchange_id == "1":
            return f"{code}.SH"
        elif exchange_id == "2":
            return f"{code}.SZ"
        elif exchange_id == "3":
            return f"{code}.BJ"
        else:
            raise ValueError(f"Unknown UFT exchange: {exchange_id}")


# ---------------------------------------------------------------------------
# Order Mapper
# ---------------------------------------------------------------------------

class OrderMapper:
    """
    Utility class for order field conversion.
    
    Maps internal order types/sides to broker-specific values.
    """
    
    # ---------------------------------------------------------------------------
    # XtQuant/QMT Mappings
    # ---------------------------------------------------------------------------
    
    # XtQuant order types
    XTQUANT_ORDER_TYPES = {
        OrderType.LIMIT: 1,      # 限价
        OrderType.MARKET: 2,     # 市价
        OrderType.STOP: 3,       # 止损 (if supported)
        OrderType.FAK: 4,        # FAK
        OrderType.FOK: 5,        # FOK
    }
    
    XTQUANT_ORDER_TYPES_REVERSE = {v: k for k, v in XTQUANT_ORDER_TYPES.items()}
    
    # XtQuant sides
    XTQUANT_SIDES = {
        OrderSide.BUY: 23,   # 买入
        OrderSide.SELL: 24,  # 卖出
    }
    
    XTQUANT_SIDES_REVERSE = {v: k for k, v in XTQUANT_SIDES.items()}
    
    # XtQuant order status
    XTQUANT_STATUS = {
        0: OrderStatus.SUBMITTED,       # 已报
        1: OrderStatus.PARTIALLY_FILLED, # 部成
        2: OrderStatus.FILLED,          # 已成
        3: OrderStatus.PENDING_SUBMIT,  # 待报
        4: OrderStatus.CANCELLED,       # 已撤
        5: OrderStatus.REJECTED,        # 废单
        6: OrderStatus.CANCEL_PENDING,  # 待撤
    }
    
    @classmethod
    def order_type_to_xtquant(cls, order_type: OrderType) -> int:
        """Convert OrderType to XtQuant order type code."""
        return cls.XTQUANT_ORDER_TYPES.get(order_type, 1)
    
    @classmethod
    def order_type_from_xtquant(cls, code: int) -> OrderType:
        """Convert XtQuant order type code to OrderType."""
        return cls.XTQUANT_ORDER_TYPES_REVERSE.get(code, OrderType.LIMIT)
    
    @classmethod
    def side_to_xtquant(cls, side: OrderSide) -> int:
        """Convert OrderSide to XtQuant side code."""
        return cls.XTQUANT_SIDES.get(side, 23)
    
    @classmethod
    def side_from_xtquant(cls, code: int) -> OrderSide:
        """Convert XtQuant side code to OrderSide."""
        return cls.XTQUANT_SIDES_REVERSE.get(code, OrderSide.BUY)
    
    @classmethod
    def status_from_xtquant(cls, code: int) -> OrderStatus:
        """Convert XtQuant status code to OrderStatus."""
        return cls.XTQUANT_STATUS.get(code, OrderStatus.PENDING_SUBMIT)
    
    # ---------------------------------------------------------------------------
    # XTP Mappings
    # ---------------------------------------------------------------------------
    
    # XTP order types (from xtp_api_data_type.h)
    XTP_ORDER_TYPES = {
        OrderType.LIMIT: 1,   # XTP_PRICE_LIMIT
        OrderType.MARKET: 2,  # XTP_PRICE_MARKET
        OrderType.FAK: 3,     # XTP_PRICE_FAK
        OrderType.FOK: 4,     # XTP_PRICE_FOK
    }
    
    XTP_ORDER_TYPES_REVERSE = {v: k for k, v in XTP_ORDER_TYPES.items()}
    
    # XTP sides
    XTP_SIDES = {
        OrderSide.BUY: 1,   # XTP_SIDE_BUY
        OrderSide.SELL: 2,  # XTP_SIDE_SELL
    }
    
    XTP_SIDES_REVERSE = {v: k for k, v in XTP_SIDES.items()}
    
    # XTP order status
    XTP_STATUS = {
        0: OrderStatus.PENDING_SUBMIT,  # XTP_ORDER_STATUS_INIT
        1: OrderStatus.SUBMITTED,       # XTP_ORDER_STATUS_ALLTRADED (all traded)
        2: OrderStatus.PARTIALLY_FILLED, # XTP_ORDER_STATUS_PARTTRADEDQUEUEING
        3: OrderStatus.SUBMITTED,       # XTP_ORDER_STATUS_PARTTRADEDNOTQUEUEING
        4: OrderStatus.SUBMITTED,       # XTP_ORDER_STATUS_NOTRADEQUEUEING
        5: OrderStatus.CANCELLED,       # XTP_ORDER_STATUS_CANCELED
        6: OrderStatus.REJECTED,        # XTP_ORDER_STATUS_REJECTED
        7: OrderStatus.ERROR,           # XTP_ORDER_STATUS_UNKNOWN
    }
    
    @classmethod
    def order_type_to_xtp(cls, order_type: OrderType) -> int:
        """Convert OrderType to XTP order type code."""
        return cls.XTP_ORDER_TYPES.get(order_type, 1)
    
    @classmethod
    def order_type_from_xtp(cls, code: int) -> OrderType:
        """Convert XTP order type code to OrderType."""
        return cls.XTP_ORDER_TYPES_REVERSE.get(code, OrderType.LIMIT)
    
    @classmethod
    def side_to_xtp(cls, side: OrderSide) -> int:
        """Convert OrderSide to XTP side code."""
        return cls.XTP_SIDES.get(side, 1)
    
    @classmethod
    def side_from_xtp(cls, code: int) -> OrderSide:
        """Convert XTP side code to OrderSide."""
        return cls.XTP_SIDES_REVERSE.get(code, OrderSide.BUY)
    
    @classmethod
    def status_from_xtp(cls, code: int) -> OrderStatus:
        """Convert XTP status code to OrderStatus."""
        return cls.XTP_STATUS.get(code, OrderStatus.PENDING_SUBMIT)
    
    # ---------------------------------------------------------------------------
    # Hundsun UFT Mappings
    # ---------------------------------------------------------------------------
    
    # UFT order types
    UFT_ORDER_TYPES = {
        OrderType.LIMIT: "0",   # 限价
        OrderType.MARKET: "1",  # 市价
        OrderType.FAK: "2",     # FAK
        OrderType.FOK: "3",     # FOK
    }
    
    UFT_ORDER_TYPES_REVERSE = {v: k for k, v in UFT_ORDER_TYPES.items()}
    
    # UFT sides
    UFT_SIDES = {
        OrderSide.BUY: "1",   # 买入
        OrderSide.SELL: "2",  # 卖出
    }
    
    UFT_SIDES_REVERSE = {v: k for k, v in UFT_SIDES.items()}
    
    # UFT order status
    UFT_STATUS = {
        "0": OrderStatus.PENDING_SUBMIT,   # 未报
        "1": OrderStatus.SUBMITTED,        # 待报
        "2": OrderStatus.SUBMITTED,        # 已报
        "3": OrderStatus.SUBMITTED,        # 已报待撤
        "4": OrderStatus.PARTIALLY_FILLED, # 部成待撤
        "5": OrderStatus.PARTIALLY_FILLED, # 部撤
        "6": OrderStatus.CANCELLED,        # 已撤
        "7": OrderStatus.FILLED,           # 已成
        "8": OrderStatus.REJECTED,         # 废单
        "9": OrderStatus.PARTIALLY_FILLED, # 部成
    }
    
    @classmethod
    def order_type_to_uft(cls, order_type: OrderType) -> str:
        """Convert OrderType to UFT order type code."""
        return cls.UFT_ORDER_TYPES.get(order_type, "0")
    
    @classmethod
    def order_type_from_uft(cls, code: str) -> OrderType:
        """Convert UFT order type code to OrderType."""
        return cls.UFT_ORDER_TYPES_REVERSE.get(code, OrderType.LIMIT)
    
    @classmethod
    def side_to_uft(cls, side: OrderSide) -> str:
        """Convert OrderSide to UFT side code."""
        return cls.UFT_SIDES.get(side, "1")
    
    @classmethod
    def side_from_uft(cls, code: str) -> OrderSide:
        """Convert UFT side code to OrderSide."""
        return cls.UFT_SIDES_REVERSE.get(code, OrderSide.BUY)
    
    @classmethod
    def status_from_uft(cls, code: str) -> OrderStatus:
        """Convert UFT status code to OrderStatus."""
        return cls.UFT_STATUS.get(code, OrderStatus.PENDING_SUBMIT)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    # Exchange enums
    "ExchangeCode",
    "XTPExchange",
    "QMTExchange",
    "UFTExchange",
    
    # Mappers
    "SymbolMapper",
    "OrderMapper",
]
