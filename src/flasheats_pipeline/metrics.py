import pandas as pd


def build_metrics(journey: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    measurable = journey[journey["delay_min"].notna()].copy()
    measurable["late_flag"] = pd.to_numeric(measurable["late_flag"], errors="coerce")
    measurable["delay_min"] = pd.to_numeric(measurable["delay_min"], errors="coerce")
    raw_measurable = journey[journey["actual_delivery_at"].notna() & journey["promised_eta"].notna()].copy()
    raw_measurable["raw_delay_min"] = (raw_measurable["actual_delivery_at"] - raw_measurable["promised_eta"]).dt.total_seconds() / 60

    late_count = int(measurable["late_flag"].eq(1).sum())
    measurable_count = int(len(measurable))
    metrics = {
        "orders_in_journey": int(len(journey)),
        "measurable_deliveries": measurable_count,
        "unknown_outcomes": int(journey["outcome_bucket"].eq("unknown").sum()),
        "late_delivery_count": late_count,
        "late_delivery_rate_pct": round(late_count / measurable_count * 100, 2) if measurable_count else None,
        "meaningfully_late_count_gt_10_min": int(measurable["delay_min"].gt(10).sum()),
        "meaningfully_late_rate_pct_gt_10_min": round(float(measurable["delay_min"].gt(10).mean() * 100), 2) if measurable_count else None,
        "median_delay_among_late_min": round(float(measurable.loc[measurable["late_flag"].eq(1), "delay_min"].median()), 2) if late_count else None,
        "median_order_to_pickup_min": round(float(journey["order_to_pickup_min"].median()), 2),
        "customer_friction_orders": int(measurable["has_customer_friction"].sum()),
        "customer_friction_rate_pct": round(float(measurable["has_customer_friction"].mean() * 100), 2) if measurable_count else None,
        "intervention_orders": int(measurable["has_intervention"].sum()),
        "intervention_rate_pct": round(float(measurable["has_intervention"].mean() * 100), 2) if measurable_count else None,
        "raw_timestamp_measurable_deliveries": int(len(raw_measurable)),
        "raw_timestamp_late_rate_pct": round(float(raw_measurable["raw_delay_min"].gt(0).mean() * 100), 2) if len(raw_measurable) else None,
    }

    evidence = pd.DataFrame([
        ["late_delivery_rate_pct", late_count, measurable_count, metrics["late_delivery_rate_pct"], "late_flag = 1 / measurable outcome rows", "Primary KPI; outcome source"],
        ["meaningfully_late_rate_pct_gt_10_min", metrics["meaningfully_late_count_gt_10_min"], measurable_count, metrics["meaningfully_late_rate_pct_gt_10_min"], "delay_min > 10 / measurable outcome rows", "Secondary severity KPI"],
        ["median_delay_among_late_min", None, late_count, metrics["median_delay_among_late_min"], "median delay_min where late_flag = 1", "Late-delivery severity"],
        ["median_order_to_pickup_min", None, int(journey["order_to_pickup_min"].notna().sum()), metrics["median_order_to_pickup_min"], "median pickup_at - created_at", "Preparation/handoff proxy"],
        ["customer_friction_rate_pct", metrics["customer_friction_orders"], measurable_count, metrics["customer_friction_rate_pct"], "orders with support/app interaction signal", "Customer experience"],
        ["intervention_rate_pct", metrics["intervention_orders"], measurable_count, metrics["intervention_rate_pct"], "orders with at least one intervention", "Operational response"],
    ], columns=["metric", "numerator", "denominator", "value", "formula", "interpretation"])
    return metrics, evidence
