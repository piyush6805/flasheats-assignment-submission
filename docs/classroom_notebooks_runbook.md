# Local classroom notebooks runbook

The submission contains solved local versions of the three classroom notebooks:

- `notebooks/FlashEats_Class5_Local_Solved.ipynb` — source investigation, late-delivery analysis, customer evidence, API retrieval, and event observability.
- `notebooks/FlashEats_Class6_Local_Solved.ipynb` — validation contracts, KPI definitions, cross-source checks, freshness, and the publishability gate.
- `notebooks/FlashEats_Class7_Local_Solved.ipynb` — order lifecycle reconstruction, canonical order model, workflow metrics, and KPI linkage.

These notebooks use the canonical files already in this repository. They do not require a Colab upload or a ZIP file. The notebooks search the current folder and its parents for `data/raw/sqlite/flasheats.db`; opening them from the submission repository is the simplest option.

## One-time setup

From PowerShell, inside `flasheats-assignment-submission`:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ipykernel install --user --name flasheats-submission --display-name "Python (FlashEats Submission)"
```

In VS Code or Jupyter, select the kernel named `Python (FlashEats Submission)`.

## Recommended demo order

Run all cells in Class 5, then Class 6, then Class 7. Class 5 starts the local mock Dispatch API, retrieves all pages with retry handling, saves raw pages under `outputs/classroom_challenges/class5_raw_dispatch`, and shuts the API down at the end.

The notebooks also write small classroom-analysis artifacts under `outputs/classroom_challenges`. The main production-style pipeline remains separate and is run with:

```powershell
.\.venv\Scripts\python.exe src\run_pipeline.py --run-date 2026-09-25
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Five-minute explanation

1. Class 5 asks whether the late-delivery problem can be measured and whether the source systems support the claim.
2. Class 6 asks whether the data is safe enough to publish as a business KPI; the solved result is a transparent `WARN`, not an unqualified `PASS`.
3. Class 7 creates the smallest useful order-level workflow model and connects customer interactions and interventions to the late-delivery KPI.
4. The final decision is to improve instrumentation and resolve validation warnings before training an AI delay predictor.

If a notebook kernel becomes stuck, use **Kernel → Restart Kernel**, select the `Python (FlashEats Submission)` kernel again, and rerun all cells from the top. Do not run the API-start cell repeatedly without running the final cleanup cell or restarting the kernel.
