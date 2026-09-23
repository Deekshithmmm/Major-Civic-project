from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anyone holding this can mint a token for any official, of any role. It is a usable default for
# local development only, and startup refuses it anywhere else - see the validator below.
DEV_JWT_SECRET = "change_me_dev_only_not_for_production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Host port 3307: a locally-installed MySQL commonly already holds 3306.
    # This is the *application* account. It holds per-table DML and no DDL at all, which is
    # what makes the audit log append-only here - see app/db/harden.py.
    database_url: str = "mysql+pymysql://civic:civic_dev_password@localhost:3307/civic_accountability?charset=utf8mb4"

    # The schema owner, used by Alembic and by the hardening script. Kept separate so that a
    # compromise of the running application cannot alter or drop a table, let alone TRUNCATE
    # the audit log.
    migration_database_url: str = (
        "mysql+pymysql://civic_migrate:civic_migrate_password@localhost:3307/civic_accountability?charset=utf8mb4"
    )

    # Setup only, used by `python -m app.db.harden` and nothing else. Granting privileges is user
    # administration, which in MySQL is a global right - handing it to the schema owner would
    # make that account able to mint itself any other account, and the separation it exists to
    # create would be worth nothing.
    admin_database_url: str = (
        "mysql+pymysql://root:civic_root_password@localhost:3307/civic_accountability?charset=utf8mb4"
    )

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    # Officials review evidence and issue challans from these sessions, and the token lives in
    # browser storage, so it expires in hours rather than lasting a working week.
    jwt_expire_minutes: int = 60

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

    # Every upload route processes the file in memory, so these are the ceiling on what one
    # request can allocate. Raising them raises the cost of a single malicious upload.
    max_image_upload_mb: int = 15
    max_video_upload_mb: int = 200

    # Comma-separated. The frontend's origin only; never "*" while credentials are allowed.
    cors_origins: str = "http://localhost:5173"

    # Rule 3(2)(a) of the IT Rules 2021 requires an intermediary to publish these details and to
    # work to these two clocks. They are configuration, not constants, because the officer is a
    # named post-holder who changes and the deadlines are statutory minimums a deployment may
    # choose to beat. GET /api/corruption/grievance-officer serves them verbatim.
    grievance_officer_name: str = "A. Rao"
    grievance_officer_designation: str = "Grievance Officer"
    grievance_officer_email: str = "grievance-officer@civic-accountability.example.in"
    grievance_officer_address: str = "Municipal Corporation Annexe, Ward 12, Bengaluru 560001"
    grievance_ack_hours: int = 24
    grievance_resolve_days: int = 15

    env: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.env == "development"

    @model_validator(mode="after")
    def _refuse_insecure_production_config(self) -> "Settings":
        """
        Fail loudly at startup rather than serving forgeable sessions. A deployment that forgets
        to set JWT_SECRET would otherwise look completely healthy while anyone who has read this
        repository could sign a token as an admin.
        """
        if not self.is_development:
            problems = []
            if self.jwt_secret == DEV_JWT_SECRET:
                problems.append("JWT_SECRET is still the development default")
            if len(self.jwt_secret) < 32:
                problems.append("JWT_SECRET is shorter than 32 characters")
            if "*" in self.cors_origins:
                problems.append("CORS_ORIGINS must name explicit origins, not a wildcard")
            if problems:
                raise ValueError(
                    f"Refusing to start with ENV={self.env}: " + "; ".join(problems) + ". "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
