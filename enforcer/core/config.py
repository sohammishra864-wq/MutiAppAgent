from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AWS Bedrock
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_bearer_token_bedrock: str = ""
    bedrock_vl_model_id: str = "qwen.qwen3-vl-235b-a22b"
    bedrock_text_model_id: str = "qwen.qwen3-next-80b-a3b"
    bedrock_force_tool_choice: bool = True

    # Discord
    discord_bot_token: str = ""
    discord_guild_id: str = ""
    discord_channel_id: str = ""
    discord_last_place_role_id: str = ""

    # Google Calendar
    google_credentials_path: Path = Path("./secrets/credentials.json")
    google_token_dir: Path = Path("./secrets/tokens")

    # Google Sheets
    google_sheets_id: str = ""
    google_ledger_token_path: Path = Path("./secrets/ledger_token.json")
    sheets_debts_range: str = "debts!A:G"

    # UPI
    upi_payee_address: str = ""
    upi_default_amount: float = 500

    # Spotify
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_refresh_token: str = ""

    # Behaviour
    enforcer_tz: str = "Asia/Kolkata"
    enforcer_dry_run: bool = True
    enforcer_integrations: str = "fake"
    enforcer_max_tool_calls: int = 12
    enforcer_task_timeout_s: int = 90
    enforcer_escalate_below_confidence: float = 0.75
    enforcer_policy_path: Path = Path("./docs/POLICY.md")
    enforcer_ledger_path: Path = Path("./data/ledger.jsonl")
    enforcer_action_log_path: Path = Path("./data/run_log.jsonl")
