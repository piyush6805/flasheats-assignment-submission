# Source map

The source map connects each business question to the system used for evidence. Ownership is inferred from the source role because the supplied files do not contain formal ownership metadata.

| Business information | Source | Grain | Working authority | Retrieval | Important gap |
|---|---|---|---|---|---|
| Order identity and lifecycle timestamps | SQLite `orders` | Intended one row/order | Order platform | SQL | Duplicate IDs and missing promised ETA |
| Customers, restaurants, drivers | SQLite dimension tables | One row/entity | Master/reference data | SQL | No explicit ownership metadata |
| Outcome and late classification | `order_outcomes.csv` | One row/order | Provisional KPI source | CSV | Does not fully reconcile to raw order timestamps |
| Dispatch assignment and current ETA | Dispatch API | One record/order | Dispatch system | Paginated HTTP API | Current snapshot, not full history |
| Lifecycle and intervention events | `order_events.csv` | One row/event | Order event log | CSV | Captures recorded events only |
| Driver movement | `driver_events.json` | Nested driver/event | Driver telemetry | JSON file | No explicit arrival-at-restaurant event |
| Customer app behaviour | `customer_app_actions.csv` | One row/action | Customer app | CSV | Behaviour is not a causal explanation |
| Customer interactions | `customer_interactions.csv` | One row/interaction | Customer interaction system | CSV | Interaction coverage is partial |
| Customer complaints | `support_tickets.csv` | One row/ticket | Support system | CSV | Three tickets are not linked to an order |
| Operational interventions | `order_interventions.csv` | One row/intervention | Operations/dispatch/support | CSV | Alternate supplied copy has conflicting schema and records |
| Restaurant operating status | `restaurant_status.csv` | One row/status update | Restaurant operations | CSV | Category and timing inconsistencies |

## Retrieval completeness

- SQL extraction inventories all four SQLite tables.
- CSV and JSON files are loaded from immutable raw copies.
- Dispatch retrieval follows pagination, retries transient HTTP 500/429 errors, preserves each successful page, and checks the reported total.
- The expected Dispatch record count is 1,600 unique orders.
