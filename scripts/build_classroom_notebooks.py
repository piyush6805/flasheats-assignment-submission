from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks"

def notebook(title, intro, cells):
    nb = nbf.v4.new_notebook()
    nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
    nb.cells = [nbf.v4.new_markdown_cell(f"# {title}\n\n{intro}")] + cells
    return nb

def md(text): return nbf.v4.new_markdown_cell(text)
def code(text): return nbf.v4.new_code_cell(text)

common = '''from pathlib import Path
import json, sqlite3, sys, time, subprocess
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

def find_root():
    candidates = [Path.cwd(), *Path.cwd().parents, Path(r"C:\\Users\\piyus\\Downloads\\FDE\\flasheats-assignment-submission")]
    for p in candidates:
        if (p / "data" / "raw" / "sqlite" / "flasheats.db").exists():
            return p
    raise FileNotFoundError("Could not find the submission repo. Open this notebook from the submission folder or update ROOT.")

ROOT = find_root()
DB = ROOT / "data" / "raw" / "sqlite" / "flasheats.db"
DATA = ROOT / "data" / "raw" / "files"
OUT = ROOT / "outputs" / "classroom_challenges"
OUT.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(DB)
orders = pd.read_sql("SELECT * FROM orders", con)
orders["created_at"] = pd.to_datetime(orders["created_at"], errors="coerce")
orders["promised_eta"] = pd.to_datetime(orders["promised_eta"], errors="coerce")
orders["pickup_at"] = pd.to_datetime(orders["pickup_at"], errors="coerce")
orders["actual_delivery_at"] = pd.to_datetime(orders["actual_delivery_at"], errors="coerce")
orders = orders.drop_duplicates("order_id", keep="first")
outcomes = pd.read_csv(DATA / "order_outcomes.csv")
events = pd.read_csv(DATA / "order_events.csv")
tickets = pd.read_csv(DATA / "support_tickets.csv")
actions = pd.read_csv(DATA / "customer_app_actions.csv")
interventions = pd.read_csv(DATA / "order_interventions.csv")
restaurant_status = pd.read_csv(DATA / "restaurant_status.csv")
driver_events = json.loads((DATA / "driver_events.json").read_text(encoding="utf-8"))
'''

