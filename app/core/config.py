from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SubLedger"
    app_version: str = "1.0.0"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/subledger_db"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
