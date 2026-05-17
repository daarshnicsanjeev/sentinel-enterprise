import threading

_lock = threading.Lock()
_counters: dict[str, float] = {}


def _format_key(name: str, labels: dict | None) -> str:
    if not labels:
        return name
    label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{label_str}}}"


def increment(name: str, value: float = 1.0, labels: dict | None = None) -> None:
    key = _format_key(name, labels)
    with _lock:
        _counters[key] = _counters.get(key, 0.0) + value


def render_prometheus() -> str:
    with _lock:
        if not _counters:
            return "\n"
        lines = [f"{key} {val}" for key, val in sorted(_counters.items())]
        return "\n".join(lines) + "\n"
