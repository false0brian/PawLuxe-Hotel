from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_prefix: str = "/api/v1"
    api_key: str = "change-me"
    encryption_key: str = ""
    database_url: str = "sqlite:///./pawluxe.db"
    upload_dir: Path = Path("storage/uploads")
    encrypted_dir: Path = Path("storage/encrypted")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
