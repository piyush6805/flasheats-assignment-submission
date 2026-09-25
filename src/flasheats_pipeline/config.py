from dataclasses import dataclass
from pathlib import Path
import os


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class PipelineConfig:
    repo_root: Path
    api_url: str = "http://127.0.0.1:8000"
    page_size: int = 50
    max_retries: int = 3
    retry_base_seconds: float = 0.25
    max_data_age_days: int = 60
    start_mock_api: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, repo_root: Path) -> "PipelineConfig":
        return cls(
            repo_root=repo_root,
            api_url=os.getenv("DISPATCH_API_URL", "http://127.0.0.1:8000"),
            page_size=int(os.getenv("PAGE_SIZE", "50")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_base_seconds=float(os.getenv("RETRY_BASE_SECONDS", "0.25")),
            max_data_age_days=int(os.getenv("MAX_DATA_AGE_DAYS", "60")),
            start_mock_api=_as_bool(os.getenv("START_MOCK_API"), True),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    @property
    def raw_root(self) -> Path:
        return self.repo_root / "data" / "raw"

    @property
    def file_root(self) -> Path:
        return self.raw_root / "files"

    @property
    def sqlite_path(self) -> Path:
        return self.raw_root / "sqlite" / "flasheats.db"

    @property
    def api_source_path(self) -> Path:
        return self.raw_root / "api" / "source" / "dispatch_data.json"

    @property
    def generated_api_root(self) -> Path:
        return self.raw_root / "api" / "retrieval_runs"

    @property
    def output_root(self) -> Path:
        return self.repo_root / "outputs" / "processed"
