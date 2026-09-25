from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import subprocess
import sys

from flasheats_pipeline.config import PipelineConfig
from flasheats_pipeline.extract import extract_local_sources, fetch_dispatch_api, _wait_for_api
from flasheats_pipeline.logging_utils import build_logger
from flasheats_pipeline.metrics import build_metrics
from flasheats_pipeline.model import build_order_journey
from flasheats_pipeline.save import save_outputs
from flasheats_pipeline.validate import ValidationError, run_validations, validation_status


def apply_chaos(sources, scenario, logger):
    if scenario == "none":
        return sources
    updated = dict(sources)
    orders = sources["orders"].copy()
    if scenario == "missing_column":
        logger.warning("CHAOS: removing promised_eta")
        updated["orders"] = orders.drop(columns=["promised_eta"])
    elif scenario == "duplicate_order":
        logger.warning("CHAOS: adding duplicate order row")
        updated["orders"] = __import__("pandas").concat([orders, orders.iloc[[0]]], ignore_index=True)
    elif scenario == "stale_data":
        logger.warning("CHAOS: shifting created_at one year backward")
        orders["created_at"] = __import__("pandas").to_datetime(orders["created_at"]) - __import__("pandas").Timedelta(days=365)
        updated["orders"] = orders
    else:
        raise ValueError(f"Unknown chaos scenario: {scenario}")
    return updated


def _start_api(config, logger):
    if not config.start_mock_api:
        return None
    if _wait_for_api(config.api_url, timeout_seconds=1):
        logger.info("Dispatch API already running")
        return None
    script = config.repo_root / "src" / "mock_dispatch_api_stdlib.py"
    process = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not _wait_for_api(config.api_url, timeout_seconds=12):
        process.terminate()
        raise RuntimeError("Mock Dispatch API did not become healthy")
    logger.info("Started local Dispatch API")
    return process


def run(repo_root: Path, run_date: date, chaos: str):
    config = PipelineConfig.from_env(repo_root)
    log_path = repo_root / "outputs" / "logs" / f"pipeline_{run_date.isoformat()}.log"
    logger = build_logger(log_path, config.log_level)
    api_process = None
    try:
        logger.info("Pipeline started | run_date=%s chaos=%s", run_date, chaos)
        api_process = _start_api(config, logger)
        sources, manifest = extract_local_sources(config, logger)
        sources = apply_chaos(sources, chaos, logger)
        dispatch, api_manifest = fetch_dispatch_api(config, run_date, logger)
        manifest.append(api_manifest)

        validation_results = run_validations(sources, dispatch, run_date, config.max_data_age_days)
        gate = validation_status(validation_results)
        for result in validation_results:
            logger.info("Validation | check=%s status=%s detail=%s", result.check, result.status, result.detail)
        if gate == "FAIL":
            raise ValidationError("Validation gate failed; processed output was not published")

        duplicate_rows = sources["orders"].loc[sources["orders"]["order_id"].duplicated(False)].copy()
        journey = build_order_journey(sources, dispatch, logger)
        metrics, evidence = build_metrics(journey)
        outputs = save_outputs(journey, metrics, evidence, validation_results, gate, manifest, config, run_date, duplicate_rows)
        logger.info("Pipeline completed | gate=%s rows=%s", gate, len(journey))
        print("PIPELINE SUCCESS")
        print(json.dumps(metrics, indent=2))
        print(json.dumps(outputs, indent=2))
        return 0
    except ValidationError as exc:
        logger.error("Pipeline stopped at validation gate | %s", exc)
        print(f"PIPELINE FAILED: {exc}")
        return 2
    except Exception as exc:
        logger.exception("Pipeline failed unexpectedly | %s", exc)
        print(f"PIPELINE FAILED: {exc}")
        return 1
    finally:
        if api_process is not None:
            api_process.terminate()
            api_process.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description="Run the FlashEats full-source pipeline")
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--chaos", choices=["none", "missing_column", "duplicate_order", "stale_data"], default="none")
    args = parser.parse_args()
    return run(Path(__file__).resolve().parents[1], date.fromisoformat(args.run_date), args.chaos)


if __name__ == "__main__":
    raise SystemExit(main())
