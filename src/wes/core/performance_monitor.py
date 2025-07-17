"""Performance monitoring and optimization for the application."""

import asyncio
import functools
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import psutil

from ..utils.logging_config import get_logger


@dataclass
class PerformanceMetric:
    """Container for performance metrics."""

    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class OperationMetrics:
    """Metrics for a specific operation."""

    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    memory_used: Optional[float] = None
    cpu_percent: Optional[float] = None

    def complete(self, success: bool = True, error: Optional[str] = None) -> None:
        """Mark operation as complete."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error = error

        # Capture resource usage
        process = psutil.Process()
        self.memory_used = process.memory_info().rss / 1024 / 1024  # MB
        self.cpu_percent = process.cpu_percent(interval=0.1)


class PerformanceMonitor:
    """Monitor and track application performance metrics."""

    def __init__(self, history_size: int = 1000) -> None:
        self.logger = get_logger(__name__)
        self.history_size = history_size

        # Metrics storage
        self._metrics: deque[PerformanceMetric] = deque(maxlen=history_size)
        self._operations: deque[OperationMetrics] = deque(maxlen=history_size)
        self._operation_stats: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"count": 0, "total_duration": 0, "errors": 0}
        )

        # Resource monitoring
        self._resource_monitor_active = False
        self._resource_history: deque[Dict[str, float]] = deque(maxlen=100)
        self._monitor_thread: Optional[threading.Thread] = None

        # Thresholds for alerts
        self.thresholds = {
            "memory_mb": 500,  # Alert if memory usage exceeds 500MB
            "cpu_percent": 80,  # Alert if CPU usage exceeds 80%
            "operation_duration": 10,  # Alert if operation takes > 10 seconds
            "error_rate": 0.1,  # Alert if error rate exceeds 10%
        }

        # Callbacks for alerts
        self._alert_callbacks: List[Callable] = []

    def start_resource_monitoring(self, interval: float = 5.0) -> None:
        """Start background resource monitoring."""
        if self._resource_monitor_active:
            return

        self._resource_monitor_active = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_resources, args=(interval,), daemon=True
        )
        self._monitor_thread.start()
        self.logger.info(f"Started resource monitoring (interval: {interval}s)")

    def stop_resource_monitoring(self) -> None:
        """Stop background resource monitoring."""
        self._resource_monitor_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("Stopped resource monitoring")

    def _monitor_resources(self, interval: float) -> None:
        """Background thread for resource monitoring."""
        process = psutil.Process()

        while self._resource_monitor_active:
            try:
                # Collect metrics
                metrics = {
                    "timestamp": datetime.now(),
                    "memory_mb": process.memory_info().rss / 1024 / 1024,
                    "cpu_percent": process.cpu_percent(interval=0.1),
                    "num_threads": process.num_threads(),
                    "open_files": len(process.open_files()),
                }

                self._resource_history.append(metrics)

                # Check thresholds
                if metrics["memory_mb"] > self.thresholds["memory_mb"]:
                    self._trigger_alert(
                        "high_memory", f"Memory usage: {metrics['memory_mb']:.1f}MB"
                    )

                if metrics["cpu_percent"] > self.thresholds["cpu_percent"]:
                    self._trigger_alert(
                        "high_cpu", f"CPU usage: {metrics['cpu_percent']:.1f}%"
                    )

            except Exception as e:
                self.logger.error(f"Resource monitoring error: {e}")

            time.sleep(interval)

    def track_operation(self, operation_name: str) -> OperationMetrics:
        """Start tracking an operation."""
        metric = OperationMetrics(operation_name=operation_name, start_time=time.time())
        return metric

    def complete_operation(self, metric: OperationMetrics) -> None:
        """Complete tracking an operation."""
        metric.complete()
        self._operations.append(metric)

        # Update statistics
        stats = self._operation_stats[metric.operation_name]
        stats["count"] += 1
        stats["total_duration"] += metric.duration or 0
        if not metric.success:
            stats["errors"] += 1

        # Check thresholds
        if metric.duration and metric.duration > self.thresholds["operation_duration"]:
            self._trigger_alert(
                "slow_operation", f"{metric.operation_name} took {metric.duration:.2f}s"
            )

        # Check error rate
        error_rate = stats["errors"] / stats["count"]
        if error_rate > self.thresholds["error_rate"]:
            self._trigger_alert(
                "high_error_rate",
                f"{metric.operation_name} error rate: {error_rate:.1%}",
            )

    def record_metric(
        self, name: str, value: float, unit: str, tags: Optional[Dict[str, str]] = None
    ):
        """Record a custom metric."""
        metric = PerformanceMetric(name=name, value=value, unit=unit, tags=tags or {})
        self._metrics.append(metric)

    def add_alert_callback(self, callback: Callable[[str, str], None]) -> None:
        """Add callback for performance alerts."""
        self._alert_callbacks.append(callback)

    def _trigger_alert(self, alert_type: str, message: str) -> None:
        """Trigger a performance alert."""
        self.logger.warning(f"Performance alert [{alert_type}]: {message}")

        for callback in self._alert_callbacks:
            try:
                callback(alert_type, message)
            except Exception as e:
                self.logger.error(f"Alert callback error: {e}")

    def get_operation_stats(
        self, operation_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get statistics for operations."""
        if operation_name:
            stats = self._operation_stats.get(operation_name, {})
            if stats and stats["count"] > 0:
                return {}

        # Return all stats
        all_stats = {}
        for op_name, stats in self._operation_stats.items():
            if stats["count"] > 0:
                all_stats[op_name] = {
                    "count": stats["count"],
                    "average_duration": stats["total_duration"] / stats["count"],
                    "total_duration": stats["total_duration"],
                    "error_count": stats["errors"],
                    "error_rate": stats["errors"] / stats["count"],
                }
        return all_stats

    def get_resource_summary(self) -> Dict[str, Any]:
        """Get summary of resource usage."""
        if not self._resource_history:
            return {}

        # Calculate averages
        total_memory = sum(r["memory_mb"] for r in self._resource_history)
        total_cpu = sum(r["cpu_percent"] for r in self._resource_history)
        count = len(self._resource_history)

        # Get current values
        latest = self._resource_history[-1]

        return {
            "cpu_percent": latest["cpu_percent"],
            "memory_percent": latest["memory_percent"],
            "disk_io": latest["disk_io"],
            "network_io": latest["network_io"]
        }

    def get_slow_operations(
        self, threshold: Optional[float] = None
    ) -> List[OperationMetrics]:
        """Get operations that exceeded duration threshold."""
        threshold = threshold or self.thresholds["operation_duration"]
        return [
            metric for metric in self._metrics 
            if metric.duration > threshold
        ]

    def clear_history(self) -> None:
        """Clear all collected metrics."""
        self._metrics.clear()
        self._operations.clear()
        self._operation_stats.clear()
        self._resource_history.clear()
        self.logger.info("Cleared performance history")


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def track_performance(operation_name: str) -> None:
    """Decorator to track function performance."""

    def decorator(func):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            metric = monitor.track_operation(operation_name)

            try:
                result = func(*args, **kwargs)
                monitor.complete_operation(metric)
                return result
            except Exception as e:
                metric.complete(success=False, error=str(e))
                monitor.complete_operation(metric)
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            metric = monitor.track_operation(operation_name)

            try:
                result = await func(*args, **kwargs)
                monitor.complete_operation(metric)
                return result
            except Exception as e:
                metric.complete(success=False, error=str(e))
                monitor.complete_operation(metric)
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class ResourceCache:
    """Simple LRU cache for expensive operations."""

    def __init__(self, max_size: int = 100, ttl: int = 300) -> None:
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._access_order: deque[str] = deque()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]

                # Check if expired
                if datetime.now() - timestamp > timedelta(seconds=self.ttl):
                    del self._cache[key]
                    self._access_order.remove(key)
                    return None

                # Update access order
                self._access_order.remove(key)
                self._access_order.append(key)

                return value

            return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        with self._lock:
            # Remove oldest if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                oldest = self._access_order.popleft()
                del self._cache[oldest]

            # Update cache
            self._cache[key] = (value, datetime.now())

            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)
