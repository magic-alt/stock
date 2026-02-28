"""
Performance Optimization Utilities

Provides tools for optimizing performance in the quantitative trading platform.

V3.1.0: Initial release - performance optimization system

Features:
- LRU caching with TTL support
- Batch processing utilities
- Memory-efficient data handling
- Profiling decorators
- Parallel execution helpers

Usage:
    >>> from src.core.performance import cached, profile, batch_process
    >>> 
    >>> @cached(ttl=3600)
    ... def expensive_calculation():
    ...     ...
    >>> 
    >>> @profile
    ... def analyze_data():
    ...     ...
"""
from __future__ import annotations

import functools
import gc
import hashlib
import pickle
import threading
import time
import weakref
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Generic, Iterator, List, Optional, TypeVar, Union

from .logger import get_logger

logger = get_logger("performance")

T = TypeVar("T")
R = TypeVar("R")


# ---------------------------------------------------------------------------
# TTL Cache
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    """Cache entry with value and expiration time."""
    value: Any
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


class TTLCache(Generic[T]):
    """
    Thread-safe LRU cache with TTL (Time To Live) support.
    
    Features:
    - LRU eviction when max size reached
    - TTL-based expiration
    - Thread-safe operations
    - Statistics tracking
    
    Usage:
        >>> cache = TTLCache[pd.DataFrame](max_size=100, ttl=3600)
        >>> cache.set("key", expensive_dataframe)
        >>> df = cache.get("key")
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl: Optional[int] = None,  # seconds
    ):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum number of entries
            ttl: Time to live in seconds (None = no expiration)
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str, default: T = None) -> Optional[T]:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return default
            
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return default
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value
    
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        with self._lock:
            # Calculate expiration
            expires_at = None
            effective_ttl = ttl if ttl is not None else self._ttl
            if effective_ttl is not None:
                expires_at = datetime.now() + timedelta(seconds=effective_ttl)
            
            # Add or update entry
            if key in self._cache:
                del self._cache[key]
            
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
            
            # Evict oldest if needed
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
            }


# Global cache instance
_global_cache = TTLCache(max_size=1000, ttl=3600)


def cached(
    ttl: Optional[int] = None,
    max_size: int = 128,
    key_func: Optional[Callable[..., str]] = None,
    cache: Optional[TTLCache] = None,
):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time to live in seconds
        max_size: Maximum cache size for this function
        key_func: Custom key generation function
        cache: Custom cache instance (uses global if None)
    
    Usage:
        >>> @cached(ttl=3600)
        ... def expensive_calculation(x, y):
        ...     return x + y
    """
    use_cache = cache or _global_cache
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Create function-specific cache if not using global
        local_cache = TTLCache(max_size=max_size, ttl=ttl) if cache is None else use_cache
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Check cache
            result = local_cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return result
            
            # Execute and cache
            result = func(*args, **kwargs)
            local_cache.set(key, result, ttl)
            return result
        
        # Expose cache for manual operations
        wrapper.cache = local_cache
        wrapper.clear_cache = local_cache.clear
        
        return wrapper
    
    return decorator


# ---------------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------------

@dataclass
class ProfileResult:
    """Profiling result container."""
    function_name: str
    elapsed_time: float  # seconds
    memory_before: int  # bytes
    memory_after: int  # bytes
    memory_delta: int  # bytes
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        return (
            f"{self.function_name}: {self.elapsed_time:.4f}s, "
            f"memory: {self.memory_delta / 1024 / 1024:+.2f}MB"
        )


