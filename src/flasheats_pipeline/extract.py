from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from urllib import error, parse, request

import pandas as pd


REQUIRED_FILE_NAMES = [
    "class7_model_brief.json",
    "client_metric_definitions.json",
    "customer_app_actions.csv",
    "customer_interactions.csv",
    "driver_events.json",
    "order_events.csv",
    "order_interventions.csv",
    "order_outcomes.csv",
    "restaurant_status.csv",
    "restaurants.csv",
    "support_tickets.csv",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_entry(path: Path, source_type: str, rows: int | None = None) -> dict:
    return {
        "source": str(path),
        "source_type": source_type,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "rows": rows,
    }


def extract_local_sources(config, logger):
    if not config.sqlite_path.exists():
        raise FileNotFoundError(f"SQLite source not found: {config.sqlite_path}")

    with sqlite3.connect(config.sqlite_path) as connection:
        sql_sources = {
            table: pd.read_sql(f"select * from {table}", connection)
            for table in ["orders", "customers", "drivers", "restaurants"]
        }

    file_sources = {}
    manifest = []
    for name in REQUIRED_FILE_NAMES:
        path = config.file_root / name
        if not path.exists():
            raise FileNotFoundError(f"Required source file not found: {path}")
        if path.suffix == ".csv":
            value = pd.read_csv(path)
            rows = len(value)
        else:
            value = json.loads(path.read_text(encoding="utf-8"))
            if path.name == "driver_events.json":
                value = pd.DataFrame([
                    {"driver_id": driver["driver_id"], **event}
                    for driver in value
                    for event in driver.get("events", [])
                ])
                rows = len(value)
            else:
                rows = len(value) if isinstance(value, list) else None
        file_sources[path.stem] = value
        manifest.append(_manifest_entry(path, "file", rows))

    for table, frame in sql_sources.items():
        manifest.append(_manifest_entry(config.sqlite_path, f"sqlite:{table}", len(frame)))

    logger.info(
        "Extracted local sources | orders=%s outcomes=%s interventions=%s files=%s",
        len(sql_sources["orders"]),
        len(file_sources["order_outcomes"]),
        len(file_sources["order_interventions"]),
        len(file_sources),
    )
    return {**sql_sources, **file_sources}, manifest


def _get_json(url: str, params: dict, timeout: float = 5) -> tuple[int, dict, dict]:
    target = f"{url}?{parse.urlencode(params)}"
    try:
        with request.urlopen(target, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload, dict(response.headers)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"error": body}
        return exc.code, payload, dict(exc.headers)
    except error.URLError as exc:
        return 0, {"error": str(exc.reason)}, {}


def _wait_for_api(api_url: str, timeout_seconds: float = 12) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status, _, _ = _get_json(f"{api_url}/health", {})
        if status == 200:
            return True
        time.sleep(0.25)
    return False


def fetch_dispatch_api(config, run_date: date, logger):
    raw_dir = config.generated_api_root / f"run_date={run_date.isoformat()}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    expected_total = None
    page = 1

    while True:
        for attempt in range(1, config.max_retries + 1):
            status, payload, headers = _get_json(
                f"{config.api_url}/dispatch/orders",
                {"page": page, "page_size": config.page_size},
            )
            if status == 200:
                break
            if status in {429, 500, 502, 503, 504} and attempt < config.max_retries:
                retry_after = payload.get("retry_after_seconds") or headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after else config.retry_base_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Retrying Dispatch API | page=%s status=%s attempt=%s/%s wait=%.2fs",
                    page, status, attempt, config.max_retries, wait_seconds,
                )
                time.sleep(wait_seconds)
                continue
            raise RuntimeError(f"Dispatch API page {page} failed: status={status} payload={payload}")

        (raw_dir / f"dispatch_page_{page:03d}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        if expected_total is None:
            expected_total = int(payload.get("total_records", 0))
        page_rows = payload.get("data", [])
        rows.extend(page_rows)
        logger.info("Fetched Dispatch page | page=%s rows=%s cumulative=%s", page, len(page_rows), len(rows))
        if not payload.get("has_more", False):
            break
        page += 1

    dispatch = pd.DataFrame(rows)
    if expected_total != len(dispatch):
        raise ValueError(f"Dispatch retrieval incomplete: expected={expected_total} received={len(dispatch)}")
    if not dispatch.empty and not dispatch["order_id"].is_unique:
        raise ValueError("Dispatch retrieval contains duplicate order_id values")
    logger.info("Dispatch extraction complete | records=%s pages=%s", len(dispatch), page)
    return dispatch, _manifest_entry(raw_dir / "dispatch_page_001.json", "api_page", None) | {
        "api_pages": page,
        "api_records": len(dispatch),
        "api_expected_records": expected_total,
        "run_date": run_date.isoformat(),
    }
