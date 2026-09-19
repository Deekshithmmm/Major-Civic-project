from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://civic:civic_dev_password@localhost:5433/civic_accountability"

    jwt_secret: str = "change_me_dev_only_not_for_production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "civic_minio"
    s3_secret_key: str = "civic_minio_password"
    s3_bucket_media: str = "civic-media"
    s3_bucket_evidence_vault: str = "civic-evidence-vault"
    s3_region: str = "us-east-1"

    redis_url: str = "redis://localhost:6379/0"

    notification_provider: str = "console"
    msg91_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""

    env: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
