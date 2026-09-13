import os
import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set a test .env override so tests don't need real credentials
os.environ.setdefault("ENFORCER_DRY_RUN", "true")
os.environ.setdefault("ENFORCER_INTEGRATIONS", "fake")
os.environ.setdefault("DISCORD_BOT_TOKEN", "test")
os.environ.setdefault("DISCORD_GUILD_ID", "0")
os.environ.setdefault("DISCORD_CHANNEL_ID", "0")
