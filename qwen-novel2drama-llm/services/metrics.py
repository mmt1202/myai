from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetricSample:
    name: str
    value: float
    labels: dict[str, str] | None = None
    help_text: str | None = None
    metric_type: str = "gauge"


def escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def render_labels(labels: dict[str, str] | None) -> str:
    if not labels:
        return ""
    pairs = [f'{key}="{escape_label(str(value))}"' for key, value in sorted(labels.items())]
    return "{" + ",".join(pairs) + "}"


def render_prometheus(samples: list[MetricSample]) -> str:
    lines: list[str] = []
    emitted: set[str] = set()
    for sample in samples:
        if sample.name not in emitted:
            if sample.help_text:
                lines.append(f"# HELP {sample.name} {sample.help_text}")
            lines.append(f"# TYPE {sample.name} {sample.metric_type}")
            emitted.add(sample.name)
        lines.append(f"{sample.name}{render_labels(sample.labels)} {float(sample.value)}")
    return "\n".join(lines) + "\n"


def runtime_metric_samples(*, readiness: dict[str, Any], queue: dict[str, Any], started_at: float | None = None) -> list[MetricSample]:
    now = time.time()
    components = readiness.get("components") or {}
    samples = [
        MetricSample("foundation_ready", 1.0 if readiness.get("status") == "ok" else 0.0, help_text="Foundation readiness status as 1/0."),
        MetricSample("foundation_uptime_seconds", now - float(started_at or now), help_text="Process uptime seconds."),
    ]
    for name, component in components.items():
        status = component.get("status")
        value = 1.0 if status == "ok" else 0.0
        samples.append(MetricSample("foundation_component_ok", value, labels={"component": str(name), "status": str(status)}, help_text="Foundation component status."))
    counts = queue.get("counts") or {}
    for status, count in counts.items():
        samples.append(MetricSample("foundation_agent_queue_runs", float(count or 0), labels={"status": str(status)}, help_text="Agent queue run counts by status."))
    samples.append(MetricSample("foundation_agent_queue_dead_letter", float(queue.get("dead_letter_count") or 0), help_text="Agent dead letter count."))
    return samples
