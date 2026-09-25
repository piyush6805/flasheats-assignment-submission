# Demo runbook

Target length: 3-5 minutes.

1. Start with the client problem: late deliveries and unreliable ETAs.
2. Show `docs/source_map.md` and explain why SQL, files, and the paginated Dispatch API are all needed.
3. Run `python src/run_pipeline.py --run-date 2026-09-25` and point to API completeness, retries, raw-page preservation, and the processed partition.
4. Show Notebook 02 or `metric_evidence.csv`: 56.39% from the outcome layer versus 57.03% from incomplete raw timestamps.
5. Explain the judgement call: publish the outcome-based KPI provisionally, but keep reconciliation as a warning until the KPI owner confirms the contract.
6. Show Notebook 03 and the one-row-per-order `order_journey` model.
7. Close with the missing driver-arrival event and the recommendation to improve instrumentation before investing in an AI predictor.
