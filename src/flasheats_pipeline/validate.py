from dataclasses import dataclass, asdict
from datetime import date
import pandas as pd


@dataclass
class CheckResult:
    check: str
    status: str
    detail: str
    action: str = ""

    def as_dict(self):
        return asdict(self)


class ValidationError(ValueError):
    pass


ORDER_REQUIRED = {
    "order_id", "customer_id", "restaurant_id", "driver_id", "created_at",
    "promised_eta", "pickup_at", "actual_delivery_at", "final_status",
}
OUTCOME_REQUIRED = {"order_id", "final_status_norm", "delivered_flag", "late_flag", "delay_min", "outcome_bucket"}
DISPATCH_REQUIRED = {"order_id", "current_delivery_eta", "dispatch_status"}


def _required_columns(frame, columns, name):
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValidationError(f"{name} missing required columns: {missing}")
    return CheckResult(f"{name}.required_columns", "PASS", f"{len(columns)} required columns present")


def _coverage(label, values, target_values):
    values = pd.Series(values).dropna().astype(str).str.strip()
    if values.empty:
        return CheckResult(label, "WARN", "no non-null keys to check", "Investigate source completeness")
    matched = values.isin(set(pd.Series(target_values).dropna().astype(str).str.strip()))
    status = "PASS" if matched.all() else "WARN"
    return CheckResult(label, status, f"coverage={matched.mean() * 100:.2f}% unmapped={int((~matched).sum())}")


def run_validations(sources, dispatch, run_date: date, max_age_days: int):
    orders = sources["orders"].copy()
    outcomes = sources["order_outcomes"].copy()
    results = [
        _required_columns(orders, ORDER_REQUIRED, "orders"),
        _required_columns(outcomes, OUTCOME_REQUIRED, "order_outcomes"),
        _required_columns(dispatch, DISPATCH_REQUIRED, "dispatch"),
    ]

    duplicate_ids = orders.loc[orders["order_id"].duplicated(False), "order_id"].nunique()
    duplicate_rows = int(orders["order_id"].duplicated(False).sum())
    results.append(CheckResult(
        "orders.order_id_uniqueness",
        "WARN" if duplicate_rows else "PASS",
        f"duplicate_order_ids={duplicate_ids} duplicate_rows_involved={duplicate_rows}",
        "Quarantine conflicting duplicates; do not silently choose first row" if duplicate_rows else "",
    ))

    status = orders["final_status"].astype(str).str.strip().str.lower()
    delivered_missing_actual = int((status.eq("delivered") & orders["actual_delivery_at"].isna()).sum())
    results.append(CheckResult(
        "orders.delivered_completion_timestamp",
        "WARN" if delivered_missing_actual else "PASS",
        f"delivered_rows_missing_actual_delivery_at={delivered_missing_actual}",
        "Exclude from raw timestamp KPI and report separately",
    ))

    for column in ["created_at", "promised_eta", "pickup_at", "actual_delivery_at"]:
        orders[column] = pd.to_datetime(orders[column], errors="coerce")
    chronology_issues = {
        "promised_before_created": int((orders["promised_eta"] < orders["created_at"]).sum()),
        "pickup_before_created": int((orders["pickup_at"] < orders["created_at"]).sum()),
        "actual_before_pickup": int((orders["actual_delivery_at"] < orders["pickup_at"]).sum()),
    }
    chronology_total = sum(chronology_issues.values())
    results.append(CheckResult(
        "orders.timestamp_chronology",
        "WARN" if chronology_total else "PASS",
        str(chronology_issues),
        "Retain invalid records but exclude affected duration calculations",
    ))

    latest_created = orders["created_at"].max()
    if pd.isna(latest_created):
        raise ValidationError("orders freshness failed: no parseable created_at values")
    age_days = (pd.Timestamp(run_date) - latest_created.normalize()).days
    if age_days > max_age_days:
        raise ValidationError(f"orders data is stale: age_days={age_days} allowed={max_age_days}")
    results.append(CheckResult("orders.freshness", "PASS", f"latest_created_at={latest_created} age_days={age_days}"))

    outcome_dupes = int(outcomes["order_id"].duplicated().sum())
    results.append(CheckResult(
        "order_outcomes.order_id_uniqueness",
        "FAIL" if outcome_dupes else "PASS",
        f"duplicate_rows={outcome_dupes}",
    ))

    results.extend([
        _coverage("orders.customer_id_to_customers", orders["customer_id"], sources["customers"]["customer_id"]),
        _coverage("orders.driver_id_to_drivers", orders["driver_id"], sources["drivers"]["driver_id"]),
        _coverage("orders.restaurant_id_to_restaurants", orders["restaurant_id"], sources["restaurants"]["restaurant_id"]),
        _coverage("order_outcomes.order_id_to_orders", outcomes["order_id"], orders["order_id"]),
        _coverage("dispatch.order_id_to_orders", dispatch["order_id"], orders["order_id"]),
    ])

    unlinked_tickets = sources["support_tickets"]["order_id"].isna() | sources["support_tickets"]["order_id"].astype(str).str.strip().eq("")
    results.append(CheckResult(
        "support_tickets.order_linkage",
        "WARN" if int(unlinked_tickets.sum()) else "PASS",
        f"unlinked_tickets={int(unlinked_tickets.sum())}",
        "Retain as unlinked customer evidence",
    ))

    expected_dispatch = set(orders["order_id"].dropna())
    actual_dispatch = set(dispatch["order_id"].dropna())
    missing_dispatch = expected_dispatch - actual_dispatch
    results.append(CheckResult(
        "dispatch.order_set_completeness",
        "PASS" if not missing_dispatch else "FAIL",
        f"expected_orders={len(expected_dispatch)} received_orders={len(actual_dispatch)} missing={len(missing_dispatch)}",
    ))

    return results


def validation_status(results):
    statuses = {result.status for result in results}
    if "FAIL" in statuses:
        return "FAIL"
    if "UNKNOWN" in statuses or "WARN" in statuses:
        return "WARN"
    return "PASS"
