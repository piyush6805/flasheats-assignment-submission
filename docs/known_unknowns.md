# Known, unknown, assumptions, and limitations

## Known

- The complete canonical source bundle contains 1,600 unique orders.
- The outcome file contains 1,532 delivered orders, 68 cancelled orders, and 37 unknown delivered outcomes.
- The Dispatch API contains 1,600 order records and deliberately exercises pagination and transient failures.
- Customer support, app, interaction, intervention, restaurant-status, and driver-event sources can be joined to the order key when the key is present.

## Unknown

- Which team formally owns the published late-delivery KPI.
- Whether `order_outcomes.csv` or raw `orders` should be the authoritative KPI source.
- Whether the `late_flag` definition is exactly “any delay” for all historical rows.
- Whether intervention timing is early enough to be treated as a response rather than a consequence of delay.
- The true time when a driver arrives at a restaurant.

## Assumptions

- Cancelled orders do not belong in operational delivery performance.
- The outcome source is the provisional KPI layer because it supplies a complete one-row-per-order classification for 1,495 measurable delivered outcomes.
- Case and whitespace differences such as `Delivered`/`delivered` and `ready`/`READY` are representation issues and may be normalized for analysis.
- Customer and operational interactions are descriptive signals, not causal variables.

## Limitations

- Raw `orders` data has substantial missing promised ETAs, so independently reconstructing the KPI from that table is incomplete.
- Duplicate order records include conflicting attributes; selecting the first row is not a defensible final rule.
- Support tickets are not fully linked to orders.
- Restaurant status data contains duplicates, unknown values, and updates after pickup.
- Driver telemetry has GPS, assignment, pickup, and delivery events but no explicit restaurant-arrival event.
- The final pipeline is intentionally small and local; it is not Airflow/Spark/Kafka or enterprise observability. The copied `src/run_pipeline_reference.py` is retained only as Class 8 provenance.
