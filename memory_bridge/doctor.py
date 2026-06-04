"""Memory health checks that avoid natural-language heuristics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

from .store import MemoryStore


@dataclass
class DoctorReport:
    issues: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def text(self) -> str:
        if self.ok:
            return "Memory doctor: OK. No lifecycle or schema issues found."
        return "Memory doctor found issues:\n" + "\n".join(f"- {issue}" for issue in self.issues)


def run_doctor(store: MemoryStore) -> DoctorReport:
    report = DoctorReport()
    active = store.list(status="active")
    buckets: Dict[str, List[str]] = defaultdict(list)

    for memory in active:
        buckets[f"{memory.slot}|{memory.scope.key()}"].append(memory.id)
        if len(memory.content) > 600:
            report.issues.append(
                f"{memory.id} content is long ({len(memory.content)} chars). Consider summarizing."
            )

    for key, ids in buckets.items():
        if len(ids) > 1:
            report.issues.append(f"multiple active memories for {key}: {', '.join(ids)}")

    return report
