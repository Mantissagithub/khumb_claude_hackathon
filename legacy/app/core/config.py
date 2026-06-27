import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "KumbhSeva — AI Issue Routing"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Anthropic / Claude
    # Resolved from the environment (.env) automatically by pydantic-settings.
    ANTHROPIC_API_KEY: str = ""
    # Per the claude-api skill: default to the most capable Opus-tier model.
    CLAUDE_MODEL: str = "claude-opus-4-8"

    # Local JSON ledger that simulates a database for the prototype.
    DB_FILE: str = "data/issue_ledger.json"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
