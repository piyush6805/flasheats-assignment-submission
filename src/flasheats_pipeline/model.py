import pandas as pd


def _aggregate_sources(sources):
    app = sources["customer_app_actions"]
    interactions = sources["customer_interactions"]
    tickets = sources["support_tickets"]
    interventions = sources["order_interventions"]
    events = sources["order_events"]
    statuses = sources["restaurant_status"].copy()

    app_summary = app.groupby("order_id").agg(
        app_action_count=("action_id", "count"),
        cancel_attempted=("action_type", lambda s: int(s.eq("CANCEL_ATTEMPTED").any())),
        support_opened=("action_type", lambda s: int(s.eq("SUPPORT_OPENED").any())),
    ).reset_index()
    interaction_summary = interactions.groupby("order_id").agg(
        interaction_count=("interaction_id", "count"),
        support_interaction=("interaction_type", lambda s: int(s.eq("SUPPORT_TICKET").any())),
    ).reset_index()
    linked_tickets = tickets[tickets["order_id"].notna() & tickets["order_id"].astype(str).str.strip().ne("")]
    ticket_summary = linked_tickets.groupby("order_id").agg(
        ticket_count=("ticket_id", "count"),
    ).reset_index()
    intervention_summary = interventions.groupby("order_id").agg(
        intervention_count=("intervention_id", "count"),
        intervention_types=("intervention_type", lambda s: ",".join(sorted(set(s)))),
    ).reset_index()
    event_summary = events.groupby("order_id").agg(
        event_count=("event_id", "count"),
        reassignment_event_count=("event_type", lambda s: int(s.eq("DRIVER_REASSIGNMENT").sum())),
    ).reset_index()
    statuses["status_norm"] = statuses["status"].astype(str).str.strip().str.lower()
    status_summary = statuses.groupby("order_id").agg(
        restaurant_status_updates=("status", "count"),
        last_restaurant_status=("status_norm", "last"),
    ).reset_index()

    driver_events = sources["driver_events"]
    driver_summary = driver_events.groupby("order_id").agg(
        driver_event_count=("type", "count"),
        gps_ping_count=("type", lambda s: int(s.eq("gps_ping").sum())),
        driver_delivered_event=("type", lambda s: int(s.eq("delivered").any())),
    ).reset_index()
    return [app_summary, interaction_summary, ticket_summary, intervention_summary, event_summary, status_summary, driver_summary]


def build_order_journey(sources, dispatch, logger):
    orders = sources["orders"].copy()
    for column in ["created_at", "promised_eta", "pickup_at", "actual_delivery_at"]:
        orders[column] = pd.to_datetime(orders[column], errors="coerce")
    duplicate_ids = orders.loc[orders["order_id"].duplicated(False), "order_id"].unique().tolist()
    orders = orders.drop_duplicates("order_id", keep="first").copy()
    orders["final_status"] = orders["final_status"].astype(str).str.strip().str.lower()
    orders["traffic_bucket"] = orders["traffic_bucket"].astype(str).str.strip().str.lower()

    outcomes = sources["order_outcomes"].copy()
    outcomes["late_flag"] = pd.to_numeric(outcomes["late_flag"], errors="coerce")
    outcomes["delay_min"] = pd.to_numeric(outcomes["delay_min"], errors="coerce")
    journey = orders.merge(outcomes, on="order_id", how="left", suffixes=("", "_outcome"))
    journey = journey.merge(dispatch[[
        column for column in ["order_id", "current_delivery_eta", "assigned_driver_id", "driver_id", "original_driver_id", "reassigned_at", "eta_model_version", "dispatch_status"]
        if column in dispatch.columns
    ]], on="order_id", how="left", suffixes=("", "_dispatch"))

    for summary in _aggregate_sources(sources):
        journey = journey.merge(summary, on="order_id", how="left")

    numeric_defaults = [
        "app_action_count", "cancel_attempted", "support_opened", "interaction_count",
        "support_interaction", "ticket_count", "intervention_count", "event_count",
        "reassignment_event_count", "restaurant_status_updates", "driver_event_count",
        "gps_ping_count", "driver_delivered_event",
    ]
    for column in numeric_defaults:
        if column in journey:
            journey[column] = journey[column].fillna(0).astype(int)

    journey["order_to_pickup_min"] = (journey["pickup_at"] - journey["created_at"]).dt.total_seconds() / 60
    journey["transit_min"] = (journey["actual_delivery_at"] - journey["pickup_at"]).dt.total_seconds() / 60
    journey["has_customer_friction"] = (
        journey["support_opened"].gt(0)
        | journey["ticket_count"].gt(0)
        | journey["support_interaction"].gt(0)
    ).astype(int)
    journey["has_intervention"] = journey["intervention_count"].gt(0).astype(int)
    journey["duplicate_order_source_flag"] = journey["order_id"].isin(duplicate_ids).astype(int)
    journey["driver_arrival_observed"] = 0

    journey = journey.merge(sources["restaurants"][["restaurant_id", "cuisine"]], on="restaurant_id", how="left")
    journey = journey.merge(sources["drivers"][["driver_id", "vehicle_type", "experience_months"]], on="driver_id", how="left")
    if not journey["order_id"].is_unique:
        raise ValueError("order_journey lost its one-row-per-order grain")
    logger.info("Built order_journey | rows=%s duplicate_source_flags=%s", len(journey), int(journey["duplicate_order_source_flag"].sum()))
    return journey
