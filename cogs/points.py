"""Points cog — PvP and PvE point tracking from screenshots."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db
from utils.ocr import extract_killmail_from_image, extract_mission_from_image


class Points(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /pvp_report ────────────────────────────────────────────────────────────

    @app_commands.command(
        name="pvp_report",
        description="Submit a PvP kill screenshot to earn points.",
    )
    @app_commands.describe(screenshot="Kill-mail screenshot")
    async def pvp_report(
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
            title="⚔️ PvP Kill Submitted",
            description="Your kill has been submitted for officer review.",
            colour=discord.Colour.red(),
        )
        embed.add_field(name="Kill ID", value=f"#{kill_id}", inline=True)
        if kd.ship_name:
            embed.add_field(name="Ship", value=kd.ship_name, inline=True)
        if kd.pilot_name:
            embed.add_field(name="Pilot", value=kd.pilot_name, inline=True)
        if kd.isk_value:
            embed.add_field(name="ISK Value", value=f"{kd.isk_value:,.0f} ISK", inline=True)
        embed.set_image(url=screenshot.url)
        embed.set_footer(text=f"Points will be awarded after admin approval.")
        await interaction.followup.send(embed=embed, ephemeral=True)

        # notify admin channel
        if config.ADMIN_CHANNEL_ID:
            ch = self.bot.get_channel(config.ADMIN_CHANNEL_ID)
            if ch:
                admin_embed = discord.Embed(
                    title=f"⚔️ PvP Kill #{kill_id} Pending Review",
                    colour=discord.Colour.red(),
                )
                admin_embed.add_field(name="Reporter", value=interaction.user.mention)
                if kd.ship_name:
                    admin_embed.add_field(name="Ship", value=kd.ship_name)
                if kd.isk_value:
                    admin_embed.add_field(name="ISK Value", value=f"{kd.isk_value:,.0f}")
                admin_embed.add_field(
                    name="Approve",
                    value=f"Use `/admin approve_kill kill_id:{kill_id}`",
                    inline=False,
                )
                admin_embed.set_image(url=screenshot.url)
                await ch.send(embed=admin_embed)  # type: ignore[union-attr]

    # ── /pve_report ────────────────────────────────────────────────────────────

    @app_commands.command(
        name="pve_report",
        description="Submit a PvE mission screenshot to earn points.",
    )
    @app_commands.describe(screenshot="Mission completion screenshot")
    async def pve_report(
        self, interaction: discord.Interaction, screenshot: discord.Attachment
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        data = await screenshot.read()
        md = extract_mission_from_image(data)

        pts = await db.add_points(interaction.user.id, pve=config.PVE_MISSION_POINTS)

        embed = discord.Embed(
            title="🛡️ PvE Mission Submitted",
            colour=discord.Colour.green(),
        )
        if md.mission_name:
            embed.add_field(name="Mission", value=md.mission_name, inline=True)
        if md.isk_reward:
            embed.add_field(name="ISK Reward", value=f"{md.isk_reward:,.0f} ISK", inline=True)
        embed.add_field(
            name="Points Awarded",
            value=f"+{config.PVE_MISSION_POINTS} PvE points",
            inline=True,
        )
        embed.add_field(
            name="Total Points",
            value=f"PvP: {pts['pvp_points']}  |  PvE: {pts['pve_points']}",
            inline=False,
        )
        embed.set_image(url=screenshot.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /leaderboard ───────────────────────────────────────────────────────────

    @app_commands.command(name="leaderboard", description="View the points leaderboard.")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        rows = await db.get_points_leaderboard(10)

        embed = discord.Embed(
            title="🏆 Weeping Ghosts Leaderboard",
            colour=discord.Colour.gold(),
        )
        if not rows:
            embed.description = "No data yet."
        else:
            lines = []
            medals = ["🥇", "🥈", "🥉"]
            for i, row in enumerate(rows):
                medal = medals[i] if i < 3 else f"{i + 1}."
                name = row["ingame_name"] or f"<@{row['discord_id']}>"
                lines.append(
                    f"{medal} **{name}** — {row['total_points']} pts "
                    f"(PvP: {row['pvp_points']} | PvE: {row['pve_points']})"
                )
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Points(bot))
