"""
Unit tests for data/metrics.py — Prometheus-compatible counter store.

TDD spec: the metrics module must accumulate counters thread-safely
and render them in Prometheus plaintext format.
"""
import pytest


class TestMetricsIncrement:
    def setup_method(self):
        import data.metrics as m
        m._counters.clear()

    def test_increment_adds_to_counter(self):
        import data.metrics as m
        m.increment("sentinel_analyses_total", labels={"decision": "APPROVED"})
        assert m._counters.get('sentinel_analyses_total{decision="APPROVED"}', 0) == 1.0

    def test_increment_accumulates(self):
        import data.metrics as m
        m.increment("sentinel_analyses_total", labels={"decision": "REJECTED"})
        m.increment("sentinel_analyses_total", labels={"decision": "REJECTED"})
        assert m._counters.get('sentinel_analyses_total{decision="REJECTED"}', 0) == 2.0

    def test_increment_custom_value(self):
        import data.metrics as m
        m.increment("sentinel_duration_seconds", value=1.5)
        assert m._counters.get("sentinel_duration_seconds", 0) == 1.5

    def test_increment_no_labels(self):
        import data.metrics as m
        m.increment("sentinel_requests_total")
        assert m._counters.get("sentinel_requests_total", 0) == 1.0

    def test_multiple_label_values_tracked_separately(self):
        import data.metrics as m
        m.increment("sentinel_analyses_total", labels={"decision": "APPROVED"})
        m.increment("sentinel_analyses_total", labels={"decision": "REJECTED"})
        assert m._counters.get('sentinel_analyses_total{decision="APPROVED"}', 0) == 1.0
        assert m._counters.get('sentinel_analyses_total{decision="REJECTED"}', 0) == 1.0


class TestMetricsRender:
    def setup_method(self):
        import data.metrics as m
        m._counters.clear()

    def test_render_prometheus_returns_string(self):
        import data.metrics as m
        result = m.render_prometheus()
        assert isinstance(result, str)

    def test_render_empty_counters_returns_newline(self):
        import data.metrics as m
        result = m.render_prometheus()
        assert result == "\n"

    def test_render_includes_counter_name(self):
        import data.metrics as m
        m.increment("sentinel_analyses_total")
        result = m.render_prometheus()
        assert "sentinel_analyses_total" in result

    def test_render_includes_counter_value(self):
        import data.metrics as m
        m.increment("sentinel_analyses_total", value=3.0)
        result = m.render_prometheus()
        assert "3.0" in result

    def test_render_label_format(self):
        import data.metrics as m
        m.increment("sentinel_analyses_total", labels={"decision": "APPROVED"})
        result = m.render_prometheus()
        assert 'sentinel_analyses_total{decision="APPROVED"}' in result

    def test_render_ends_with_newline(self):
        import data.metrics as m
        m.increment("sentinel_analyses_total")
        result = m.render_prometheus()
        assert result.endswith("\n")


class TestLabelEscaping:
    def test_escape_newline_in_label(self):
        import data.metrics as m
        m._counters.clear()
        m.increment("sentinel_analyses_total", labels={"decision": "APPROVED\nfake"})
        result = m.render_prometheus()
        assert "\n" not in result.split("\n")[0].split("=")[1]  # no raw newline in label value

    def test_escape_backslash_in_label(self):
        from data.metrics import _escape_label_value
        assert _escape_label_value("path\\file") == "path\\\\file"

    def test_escape_quote_in_label(self):
        from data.metrics import _escape_label_value
        assert _escape_label_value('say "hi"') == 'say \\"hi\\"'

    def test_escape_newline_char(self):
        from data.metrics import _escape_label_value
        assert _escape_label_value("a\nb") == "a\\nb"

    def test_escape_all_three(self):
        from data.metrics import _escape_label_value
        assert _escape_label_value('a\nb"c\\d') == 'a\\nb\\"c\\\\d'

    def test_clean_label_unchanged(self):
        from data.metrics import _escape_label_value
        assert _escape_label_value("APPROVED") == "APPROVED"