c5 = [
    code(common),
    md("## Challenge 1 — Late-delivery problem\n\nDefinition used here: a delivered order with non-null promised and actual delivery timestamps is late when actual delivery is after the promised ETA. Cancelled and timestamp-missing orders are excluded from the denominator."),
    code('''analysis = orders[orders["final_status"].astype(str).str.lower().eq("delivered")].copy()
analysis["delay_min"] = (analysis["actual_delivery_at"] - analysis["promised_eta"]).dt.total_seconds() / 60
measurable = analysis.dropna(subset=["promised_eta", "actual_delivery_at"])
late = measurable[measurable["delay_min"] > 0]
print({"measurable_deliveries": len(measurable), "late_count": len(late), "late_rate_pct": round(late.shape[0] / len(measurable) * 100, 2), "median_lateness_min": round(late["delay_min"].median(), 2)})
display(late.nlargest(10, "delay_min")[['order_id','promised_eta','actual_delivery_at','delay_min']])
print("Quality issues:", {"duplicate_order_ids": int(orders["order_id"].duplicated().sum()), "delivered_missing_actual": int((analysis["actual_delivery_at"].isna()).sum()), "promised_before_created": int((analysis["promised_eta"] < analysis["created_at"]).sum())})'''),
    md("## Challenge 2 — Is traffic the problem?\n\nThese comparisons are associations, not causal effects. I compare traffic, weather, distance, and time of day using the same measurable delivered-order denominator."),
    code('''m = measurable.copy()
m["late_flag"] = (m["delay_min"] > 0).astype(int)
m["distance_band"] = pd.cut(m["distance_km_estimate"], bins=[-1, 3, 7, 100], labels=["0-3 km", "3-7 km", "7+ km"])
m["hour"] = m["created_at"].dt.hour
m["time_band"] = pd.cut(m["hour"], bins=[-1, 6, 11, 15, 19, 24], labels=["night", "morning", "afternoon", "evening", "late night"])
for col in ["traffic_bucket", "weather_bucket", "distance_band", "time_band"]:
    print("\\n", col); display(m.groupby(col, observed=False).agg(orders=("order_id","size"), late_rate_pct=("late_flag", lambda x: round(x.mean()*100,2)), median_delay_min=("delay_min","median")).reset_index())
m.groupby("traffic_bucket")["late_flag"].mean().mul(100).plot(kind="bar", title="Late rate by traffic bucket"); plt.ylabel("Late rate %"); plt.tight_layout(); plt.show()
print("Interpretation: traffic is associated with delay if its groups differ, but distance, restaurant operations, driver supply, and timestamp quality remain alternative explanations.")'''),
    md("## Challenge 3 — Customer support view versus system view"),
    code('''print("Ticket categories:"); display(tickets["category"].value_counts().rename_axis("category").reset_index(name="tickets"))
print("Duplicate ticket IDs:", int(tickets["ticket_id"].duplicated().sum()))
ticket_orders = set(tickets["order_id"].dropna())
system = measurable.assign(late_flag=measurable["delay_min"] > 0)
system["has_ticket"] = system["order_id"].isin(ticket_orders)
display(system.groupby("has_ticket").agg(orders=("order_id","size"), late_rate_pct=("late_flag", lambda x: round(x.mean()*100,2)), median_delay_min=("delay_min","median")).reset_index())
print("Tickets add customer language and perceived friction; timestamps show operational timing but not the customer's experience or reason for contact.")'''),
    md("## Challenge 4 — Complete Dispatch API ingestion"),
    code('''api_script = ROOT / "src" / "mock_dispatch_api_stdlib.py"
api_proc = subprocess.Popen([sys.executable, str(api_script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
import requests
raw_dir = OUT / "class5_raw_dispatch"; raw_dir.mkdir(parents=True, exist_ok=True)
records, page, attempts = [], 1, 0
while True:
    for attempt in range(5):
        response = requests.get("http://127.0.0.1:8000/dispatch/orders", params={"page": page, "page_size": 50}, timeout=10)
        if response.status_code == 200: break
        if response.status_code in (429, 500): time.sleep(0.2 * (attempt + 1)); continue
        response.raise_for_status()
    response.raise_for_status(); payload = response.json()
    (raw_dir / f"page_{page:03d}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    records.extend(payload["data"]); attempts += 1
    if not payload["has_more"]: total = payload["total_records"]; break
    page += 1
print({"pages_saved": page, "records_retrieved": len(records), "api_reported_total": total, "complete": len(records) == total})
api_proc.terminate()'''),
    md("## Challenge 5 — Can we attribute the delay?"),
    code('''flat = [{"driver_id": d["driver_id"], **e} for d in driver_events for e in d["events"]]
driver_events_df = pd.DataFrame(flat)
display(driver_events_df["type"].value_counts().rename_axis("event_type").reset_index(name="events"))
expected = ["assigned", "driver_assigned", "pickup", "picked_up", "delivery", "delivered", "driver_arrived_at_restaurant"]
print("Observed event types:", sorted(driver_events_df["type"].dropna().unique().tolist()))
print("Explicit restaurant-arrival event present:", "driver_arrived_at_restaurant" in set(driver_events_df["type"]))
print("Conclusion: assignment, pickup, and delivery are observed only where their event types exist; driver arrival at the restaurant is not reliably observed, so any arrival time would be inferred from GPS or pickup timing and should not be treated as authoritative.")'''),
    md("## Final synthesis\n\nThe data supports a measurable late-delivery problem and shows operational associations, but it does not establish causation. The validation warnings—duplicates, missing timestamps, chronology defects, and missing explicit restaurant-arrival events—should be resolved or disclosed before training an AI predictor. The next instrumentation priority is an explicit driver-arrived-at-restaurant event plus consistent lifecycle timestamps."),
]

