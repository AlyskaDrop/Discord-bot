"""Killboard cog — display and post kill records."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db
from utils.ocr import extract_killmail_from_image


class Killboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="killboard", description="View the recent kill feed.")
    @app_commands.describe(limit="Number of kills to show (max 15)")
    async def killboard(
        self, interaction: discord.Interaction, limit: int = 10
    ) -> None:
        await interaction.response.defer()
        limit = max(1, min(15, limit))
        kills = await db.get_kills(limit=limit, approved_only=True)

        embed = discord.Embed(
            title="💀 Killboard — Weeping Ghosts",
            colour=discord.Colour.red(),
        )
        if not kills:
            embed.description = "No kills recorded yet."
        else:
            lines = []
            for k in kills:
                reporter = k.get("ingame_name") or f"<@{k['discord_id']}>"
                ship = k["ship_destroyed"] or "Unknown ship"
                pilot = k["pilot_name"] or "Unknown pilot"
                isk = f"{k['isk_value']:,.0f} ISK" if k["isk_value"] else "?"
                lines.append(
                    f"⚔️ **{reporter}** killed **{pilot}** ({ship}) — {isk} | "
                    f"`{k['posted_at'][:10]}`"
                )
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="post_kill",
        description="Post a kill to the public killboard channel.",
    )
    @app_commands.describe(screenshot="Kill-mail screenshot")
    async def post_kill(
        self, interaction: discord.Interaction, screenshot: discord.Attachment
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        data = await screenshot.read()
        kd = extract_killmail_from_image(data)

        kill_id = await db.add_kill(
            interaction.user.id,
            kill_data=kd.raw_text,
            ship_destroyed=kd.ship_name,
            pilot_name=kd.pilot_name,
            isk_value=kd.isk_value,
        )

        embed = discord.Embed(
            title="☠️ New Kill Submitted",
            description="Your kill has been submitted for review.",
            colour=discord.Colour.red(),
        )
        embed.add_field(name="Kill ID", value=f"#{kill_id}")
        if kd.ship_name:
            embed.add_field(name="Ship", value=kd.ship_name)
        if kd.pilot_name:
            embed.add_field(name="Victim", value=kd.pilot_name)
        if kd.isk_value:
            embed.add_field(name="ISK", value=f"{kd.isk_value:,.0f}")
        embed.set_image(url=screenshot.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _post_to_killboard_channel(self, kill: dict) -> None:
        """Post an approved kill to the dedicated killboard channel."""
        if not config.KILLBOARD_CHANNEL_ID:
            return
        ch = self.bot.get_channel(config.KILLBOARD_CHANNEL_ID)
        if not ch:
            return

        reporter = kill.get("ingame_name") or f"<@{kill['discord_id']}>"
        ship = kill["ship_destroyed"] or "Unknown ship"
        pilot = kill["pilot_name"] or "Unknown pilot"
        isk = f"{kill['isk_value']:,.0f} ISK" if kill["isk_value"] else "Unknown"

        embed = discord.Embed(
            title=f"☠️ Kill #{kill['id']}",
            description=f"**{reporter}** destroyed **{pilot}**'s {ship}",
            colour=discord.Colour.red(),
        )
        embed.add_field(name="ISK Value", value=isk)
        embed.add_field(name="Date", value=kill["posted_at"][:10])
        await ch.send(embed=embed)  # type: ignore[union-attr]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Killboard(bot))
