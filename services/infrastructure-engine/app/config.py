from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379"
    database_url: str = ""
    infra_engine_port: int = 8000
    github_token: str = ""
    groq_api_key: str = ""
    temp_workspace_root: str = "/tmp/codelens/workspace"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
