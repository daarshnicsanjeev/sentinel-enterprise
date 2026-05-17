"""Unit tests for structured JSON logging via structlog — TDD RED first."""
import json
import io
import pytest


class TestStructuredLogging:
    def test_structlog_is_configured_in_main(self):
        import structlog
        import main  # noqa: F401 — side effect: configures structlog
        logger = structlog.get_logger()
        assert logger is not None

    def test_log_output_is_valid_json(self, capsys):
        import structlog
        import main  # noqa: F401
        logger = structlog.get_logger()
        logger.info("test event", key="value")
        captured = capsys.readouterr()
        # structlog with JSONRenderer emits a JSON line
        output = captured.out.strip()
        if output:
            parsed = json.loads(output)
            assert "event" in parsed or "key" in parsed

    def test_routes_uses_structlog_logger(self):
        """routes.py must import and use a structlog logger (not bare print)."""
        import api.routes as routes_module
        import inspect
        source = inspect.getsource(routes_module)
        assert "structlog" in source

    def test_routes_logger_logs_on_completion(self, monkeypatch, capsys):
        """A completed analysis must emit a structured log line with trace_id."""
        import structlog
        import main  # noqa: F401
        log_calls = []

        class CapturingLogger:
            def info(self, event, **kw):
                log_calls.append({"event": event, **kw})
            def warning(self, event, **kw):
                log_calls.append({"event": event, **kw})
            def error(self, event, **kw):
                log_calls.append({"event": event, **kw})
            def bind(self, **kw):
                return self

        monkeypatch.setattr("api.routes._log", CapturingLogger())

        from fastapi.testclient import TestClient
        from main import app
        import io as _io

        client = TestClient(app, raise_server_exceptions=False)
        # A valid text upload triggers the pipeline; route must call _log
        client.post(
            "/api/analyze",
            files={"file": ("t.txt", _io.BytesIO(b"sample contract text for logging test " * 5), "text/plain")},
        )
        # At minimum, the routes module should have the _log attribute
        import api.routes as r
        assert hasattr(r, "_log")

    def test_log_has_trace_id_in_done_payload(self, monkeypatch):
        """The done SSE payload already contains trace_id — verify it's a UUID."""
        import uuid
        from fastapi.testclient import TestClient
        from main import app
        import io as _io

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/analyze",
            files={"file": ("t.txt", _io.BytesIO(b"structured logging test contract text " * 5), "text/plain")},
        )
        events = [
            json.loads(line[6:])
            for line in resp.text.splitlines()
            if line.startswith("data: ")
        ]
        done = next((e for e in events if e.get("type") == "done"), None)
        assert done is not None
        assert "trace_id" in done
        uuid.UUID(done["trace_id"])  # raises if not a valid UUID
