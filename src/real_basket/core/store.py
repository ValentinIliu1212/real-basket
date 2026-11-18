"""File-based data store with provenance and audit trail, plus memory across runs.

Layout (git-ignored):
    data_store/
        memory.json                     source reliability + recent run summaries
        runs/<run_id>/
            run.json                    run record (plan, decisions, results, report, status)
            audit.jsonl                 every decision of every agent / guardrail
            raw/<dataset>_<n>_<source>.json   raw snapshot of each fetch attempt
            dataset.json                accepted rows + weights + hash (input of the calculation)
            report.md                   published report
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from real_basket.core.engine import dataset_hash
from real_basket.core.settings import get_settings
from real_basket.schemas.flow import AuditEvent, Row

_AUDIT_LOCK = threading.Lock()

class DataStore:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or get_settings().DATA_DIR)
        (self.root / "runs").mkdir(parents=True, exist_ok=True)

    # --- runs ---------------------------------------------------------------------------------
    @staticmethod
    def new_run_id() -> str:
        return f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"

    def run_dir(self, run_id: str) -> Path:
        d = self.root / "runs" / run_id
        (d / "raw").mkdir(parents=True, exist_ok=True)
        return d

    def save_run(self, run_id: str, record: dict) -> None:
        _write_json(self.run_dir(run_id) / "run.json", record)

    def load_run(self, run_id: str) -> dict:
        return json.loads((self.root / "runs" / run_id / "run.json").read_text(encoding="utf-8"))

    def list_runs(self) -> list[dict]:
        runs = []
        for f in sorted((self.root / "runs").glob("*/run.json"), reverse=True):
            try:
                runs.append(json.loads(f.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return runs

    def write_text(self, run_id: str, name: str, text: str) -> Path:
        path = self.run_dir(run_id) / name
        path.write_text(text, encoding="utf-8")
        return path

    # --- provenance -----------------------------------------------------------------------------
    def save_raw(self, run_id: str, dataset: str, source: str, attempt: int, rows: list[Row]) -> Path:
        path = self.run_dir(run_id) / "raw" / f"{dataset}_{attempt}_{source}.json"
        _write_json(path, [r.model_dump() for r in rows])
        return path

    def save_dataset(self, run_id: str, rows: list[Row], weights: dict[str, float]) -> str:
        h = dataset_hash(rows, weights)
        _write_json(self.run_dir(run_id) / "dataset.json",
                    {"hash": h, "weights": weights, "rows": [r.model_dump() for r in rows]})
        return h

    def load_dataset(self, run_id: str) -> tuple[list[Row], dict[str, float]]:
        data = json.loads((self.root / "runs" / run_id / "dataset.json").read_text(encoding="utf-8"))
        return [Row(**r) for r in data["rows"]], data["weights"]

    # --- audit ----------------------------------------------------------------------------------
    def append_audit(self, run_id: str, event: AuditEvent) -> None:
        # Strands executes parallel tool calls in threads: serialise writes so lines never interleave.
        line = event.model_dump_json() + "\n"
        with _AUDIT_LOCK, (self.run_dir(run_id) / "audit.jsonl").open("a", encoding="utf-8") as f:
            f.write(line)

    def load_audit(self, run_id: str) -> list[dict]:
        path = self.root / "runs" / run_id / "audit.jsonl"
        if not path.exists():
            return []
        events = []
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:  # tolerate lines corrupted by older, unlocked versions
                events.append({"ts": "", "actor": "system", "action": "corrupt_audit_line",
                               "detail": {"line": n, "raw": line[:200]}})
        return events


class Memory:
    """Source reliability (Laplace-smoothed success rate blended with a prior) + recent runs."""

    def __init__(self, store: DataStore):
        self.path = store.root / "memory.json"
        self.data = (json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists()
                     else {"sources": {}, "runs": []})

    def record_source(self, source: str, ok: bool) -> None:
        s = self.data["sources"].setdefault(source, {"ok": 0, "fail": 0})
        s["ok" if ok else "fail"] += 1

    def reliability(self, source: str, prior: float = 0.8) -> float:
        s = self.data["sources"].get(source, {"ok": 0, "fail": 0})
        return round((s["ok"] + 2 * prior) / (s["ok"] + s["fail"] + 2), 2)

    def add_run(self, summary: dict, keep: int = 20) -> None:
        self.data["runs"] = ([summary] + self.data["runs"])[:keep]

    def recent_runs(self, n: int = 5) -> list[dict]:
        return self.data["runs"][:n]

    def save(self) -> None:
        _write_json(self.path, self.data)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
