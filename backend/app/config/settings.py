import os
from pathlib import Path
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # keeps doctor/path tests runnable before dependencies are installed
    BaseSettings = object
    def SettingsConfigDict(**kwargs):
        return kwargs

# settings.py is at <PROJECT_ROOT>/backend/app/config/settings.py
# parents[3] == <PROJECT_ROOT>/backend, parents[4] == <PROJECT_ROOT> in old code was wrong?
# Robustly discover the project root by walking upward until run.py and backend/ exist.
def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / "run.py").is_file() and (candidate / "backend").is_dir():
            return candidate
    # Safe fallback for source layout: backend/app/config/settings.py -> project root
    return Path(__file__).resolve().parents[3]

PROJECT_ROOT = find_project_root()
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

class Settings(BaseSettings):
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    mock_mode: bool = False
    concurrency: int = 5
    headless: bool = True
    timeout_seconds: int = 60
    retry_count: int = 1
    retry_delay_seconds: int = 2
    help_draw_url: str = ""
    # Always default runtime data to <PROJECT_ROOT>/data.
    # If DATA_DIR is overridden, relative paths are resolved under PROJECT_ROOT,
    # never under the caller's current working directory.
    data_dir: Path = DEFAULT_DATA_DIR

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    def model_post_init(self, __context):
        if not self.data_dir.is_absolute():
            self.data_dir = (PROJECT_ROOT / self.data_dir).resolve()
        else:
            self.data_dir = self.data_dir.resolve()

    @property
    def accounts_dir(self) -> Path:
        return self.data_dir / "accounts"

    @property
    def screenshots_dir(self) -> Path:
        return self.data_dir / "screenshots"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def database_dir(self) -> Path:
        return self.data_dir / "database"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.database_dir / 'midasbuy.sqlite3'}"

settings = Settings()

def ensure_dirs() -> None:
    for path in [settings.accounts_dir, settings.screenshots_dir, settings.logs_dir, settings.exports_dir, settings.database_dir]:
        path.mkdir(parents=True, exist_ok=True)