class ProfileStats:
    """Collect and aggregate profiling statistics."""
    
    def __init__(self):
        self._results: Dict[str, List[ProfileResult]] = {}
        self._lock = threading.Lock()
    
    def record(self, result: ProfileResult) -> None:
        """Record a profiling result."""
        with self._lock:
            if result.function_name not in self._results:
                self._results[result.function_name] = []
            self._results[result.function_name].append(result)
    
    def get_summary(self, function_name: Optional[str] = None) -> Dict[str, Any]:
        """Get profiling summary."""
        with self._lock:
            if function_name:
                results = self._results.get(function_name, [])
                return self._summarize_results(function_name, results)
            
            return {
                name: self._summarize_results(name, results)
                for name, results in self._results.items()
            }
    
    def _summarize_results(self, name: str, results: List[ProfileResult]) -> Dict[str, Any]:
        if not results:
            return {"calls": 0}
        
        times = [r.elapsed_time for r in results]
        return {
            "calls": len(results),
            "total_time": sum(times),
            "avg_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
        }
    
    def clear(self) -> None:
        """Clear all statistics."""
        with self._lock:
            self._results.clear()


# Global profile stats
_profile_stats = ProfileStats()


def _get_memory_usage() -> int:
    """Get current memory usage in bytes."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss
    except ImportError:
        return 0


def profile(
    func: Optional[Callable] = None,
    log_result: bool = True,
    track_memory: bool = True,
    stats: Optional[ProfileStats] = None,
):
    """
    Decorator for profiling function execution.
    
    Args:
        func: Function to profile (for direct decoration)
        log_result: Whether to log profiling results
        track_memory: Whether to track memory usage
        stats: Custom stats collector
    
    Usage:
        >>> @profile
        ... def slow_function():
        ...     time.sleep(1)
        
        >>> @profile(log_result=False)
        ... def quiet_function():
        ...     pass
    """
    use_stats = stats or _profile_stats
    
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Memory before
            mem_before = _get_memory_usage() if track_memory else 0
            
            # Execute
            start_time = time.perf_counter()
            result = f(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            
            # Memory after
            mem_after = _get_memory_usage() if track_memory else 0
            
            # Record result
            profile_result = ProfileResult(
                function_name=f.__name__,
                elapsed_time=elapsed,
                memory_before=mem_before,
                memory_after=mem_after,
                memory_delta=mem_after - mem_before,
            )
            use_stats.record(profile_result)
            
            if log_result:
                logger.debug(str(profile_result))
            
            return result
        
        return wrapper
    
    # Support both @profile and @profile()
    if func is not None:
        return decorator(func)
    return decorator


@contextmanager
def profile_block(name: str, log_result: bool = True):
    """
    Context manager for profiling code blocks.
    
    Usage:
        >>> with profile_block("data_loading"):
        ...     data = load_large_dataset()
    """
    mem_before = _get_memory_usage()
    start_time = time.perf_counter()
    
    yield
    
    elapsed = time.perf_counter() - start_time
    mem_after = _get_memory_usage()
    
    result = ProfileResult(
        function_name=name,
        elapsed_time=elapsed,
        memory_before=mem_before,
        memory_after=mem_after,
        memory_delta=mem_after - mem_before,
    )
    _profile_stats.record(result)
    
    if log_result:
        logger.debug(str(result))


def get_profile_summary() -> Dict[str, Any]:
    """Get global profiling summary."""
    return _profile_stats.get_summary()


# ---------------------------------------------------------------------------
# Batch Processing
# ---------------------------------------------------------------------------

def batch_process(
    items: List[T],
    process_func: Callable[[T], R],
    batch_size: int = 100,
    max_workers: int = 4,
    use_processes: bool = False,
    show_progress: bool = False,
    on_error: str = "raise",  # "raise", "skip", "none"
) -> List[R]:
    """
    Process items in batches with optional parallelization.
    
    Args:
        items: Items to process
        process_func: Function to apply to each item
        batch_size: Items per batch
        max_workers: Maximum parallel workers
        use_processes: Use processes instead of threads
        show_progress: Show progress bar
        on_error: Error handling: "raise", "skip", "none"
    
    Returns:
        List of results (may contain None for skipped errors)
    
    Usage:
        >>> def process_symbol(symbol):
        ...     return load_data(symbol)
        >>> 
        >>> results = batch_process(
        ...     symbols,
        ...     process_symbol,
        ...     batch_size=50,
        ...     max_workers=4,
        ... )
    """
    results: List[Optional[R]] = [None] * len(items)
    
    # Choose executor
    executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
    
    def process_batch(batch_items: List[tuple]) -> List[tuple]:
        """Process a batch of (index, item) pairs."""
        batch_results = []
        for idx, item in batch_items:
            try:
                result = process_func(item)
                batch_results.append((idx, result, None))
            except Exception as e:
                if on_error == "raise":
                    raise
                batch_results.append((idx, None, str(e)))
        return batch_results
    
    # Create batches
    batches = []
    for i in range(0, len(items), batch_size):
        batch = [(i + j, items[i + j]) for j in range(min(batch_size, len(items) - i))]
        batches.append(batch)
    
    # Process
    with executor_class(max_workers=max_workers) as executor:
        futures = {executor.submit(process_batch, batch): batch for batch in batches}
        
        completed = 0
        for future in as_completed(futures):
            try:
                batch_results = future.result()
                for idx, result, error in batch_results:
                    if error and on_error == "skip":
                        logger.warning(f"Skipped item {idx}: {error}")
                        continue
                    results[idx] = result
            except Exception as e:
                if on_error == "raise":
                    raise
                logger.error(f"Batch processing error: {e}")
            
            completed += 1
            if show_progress:
                logger.info(f"Progress: {completed}/{len(batches)} batches")
    
    return results


def chunked(iterable: List[T], size: int) -> Iterator[List[T]]:
    """
    Split iterable into chunks of given size.
    
    Usage:
        >>> for chunk in chunked(large_list, 100):
        ...     process_chunk(chunk)
    """
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


# ---------------------------------------------------------------------------
# Memory Management
# ---------------------------------------------------------------------------

class MemoryManager:
    """
    Memory management utilities.
    
    Features:
    - Memory usage monitoring
    - Garbage collection triggers
    - Memory limit enforcement
    """
    
    def __init__(self, memory_limit_mb: Optional[float] = None):
        """
        Initialize memory manager.
        
        Args:
            memory_limit_mb: Memory limit in MB (None = no limit)
        """
        self.memory_limit = memory_limit_mb * 1024 * 1024 if memory_limit_mb else None
        self._references: Dict[str, weakref.ref] = {}
    
    def get_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        return _get_memory_usage() / 1024 / 1024
    
    def check_limit(self) -> bool:
        """Check if memory limit exceeded."""
        if self.memory_limit is None:
            return False
        return _get_memory_usage() > self.memory_limit
    
    def collect_garbage(self, generation: int = 2) -> int:
        """
        Run garbage collection.
        
        Returns:
            Number of objects collected
        """
        return gc.collect(generation)
    
    def register(self, name: str, obj: Any) -> None:
        """Register object for tracking (weak reference)."""
        self._references[name] = weakref.ref(obj)
    
    def is_alive(self, name: str) -> bool:
        """Check if registered object is still alive."""
        ref = self._references.get(name)
        return ref is not None and ref() is not None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "usage_mb": self.get_usage_mb(),
            "limit_mb": self.memory_limit / 1024 / 1024 if self.memory_limit else None,
            "gc_counts": gc.get_count(),
            "tracked_objects": len([r for r in self._references.values() if r() is not None]),
        }


@contextmanager
def memory_guard(limit_mb: float, action: str = "warn"):
    """
    Context manager to guard memory usage.
    
    Args:
        limit_mb: Memory limit in MB
        action: "warn" or "raise" when limit exceeded
    
    Usage:
        >>> with memory_guard(1024, action="warn"):
        ...     process_large_data()
    """
    manager = MemoryManager(limit_mb)
    start_usage = manager.get_usage_mb()
    
    yield manager
    
    end_usage = manager.get_usage_mb()
    delta = end_usage - start_usage
    
    if manager.check_limit():
        msg = f"Memory limit exceeded: {end_usage:.1f}MB > {limit_mb}MB (delta: {delta:+.1f}MB)"
        if action == "raise":
            raise MemoryError(msg)
        logger.warning(msg)


# ---------------------------------------------------------------------------
# Data Frame Optimization
# ---------------------------------------------------------------------------

def optimize_dataframe(df, category_threshold: float = 0.5) -> None:
    """
    Optimize DataFrame memory usage in-place.
    
    Optimizations:
    - Downcast numeric types
    - Convert low-cardinality strings to category
    
    Args:
        df: pandas DataFrame to optimize
        category_threshold: Convert to category if unique ratio < threshold
    
    Usage:
        >>> df = load_large_dataframe()
        >>> optimize_dataframe(df)
        >>> # Memory usage reduced
    """
    import numpy as np
    import pandas as pd
    
    start_mem = df.memory_usage(deep=True).sum()
    
    for col in df.columns:
        col_type = df[col].dtype
        
        # Downcast integers
        if col_type in ['int64', 'int32']:
            df[col] = pd.to_numeric(df[col], downcast='integer')
        
        # Downcast floats
        elif col_type in ['float64']:
            df[col] = pd.to_numeric(df[col], downcast='float')
        
        # Convert strings to category
        elif col_type == 'object':
            unique_ratio = df[col].nunique() / len(df)
            if unique_ratio < category_threshold:
                df[col] = df[col].astype('category')
    
    end_mem = df.memory_usage(deep=True).sum()
    reduction = (start_mem - end_mem) / start_mem * 100
    
    logger.debug(
        f"DataFrame optimized",
        before_mb=start_mem / 1024 / 1024,
        after_mb=end_mem / 1024 / 1024,
        reduction_pct=reduction,
    )


# ---------------------------------------------------------------------------
# Parallel Utilities
# ---------------------------------------------------------------------------

def parallel_map(
    func: Callable[[T], R],
    items: List[T],
    max_workers: int = 4,
    use_processes: bool = False,
) -> List[R]:
    """
    Parallel map function.
    
    Args:
        func: Function to apply
        items: Items to process
        max_workers: Number of parallel workers
        use_processes: Use processes instead of threads
    
    Returns:
        List of results in same order as items
    
    Usage:
        >>> results = parallel_map(process_item, items, max_workers=8)
    """
    executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
    
    with executor_class(max_workers=max_workers) as executor:
        results = list(executor.map(func, items))
    
    return results


@contextmanager
def timed(name: str = "operation"):
    """
    Simple timing context manager.
    
    Usage:
        >>> with timed("data_load"):
        ...     data = load_data()
        # Logs: data_load completed in 1.23s
    """
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    logger.info(f"{name} completed in {elapsed:.2f}s")


# ---------------------------------------------------------------------------
# Tiered Cache (L1 Memory + L2 SQLite)
# ---------------------------------------------------------------------------

class TieredCache(Generic[T]):
    """
    Two-level cache: L1 in-memory (hot) + L2 SQLite on-disk (cold).

    Access pattern:
    - get(): L1 hit → return.  L1 miss → check L2 → promote to L1 → return.
    - set(): write to both L1 and L2.
    - Entries evicted from L1 (LRU) remain in L2 for later promotion.
    - L2 uses its own TTL for long-term staleness cleanup.

    Usage:
        >>> cache = TieredCache[bytes](l1_max=100, l1_ttl=300, l2_path="cache/tiered.db", l2_ttl=86400)
        >>> cache.set("key", data)
        >>> val = cache.get("key")
    """

    def __init__(
        self,
        l1_max: int = 500,
        l1_ttl: Optional[int] = 300,
        l2_path: Optional[str] = None,
        l2_ttl: Optional[int] = 86400,
    ):
        import sqlite3 as _sqlite3

        self._l1 = TTLCache(max_size=l1_max, ttl=l1_ttl)
        self._l2_ttl = l2_ttl

        db_path = l2_path or os.path.join(
            os.environ.get("CACHE_DIR", "cache"), "tiered_cache.db"
        )
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._l2_conn = _sqlite3.connect(db_path, check_same_thread=False)
        self._l2_lock = threading.Lock()
        self._l2_conn.execute(
            "CREATE TABLE IF NOT EXISTS tiered_cache "
            "(key TEXT PRIMARY KEY, value BLOB, expires_at REAL)"
        )
        self._l2_conn.commit()

        # stats
        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0

    # -- public API ----------------------------------------------------------

    def get(self, key: str, default: T = None) -> Optional[T]:
        """Get value: L1 → L2 → miss."""
        val = self._l1.get(key)
        if val is not None:
            self._l1_hits += 1
            return val

        val = self._l2_get(key)
        if val is not None:
            self._l2_hits += 1
            # promote to L1
            self._l1.set(key, val)
            return val

        self._misses += 1
        return default

    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """Write to L1 and L2."""
        self._l1.set(key, value, ttl)
        self._l2_set(key, value)

    def delete(self, key: str) -> None:
        self._l1.delete(key)
        with self._l2_lock:
            self._l2_conn.execute("DELETE FROM tiered_cache WHERE key=?", (key,))
            self._l2_conn.commit()

    def clear(self) -> None:
        self._l1.clear()
        with self._l2_lock:
            self._l2_conn.execute("DELETE FROM tiered_cache")
            self._l2_conn.commit()
        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0

    def cleanup_expired(self) -> int:
        """Remove expired entries from both levels."""
        count = self._l1.cleanup_expired()
        with self._l2_lock:
            cur = self._l2_conn.execute(
                "DELETE FROM tiered_cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                (time.time(),),
            )
            count += cur.rowcount
            self._l2_conn.commit()
        return count

    @property
    def stats(self) -> Dict[str, Any]:
        total = self._l1_hits + self._l2_hits + self._misses
        return {
            "l1": self._l1.stats,
            "l2_size": self._l2_size(),
            "l1_hits": self._l1_hits,
            "l2_hits": self._l2_hits,
            "misses": self._misses,
            "hit_rate": (self._l1_hits + self._l2_hits) / total if total else 0.0,
        }

    # -- L2 helpers ----------------------------------------------------------

    def _l2_get(self, key: str) -> Optional[T]:
        with self._l2_lock:
            row = self._l2_conn.execute(
                "SELECT value, expires_at FROM tiered_cache WHERE key=?", (key,)
            ).fetchone()
        if row is None:
            return None
        blob, expires_at = row
        if expires_at is not None and time.time() > expires_at:
            self.delete(key)
            return None
        return pickle.loads(blob)

    def _l2_set(self, key: str, value: T) -> None:
        expires_at = time.time() + self._l2_ttl if self._l2_ttl else None
        blob = pickle.dumps(value)
        with self._l2_lock:
            self._l2_conn.execute(
                "INSERT OR REPLACE INTO tiered_cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, blob, expires_at),
            )
            self._l2_conn.commit()

    def _l2_size(self) -> int:
        with self._l2_lock:
            row = self._l2_conn.execute("SELECT COUNT(*) FROM tiered_cache").fetchone()
        return row[0] if row else 0


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Simple rate limiter for API calls.
    
    Usage:
        >>> limiter = RateLimiter(calls_per_second=5)
        >>> for item in items:
        ...     with limiter:
        ...         api_call(item)
    """
    
    def __init__(self, calls_per_second: float = 10):
        self.min_interval = 1.0 / calls_per_second
        self._last_call = 0.0
        self._lock = threading.Lock()
    
    def __enter__(self):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call = time.time()
        return self
    
    def __exit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    # Cache
    "TTLCache",
    "TieredCache",
    "cached",
    # Profiling
    "profile",
    "profile_block",
    "get_profile_summary",
    # Batch processing
    "batch_process",
    "chunked",
    "parallel_map",
    # Memory
    "MemoryManager",
    "memory_guard",
    "optimize_dataframe",
    # Utilities
    "timed",
    "RateLimiter",
]
