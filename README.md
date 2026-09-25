# FlashEats Operations Reliability Submission

## Problem

FlashEats leadership reports that late deliveries are increasing and that customer ETAs are unreliable. This project reconstructs the order workflow from multiple operational systems, validates the late-delivery KPI, identifies where customer friction and interventions appear in the journey, and prepares a repeatable data foundation for operational decisions.

## Project KPI

The provisional KPI is **Late Delivery Rate**:

```text
late delivered outcomes / delivered outcomes with a non-null outcome classification
```

The current outcome source contains 843 late deliveries out of 1,495 measurable delivered outcomes: **56.39%**. Cancelled orders are excluded and 37 unknown outcomes are reported separately.

The raw `orders` table produces a different result because 790 of the 1,600 canonical orders have no `promised_eta`. The discrepancy is a validation warning, not something silently corrected.

## Canonical source decision

`data/raw` is copied from `flasheats-classroom-pack-main`, which contains the complete Class 4-7 source set. The Class 8 project was used as a pipeline reference under `src/`.

The alternate `order_interventions.csv` from the separate data-pipeline folder is deliberately not included because it is a different 260-row dataset with a different schema. The canonical classroom file has 430 intervention records.

## Repository layout

```text
data/raw/sqlite/       SQLite source database
data/raw/files/        CSV and JSON source files
data/raw/api/source/   Dispatch API fixture
data/raw/api/          Preserved API retrieval runs
notebooks/             Reproducible retrieval, validation, modelling, and reliability work
outputs/               Derived order journey and evidence tables
src/                   Final pipeline package, mock API, and Class 8 reference code
docs/                  Source, model, validation, and limitation documentation
```

## Notebook order

1. `notebooks/01_retrieve_and_profile.ipynb` - retrieve SQL/files and paginated Dispatch data, preserve raw API pages, and profile source grains.
2. `notebooks/02_validate_and_define_kpi.ipynb` - execute the validation contract and compare KPI definitions.
3. `notebooks/03_model_workflow_and_metrics.ipynb` - build the one-row-per-order `order_journey` model and calculate KPI-linked metrics.
4. `notebooks/04_pipeline_reliability_demo.ipynb` - record completeness, validation, retry, raw-preservation, and idempotency checks.

## Setup

```bash
python -m pip install -r requirements.txt
python src/run_pipeline.py --run-date 2026-09-25
jupyter notebook
```

Run notebooks from the repository root. Notebook 01 starts the local mock Dispatch API when it is not already running. The API fixture and launcher are in `src/`.

## Current outputs

The pipeline writes a run-date partition under `outputs/processed/` containing:

- `order_journey.csv`
- `metrics.json`
- `metric_evidence.csv`
- `validation_report.json`
- `source_manifest.json`
- `duplicate_order_quarantine.csv`
- `decision_summary.md`

Notebook 03 also writes:

- `outputs/order_journey.csv`
- `outputs/metric_evidence.csv`
- `outputs/intervention_comparison.csv`

The current workflow model contains 1,600 unique order rows. The pipeline completes with a WARN gate because known source-quality issues are retained and reported. All associations are descriptive; intervention or customer-contact differences do not establish causation.

## Decision supported

The output supports an Operations/Data Team decision about whether the late-delivery KPI is safe to publish and which workflow signals deserve operational investigation before investing in an AI delay-prediction system.

The copied `src/run_pipeline_reference.py` is retained only as Class 8 provenance. Use `src/run_pipeline.py` for the finished full-source pipeline.

See `docs/known_unknowns.md` before using the KPI for external reporting.
