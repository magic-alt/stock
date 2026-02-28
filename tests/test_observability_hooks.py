"""
Tests for observability: TraceContext, Span, Tracer, MetricCollector.
"""
import time

from src.core.monitoring import (
    MetricCollector,
    Span,
    TraceContext,
    Tracer,
    get_metric_collector,
    get_tracer,
)


class TestTraceContext:
    def test_trace_context_creation(self):
        ctx = TraceContext(trace_id="t1", span_id="s1")
        assert ctx.trace_id == "t1"
        assert ctx.span_id == "s1"
        assert ctx.parent_span_id == ""
        assert ctx.baggage == {}

    def test_trace_context_with_baggage(self):
        ctx = TraceContext(trace_id="t1", span_id="s1", baggage={"key": "val"})
        assert ctx.baggage["key"] == "val"


class TestSpan:
    def test_span_nesting(self):
        parent = Span("parent")
        child = Span("child", trace_id=parent.trace_id, parent_span_id=parent.span_id)
        parent.children.append(child)

        assert child.parent_span_id == parent.span_id
        assert child.trace_id == parent.trace_id
        assert len(parent.children) == 1

    def test_span_timing(self):
        span = Span("test")
        time.sleep(0.01)
        span.end()
        assert span.end_time is not None
        assert span.duration_ms > 0

    def test_span_attributes(self):
        span = Span("test")
        span.set_attribute("key", "value")
        span.set_attribute("count", 42)
        assert span.attributes["key"] == "value"
        assert span.attributes["count"] == 42

    def test_span_to_dict(self):
        span = Span("test")
        span.set_attribute("k", "v")
        span.end()
        d = span.to_dict()
        assert d["name"] == "test"
        assert d["attributes"] == {"k": "v"}
        assert d["status"] == "ok"
        assert isinstance(d["duration_ms"], float)


class TestTracer:
    def test_start_span_returns_span(self):
        tracer = Tracer()
        span = tracer.start_span("test")
        assert isinstance(span, Span)
        assert span.name == "test"
        tracer.end_span()
        tracer.reset()

    def test_context_manager_records_duration(self):
        tracer = Tracer()
        with tracer.trace("op") as span:
            time.sleep(0.01)
        assert span.end_time is not None
        assert span.duration_ms > 0
        tracer.reset()

    def test_nested_spans_parent_child(self):
        tracer = Tracer()
        with tracer.trace("parent") as parent:
            with tracer.trace("child") as child:
                pass
        assert child.parent_span_id == parent.span_id
        assert child.trace_id == parent.trace_id
        assert len(parent.children) == 1
        tracer.reset()

    def test_exception_marks_span_error(self):
        tracer = Tracer()
        try:
            with tracer.trace("fail") as span:
                raise ValueError("boom")
        except ValueError:
            pass
        assert span.status == "error"
        assert span._error == "boom"
        tracer.reset()

    def test_get_completed_spans(self):
        tracer = Tracer()
        with tracer.trace("a"):
            pass
        with tracer.trace("b"):
            pass
        completed = tracer.get_completed_spans()
        assert len(completed) >= 2
        tracer.reset()


class TestMetricCollector:
    def test_counter_increment(self):
        mc = MetricCollector()
        mc.counter("requests", 1)
        mc.counter("requests", 2)
        export = mc.export()
        assert export["counters"]["requests"] == 3.0

    def test_gauge_set(self):
        mc = MetricCollector()
        mc.gauge("cpu", 45.0)
        mc.gauge("cpu", 60.0)
        export = mc.export()
        assert export["gauges"]["cpu"] == 60.0

    def test_histogram_record(self):
        mc = MetricCollector()
        for v in [10, 20, 30, 40, 50]:
            mc.histogram("latency", v)
        export = mc.export()
        h = export["histograms"]["latency"]
        assert h["count"] == 5
        assert h["min"] == 10
        assert h["max"] == 50

    def test_export_all_metrics(self):
        mc = MetricCollector()
        mc.counter("a", 1)
        mc.gauge("b", 2)
        mc.histogram("c", 3)
        export = mc.export()
        assert "counters" in export
        assert "gauges" in export
        assert "histograms" in export

    def test_collector_reset(self):
        mc = MetricCollector()
        mc.counter("x", 5)
        mc.reset()
        export = mc.export()
        assert export["counters"] == {}


class TestTracerSingleton:
    def test_tracer_singleton(self):
        t1 = get_tracer()
        t2 = get_tracer()
        assert t1 is t2

    def test_metric_collector_singleton(self):
        mc1 = get_metric_collector()
        mc2 = get_metric_collector()
        assert mc1 is mc2
