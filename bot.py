"""
Weeping Ghosts — Eve Echoes Corporation Discord Bot
────────────────────────────────────────────────────
Run:
    python bot.py

Required environment variables (copy .env.example → .env and fill in):
    DISCORD_TOKEN   — your Discord bot token
    GUILD_ID        — your server's ID (for instant slash-command sync)

All other variables are optional but enable extra features.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands

import config
from utils import database as db

# Ensure data directory exists before logging initialisation
os.makedirs("data", exist_ok=True)

# ── logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("weeping_ghosts")

# ── cogs to load ──────────────────────────────────────────────────────────────

COGS = [
    "cogs.registration",
    "cogs.isk_counter",
    "cogs.points",
    "cogs.balance",
    "cogs.compensation",
    "cogs.orders",
    "cogs.shop",
    "cogs.calculators",
    "cogs.killboard",
    "cogs.ai_agent",
    "cogs.admin",
    "cogs.auto_roles",
]

# ── bot setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class WeepingGhostsBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",   # kept for any legacy text commands
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self) -> None:
        # Initialise database
        os.makedirs("data", exist_ok=True)
        await db.init()
        log.info("Database initialised.")

        # Load all cogs
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("Loaded cog: %s", cog)
            except Exception as exc:
                log.error("Failed to load cog %s: %s", cog, exc)

        # Sync slash commands
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d guild slash commands.", len(synced))
        else:
            synced = await self.tree.sync()
            log.info("Synced %d global slash commands (may take up to 1 hour).", len(synced))

    async def on_ready(self) -> None:
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)  # type: ignore[union-attr]
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{config.CORP_NAME} | /help",
            )
        )

    async def on_application_command_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        msg = f"❌ An unexpected error occurred: `{error}`"
        log.exception("Slash command error", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)


# ── /help ──────────────────────────────────────────────────────────────────────

@commands.command(name="help")
async def _help(ctx: commands.Context) -> None:  # type: ignore[type-arg]
    embed = discord.Embed(
        title=f"🩸 {config.CORP_NAME} Bot — Help",
        description="All features are available as slash commands (/).",
        colour=discord.Colour.dark_red(),
    )
    sections = {
        "📋 Registration": [
            "`/register` — Register with optional screenshot",
            "`/profile` — View member profile",
        ],
        "💰 Balance": [
            "`/balance` — Check your ISK balance",
            "`/deposit` — Request top-up from screenshot",
            "`/history` — Transaction history",
            "`/richlist` — Top members by balance",
        ],
        "⚔️ PvP / PvE": [
            "`/pvp_report` — Submit kill screenshot for points",
            "`/pve_report` — Submit mission screenshot for points",
            "`/leaderboard` — Points leaderboard",
        ],
        "💀 Killboard": [
            "`/killboard` — View recent kills",
            "`/post_kill` — Submit a kill",
        ],
        "🚀 Compensation": [
            "`/compensation` — Request ship loss reimbursement",
            "`/comp_status` — Check your comp requests",
        ],
        "📋 Corp Orders": [
            "`/orders` — List open orders",
            "`/order_create` — Create an order (officers)",
            "`/order_close` — Close an order (officers)",
        ],
        "🛒 Corp Shop": [
            "`/shop` — Browse the shop",
            "`/shop_add` — Add an item (officers)",
            "`/shop_remove` — Remove an item (officers)",
        ],
        "🧮 Calculators": [
            "`/calc_profit` — Trade profit calculator",
            "`/calc_implant` — Implant level calculator",
            "`/calc_mining` — Mining income calculator",
            "`/calc_production` — Production cost calculator",
        ],
        "💰 ISK Counter": ["`/isk_count` — Extract ISK from screenshot"],
        "🤖 AI Agent": [
            "`/ai` — Ask GHOST-AI a question",
            "`/ai_reset` — Clear conversation history",
        ],
        "🏅 Auto-Roles": [
            "`/autorole_add` — Add auto-role rule (admin)",
            "`/autorole_remove` — Remove rule (admin)",
            "`/autorole_list` — List rules",
            "`/autorole_run` — Run check now (admin)",
        ],
        "🛡️ Admin Panel": [
            "`/admin_verify` — Verify a member",
            "`/admin_credit` — Add ISK to balance",
            "`/admin_debit` — Deduct ISK",
            "`/admin_give_role` / `admin_remove_role` — Manage roles",
            "`/admin_approve_kill` — Approve kill & award points",
            "`/admin_approve_comp` / `admin_reject_comp` — Handle compensations",
            "`/admin_pending` — List pending compensations",
            "`/admin_members` — List all members",
        ],
    }
    for title, lines in sections.items():
        embed.add_field(name=title, value="\n".join(lines), inline=False)
    embed.set_footer(text=config.CORP_NAME + " | " + config.CORP_TICKER)
    await ctx.send(embed=embed)


# ── entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    if not config.DISCORD_TOKEN:
        log.error("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    bot = WeepingGhostsBot()
    bot.add_command(_help)

    async with bot:
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