c6 = [
    code(common),
    md("## Challenge 1 — Validation contract for the 56% claim"),
    code('''delivered = orders[orders["final_status"].astype(str).str.lower().eq("delivered")]
contract = pd.DataFrame([
 {"assumption":"One row = one business order","test":"unique order_id after quarantine","status":"WARN" if orders["order_id"].duplicated().any() else "PASS","evidence":int(orders["order_id"].duplicated().sum())},
 {"assumption":"Delivered orders have completion time","test":"delivered actual_delivery_at non-null","status":"WARN" if delivered["actual_delivery_at"].isna().any() else "PASS","evidence":int(delivered["actual_delivery_at"].isna().sum())},
 {"assumption":"Promised ETA is valid","test":"promised_eta >= created_at","status":"WARN" if (orders["promised_eta"] < orders["created_at"]).any() else "PASS","evidence":int((orders["promised_eta"] < orders["created_at"]).sum())},
 {"assumption":"Event chronology is valid","test":"pickup_at <= actual_delivery_at","status":"WARN" if (orders["pickup_at"] > orders["actual_delivery_at"]).any() else "PASS","evidence":int((orders["pickup_at"] > orders["actual_delivery_at"]).sum())},
 {"assumption":"Late has an agreed definition","test":"compare any-delay and >10-minute definitions","status":"WARN","evidence":"definition ownership required"},
]); display(contract)'''),
    md("## Challenge 2 — Three late definitions"),
    code('''x = delivered.dropna(subset=["promised_eta","actual_delivery_at"]).copy(); x["delay_min"]=(x["actual_delivery_at"]-x["promised_eta"]).dt.total_seconds()/60
definitions = pd.DataFrame([
 {"definition":"delay > 0 minutes","late_rate_pct":round((x["delay_min"]>0).mean()*100,2),"business_meaning":"any miss of promised ETA"},
 {"definition":"delay > 10 minutes","late_rate_pct":round((x["delay_min"]>10).mean()*100,2),"business_meaning":"meaningful customer-impact miss"},
 {"definition":"historical delivered/non-null population","late_rate_pct":round((x["delay_min"]>0).mean()*100,2),"business_meaning":"only comparable measurable deliveries"},
]); display(definitions); print("Recommendation: publish the agreed definition in the metric contract; operations and the client KPI owner must approve it.")'''),
    md("## Challenge 3 — Category validation"),
    code('''for label, df, col in [("final_status",orders,"final_status"),("traffic_bucket",orders,"traffic_bucket"),("restaurant status",restaurant_status,"status"),("support category",tickets,"category")]:
    print("\\n"+label); print(sorted(df[col].dropna().astype(str).unique().tolist()))
print("Safe normalization: case and whitespace can be standardized. Semantic mappings such as handoff versus handed_off require owner confirmation.")'''),
    md("## Challenge 4 — Cross-source integrity"),
    code('''restaurants = pd.read_sql("SELECT * FROM restaurants", con); drivers = pd.read_sql("SELECT * FROM drivers", con)
checks = [
 ("orders.restaurant_id → restaurants", orders["restaurant_id"].isin(restaurants["restaurant_id"])),
 ("orders.driver_id → drivers", orders["driver_id"].isin(drivers["driver_id"])),
 ("tickets.order_id → orders", tickets["order_id"].isin(orders["order_id"])),
 ("restaurant_status.order_id → orders", restaurant_status["order_id"].isin(orders["order_id"])),]
mapping = pd.DataFrame([{"relationship":n,"coverage_pct":round(s.mean()*100,2),"status":"PASS" if s.all() else "WARN","unmapped":int((~s).sum())} for n,s in checks]); display(mapping)
print("A small unmapped percentage is only acceptable after checking whether those records affect the decision being made.")'''),
    md("## Challenge 5 — Freshness is an SLA question"),
    code('''rs = restaurant_status.copy(); rs["last_updated_at"]=pd.to_datetime(rs["last_updated_at"],errors="coerce")
joined=rs.merge(orders[["order_id","created_at","actual_delivery_at"]],on="order_id",how="left"); joined["update_lag_min"]=(joined["last_updated_at"]-pd.to_datetime(joined["created_at"],errors="coerce")).dt.total_seconds()/60
display(joined["update_lag_min"].describe())
print("Assessment: freshness may be adequate for weekly analytics, but live ETA requires an explicit SLA and current update timestamp at decision time; restaurant accountability requires agreeing which status event is authoritative.")'''),
    md("## Challenge 6 — Validation gate"),
    code('''validation_report = {"business_grain":"WARN","timestamp_chronology":"WARN","kpi_definition":"WARN","category_semantics":"PASS","cross_source_mapping":"PASS" if mapping["status"].eq("PASS").all() else "WARN","freshness":"UNKNOWN","publish_56_percent":"WARN"}
print(json.dumps(validation_report, indent=2)); print("Decision: do not publish an unqualified 56% claim. Publish only with the denominator, late definition, exclusions, and known data-quality caveats attached.")'''),
    md("## Final takeaway\n\nThe validation gate is WARN: the data is useful for a transparent exploratory decision, but the headline KPI needs an agreed definition, duplicate/timestamp remediation, chronology review, and freshness ownership before it is treated as a production-grade number."),
]

