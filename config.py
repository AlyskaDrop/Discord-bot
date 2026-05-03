"""Central configuration loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


def _int(key: str, default: int = 0) -> int:
    val = os.getenv(key, "")
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
GUILD_ID: int = _int("GUILD_ID")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

ADMIN_CHANNEL_ID: int = _int("ADMIN_CHANNEL_ID")
LOG_CHANNEL_ID: int = _int("LOG_CHANNEL_ID")
KILLBOARD_CHANNEL_ID: int = _int("KILLBOARD_CHANNEL_ID")

ADMIN_ROLE_ID: int = _int("ADMIN_ROLE_ID")
MEMBER_ROLE_ID: int = _int("MEMBER_ROLE_ID")
OFFICER_ROLE_ID: int = _int("OFFICER_ROLE_ID")

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/weeping_ghosts.db")

# ── Points rules ─────────────────────────────────────────────────────────────
PVP_KILL_POINTS: int = 10       # points awarded per confirmed kill
PVE_MISSION_POINTS: int = 5     # points awarded per confirmed PvE mission

# ── Balance ───────────────────────────────────────────────────────────────────
COMPENSATION_BASE_PERCENT: float = 0.80   # 80 % of ship value compensated

# ── Auto-role thresholds ──────────────────────────────────────────────────────
# Format: (min_points, role_name)
AUTO_ROLE_THRESHOLDS: list[tuple[int, str]] = [
    (50,  "Recruit"),
    (200, "Soldier"),
    (500, "Veteran"),
    (1000, "Elite"),
]

# ── Corp info ─────────────────────────────────────────────────────────────────
CORP_NAME: str = "Weeping Ghosts"
CORP_TICKER: str = "WGHST"
