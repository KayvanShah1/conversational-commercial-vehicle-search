from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_project_root(markers: tuple[str, ...] = (".git", ".env")) -> Path:
    """Find the workspace root without relying on fixed parent indexes."""
    current = Path(__file__).resolve().parent

    for parent in [current, *current.parents]:
        if any((parent / marker).exists() for marker in markers):
            return parent

    return current.parent


PROJECT_ROOT = find_project_root()


class BaseProjectSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    def project_relative_path(self, path: Path) -> str:
        """Return a project-relative path, falling back to the original path when external."""
        project_root = getattr(self, "project_root", PROJECT_ROOT)
        try:
            return str(path.relative_to(project_root))
        except ValueError:
            return str(path)

    def model_dump(self, **kwargs):
        """Make absolute workspace paths relative for clean logging."""
        dump = super().model_dump(**kwargs)

        for key, value in dump.items():
            if isinstance(value, Path) and value.is_absolute():
                dump[key] = self.project_relative_path(value)

        return dump


class LoggingConfig(BaseProjectSettings):
    """
    Logging configuration.

    Keep DEBUG useful locally, but avoid logging sensitive values.
    Redaction happens inside logger.py.
    """

    level: str = Field(default="INFO")
    file_enabled: bool = Field(default=True)
    console_enabled: bool = Field(default=True)
    file_name: str = Field(
        default="conversational-commercial-vehicle-search.log",
        description="Optional explicit log filename. Defaults to '<project_name>.log' when unset.",
    )
    max_bytes: int = Field(default=2000 * 1024)
    backup_count: int = Field(default=5)


class MotherDuckConfig(BaseModel):
    database: str = Field(default="vehicle_catalog", description="MotherDuck database name")
    token: SecretStr = Field(default="<API_TOKEN>", description="MotherDuck API token")


class CommonSettings(BaseProjectSettings):
    project_name: str = Field(default="vehicle-search-utils")
    project_root: Path = PROJECT_ROOT
    log_dir: Path = Field(default=project_root / "logs")
    data_dir: Path = Field(default=project_root / "data", description="Directory for shared data files")

    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    motherduck: MotherDuckConfig = Field(default_factory=MotherDuckConfig)

    def model_post_init(self, __context, /):
        """Ensure shared workspace directories exist on startup."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


settings = CommonSettings()

if __name__ == "__main__":
    from rich.pretty import pretty_repr

    from vehicle_search_utils.logger import get_logger

    logger = get_logger("CommonSettings")
    logger.debug(f"Project Root Detected: {settings.project_root}")
    logger.debug("--- Loaded Settings ---")
    logger.debug(pretty_repr(settings.model_dump()))
