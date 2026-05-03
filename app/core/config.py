from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    LAMBDA_URL: str = ""
    LAMBDA_API_KEY: str = ""
    CORS_ORIGINS: str = ""
    DATABASE_URL: str = ""
    DEFAULT_USER_ID: str = "default-user"
    HISTORY_LIMIT: int = 10
    GOOGLE_API_KEY: str = ""
    COGNITO_REGION: str = ""
    COGNITO_USER_POOL_ID: str = ""
    COGNITO_CLIENT_ID: str = ""
    CHARACTERS_S3_BASE_URL: str = "https://chars-hp-epam.s3.us-east-1.amazonaws.com"

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def cognito_issuer(self) -> str:
        return f"https://cognito-idp.{self.COGNITO_REGION}.amazonaws.com/{self.COGNITO_USER_POOL_ID}"

    @property
    def cognito_jwks_url(self) -> str:
        return f"{self.cognito_issuer}/.well-known/jwks.json"


settings = Settings()
