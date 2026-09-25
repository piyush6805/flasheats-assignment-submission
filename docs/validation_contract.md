# Validation contract

## Status meanings

- **PASS** - safe for the stated check and use case.
- **WARN** - usable with an explicit limitation or exclusion.
- **FAIL** - do not publish processed output.
- **UNKNOWN** - requires a business owner or source-system decision.

## Checks

| Check | Expected rule | Current evidence | Status | Action |
|---|---|---|---|---|
| Business grain | One row per `order_id` | 1,603 raw rows, 1,600 unique IDs; three duplicate IDs | WARN | Audit conflicting duplicates before final publish |
| Outcome completeness | Delivered outcome has classification | 1,495 measurable outcomes and 37 unknown outcomes | WARN | Report unknowns outside KPI denominator |
| Promised ETA availability | Raw order timestamps support KPI reconstruction | 790 missing `promised_eta` values | WARN | Use outcome source provisionally and reconcile |
| Chronology | Created ≤ pickup ≤ delivery | Promised-before-created and actual-before-pickup cases exist | WARN | Retain invalid records and report counts |
| Cross-source IDs | Non-null keys map to reference orders/entities | Core mappings are 100% for tested non-null keys | PASS | Continue monitoring |
| Support linkage | Tickets map to orders | Three tickets have no order ID | WARN | Retain tickets as unlinked customer evidence |
| Category semantics | Status/category values are canonical | Casing, whitespace, and representation variants exist | WARN | Normalize representation; confirm semantic mappings |
| KPI ownership | Late definition and authoritative source are approved | Stakeholders disagree in supplied definitions | UNKNOWN | Obtain Operations/Data Team approval |
| Dispatch completeness | Retrieved unique rows equal API total | API fixture reports 1,600 records | PASS when retrieval check passes | Preserve raw pages and page counts |

The final pipeline publishes the processed partition with an overall `WARN` gate because the source issues above are known and documented; hard failures such as missing required columns or stale data stop publication.

## KPI definitions

| Definition | Result | Use |
|---|---:|---|
| Any delay greater than 0 minutes | 843 / 1,495 = 56.39% | Provisional primary KPI |
| Delay greater than 10 minutes | 349 / 1,495 = 23.34% | Secondary meaningful-lateness metric |
| Raw order timestamps | 430 / 754 = 57.03% | Reconciliation check only until ETA completeness is resolved |
