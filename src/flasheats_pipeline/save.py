from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def _atomic_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as stream:
        stream.write(text)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def save_outputs(journey, metrics, evidence, validation_results, validation_gate, manifest, config, run_date, duplicate_rows=None):
    partition = config.output_root / f"run_date={run_date.isoformat()}"
    partition.mkdir(parents=True, exist_ok=True)

    journey_path = partition / "order_journey.csv"
    temporary_csv = partition / "order_journey.csv.tmp"
    journey.to_csv(temporary_csv, index=False)
    os.replace(temporary_csv, journey_path)
    _atomic_text(partition / "metrics.json", json.dumps(metrics, indent=2))
    evidence.to_csv(partition / "metric_evidence.csv", index=False)
    _atomic_text(partition / "validation_report.json", json.dumps({
        "gate": validation_gate,
        "checks": [result.as_dict() for result in validation_results],
    }, indent=2))
    _atomic_text(partition / "source_manifest.json", json.dumps(manifest, indent=2))
    if duplicate_rows is not None:
        duplicate_rows.to_csv(partition / "duplicate_order_quarantine.csv", index=False)
    summary = [
        "# FlashEats pipeline decision summary",
        "",
        f"Validation gate: **{validation_gate}**",
        "",
        f"Late delivery rate: **{metrics.get('late_delivery_rate_pct')}%** ({metrics.get('late_delivery_count')} / {metrics.get('measurable_deliveries')})",
        f"Meaningfully late over 10 minutes: **{metrics.get('meaningfully_late_rate_pct_gt_10_min')}%**",
        f"Median delay among late deliveries: **{metrics.get('median_delay_among_late_min')} minutes**",
        f"Median order-to-pickup duration: **{metrics.get('median_order_to_pickup_min')} minutes**",
        f"Customer friction rate: **{metrics.get('customer_friction_rate_pct')}%**",
        f"Intervention rate: **{metrics.get('intervention_rate_pct')}%**",
        "",
        "The KPI is provisional because the raw order timestamp reconstruction is incomplete and the validation report contains known warnings. Associations are descriptive, not causal.",
    ]
    _atomic_text(partition / "decision_summary.md", "\n".join(summary) + "\n")
    return {
        "partition": str(partition),
        "journey": str(journey_path),
        "metrics": str(partition / "metrics.json"),
        "evidence": str(partition / "metric_evidence.csv"),
        "validation": str(partition / "validation_report.json"),
        "manifest": str(partition / "source_manifest.json"),
        "quarantine": str(partition / "duplicate_order_quarantine.csv") if duplicate_rows is not None else None,
        "decision_summary": str(partition / "decision_summary.md"),
    }