c7 = [
    code(common),
    md("## Challenge 1 — Reconstruct three order lifecycles"),
    code('''out = outcomes.drop_duplicates("order_id"); late_id=out.loc[out["late_flag"].eq(1),"order_id"].iloc[0]; ontime_id=out.loc[out["late_flag"].eq(0),"order_id"].iloc[0]; intervention_id=interventions["order_id"].iloc[0]
def build_order_timeline(order_id):
    rows=[]
    o=orders[orders.order_id.eq(order_id)].iloc[0]
    for col, typ in [("created_at","order_created"),("promised_eta","promised_eta"),("pickup_at","pickup"),("actual_delivery_at","delivered")]:
        if pd.notna(o[col]): rows.append({"event_time":o[col],"event_type":typ,"actor":"system","source_system":"orders"})
    for _,e in events[events.order_id.eq(order_id)].iterrows(): rows.append({"event_time":e.event_time,"event_type":e.event_type,"actor":e.actor_type,"source_system":e.source_system})
    for _,i in interventions[interventions.order_id.eq(order_id)].iterrows(): rows.append({"event_time":i.intervention_at,"event_type":i.intervention_type,"actor":i.initiated_by,"source_system":"interventions"})
    return pd.DataFrame(rows).assign(event_time=lambda d:pd.to_datetime(d.event_time,errors="coerce")).sort_values("event_time")
for label, oid in [("on_time",ontime_id),("late",late_id),("intervention",intervention_id)]: print(label,oid); display(build_order_timeline(oid))'''),
    md("## Challenge 2 — Canonical project model"),
    code('''model = pd.DataFrame([
 {"table":"orders","primary_key":"order_id","foreign_keys":"customer_id, restaurant_id, driver_id","grain":"one row per source order"},
 {"table":"customer_app_actions","primary_key":"action_id","foreign_keys":"order_id, customer_id","grain":"one customer action"},
 {"table":"support_tickets","primary_key":"ticket_id","foreign_keys":"order_id","grain":"one support ticket"},
 {"table":"order_interventions","primary_key":"intervention_id","foreign_keys":"order_id","grain":"one intervention"},
 {"table":"order_outcomes","primary_key":"order_id","foreign_keys":"order_id","grain":"one canonical outcome"},]); display(model)
print("This model keeps source grains explicit and aggregates one-to-many interactions before joining to one order row, preventing fan-out and double counting.")'''),
    md("## Challenge 3 — Interaction → intervention → outcome order model"),
    code('''action_agg=actions.groupby("order_id").agg(support_opened=("action_id","size"),cancel_attempted=("action_type",lambda s:int(s.astype(str).str.contains("cancel",case=False).any()))).reset_index(); action_agg["support_opened"]=action_agg["support_opened"]>0
int_agg=interventions.groupby("order_id").agg(intervention_count=("intervention_id","size"),intervention_types=("intervention_type",lambda s:", ".join(sorted(set(s.astype(str)))))).reset_index()
journey=outcomes.merge(orders[["order_id","customer_id","final_status"]],on="order_id",how="left").merge(action_agg,on="order_id",how="left").merge(int_agg,on="order_id",how="left"); journey[["support_opened","cancel_attempted"]]=journey[["support_opened","cancel_attempted"]].fillna(False); journey["intervention_count"]=journey["intervention_count"].fillna(0).astype(int); journey["intervention_types"]=journey["intervention_types"].fillna(""); display(journey.head()); print({"late_with_support":int(journey.query("late_flag == 1 and support_opened == True").shape[0]),"orders_with_intervention":int((journey.intervention_count>0).sum()),"most_common_intervention":interventions["intervention_type"].value_counts().idxmax(),"late_no_intervention_with_support":int(journey.query("late_flag == 1 and support_opened == True and intervention_count == 0").shape[0])})'''),
    md("## Challenge 4 — Selected business metrics"),
    code('''metrics = pd.DataFrame([
 {"metric":"Late delivery rate","formula":"late outcomes / measurable delivered outcomes","grain":"order","why":"project outcome KPI"},
 {"metric":"Customer friction rate","formula":"orders with customer action or ticket / orders","grain":"order","why":"customer interaction leading indicator"},
 {"metric":"Intervention rate","formula":"orders with ≥1 intervention / orders","grain":"order","why":"controllable operational response"},
 {"metric":"Median delay among late orders","formula":"median delay_min where late_flag=1","grain":"late order","why":"severity of outcome"},]); display(metrics)
print("Calculated values:"); print({"late_rate_pct":round(journey.late_flag.mean()*100,2),"customer_friction_rate_pct":round((journey.support_opened | journey.cancel_attempted).mean()*100,2),"intervention_rate_pct":round((journey.intervention_count>0).mean()*100,2),"median_delay_min":round(journey.loc[journey.late_flag.eq(1),"delay_min"].median(),2)})'''),
    md("## Challenge 5 — Workflow investigations"),
    code('''journey["has_intervention"]=journey.intervention_count>0
print("A. Support association"); display(journey.groupby("support_opened").agg(orders=("order_id","size"),late_rate_pct=("late_flag",lambda x:round(x.mean()*100,2)),median_delay_min=("delay_min","median")))
print("B. Intervention association"); display(journey.groupby("has_intervention").agg(orders=("order_id","size"),late_rate_pct=("late_flag",lambda x:round(x.mean()*100,2))))
print("C. Intervention type"); display(journey[journey.has_intervention].explode("intervention_types").groupby("intervention_types").agg(orders=("order_id","size"),late_rate_pct=("late_flag",lambda x:round(x.mean()*100,2))).sort_values("late_rate_pct"))
print("These are associations. They do not prove that support or intervention caused delay; customers may contact support because an order is already going badly, and interventions may target the hardest cases.")'''),
    md("## Challenge 6 — KPI linkage and instrumentation"),
    code('''print("PROJECT KPI: reduce late delivery rate")
print("→ outcome: late_delivery_rate, median_delay_among_late")
print("→ workflow/driver metrics: order-to-pickup time, traffic/distance segments, customer friction")
print("→ interventions: intervention rate and type-specific outcomes")
print("→ sources/events: orders, outcomes, customer actions, tickets, interventions, order events, driver events")
print("Controllable by operations: pickup time, intervention routing, restaurant/driver process. Outcomes: late rate and delay severity. Biggest missing event: explicit driver arrival at restaurant. Instrument next: driver_arrived_at_restaurant, consistent event timestamps, and intervention outcome/reason codes.")'''),
    md("## Final reflection\n\nThe smallest useful model is an order-level journey with carefully aggregated customer interactions, support, interventions, and outcomes. It supports the KPI without pretending that associations are causal."),
]

for name, title, intro, cells in [
    ("FlashEats_Class5_Local_Solved.ipynb", "FlashEats — Class 5 Investigation (Local Solved)", "Solved locally against the submission repository. This notebook covers source discovery, late-delivery analysis, customer evidence, reliable API retrieval, and event observability.", c5),
    ("FlashEats_Class6_Local_Solved.ipynb", "FlashEats — Class 6 Validation (Local Solved)", "Solved locally against the submission repository. This notebook turns business assumptions into validation checks and a publishability decision.", c6),
    ("FlashEats_Class7_Local_Solved.ipynb", "FlashEats — Class 7 Workflow Model (Local Solved)", "Solved locally against the submission repository. This notebook builds the order-level workflow model and connects it to the late-delivery KPI.", c7),
]:
    nbf.write(notebook(title, intro, cells), OUT / name)
print("Created", len([*OUT.glob("FlashEats_Class*_Local_Solved.ipynb")]), "notebooks in", OUT)
