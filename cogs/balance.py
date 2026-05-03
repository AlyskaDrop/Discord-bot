"""Balance cog — view balance, history, top-up from screenshots, leaderboard."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db
from utils.ocr import extract_transaction_from_image


class Balance(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="balance", description="Check your corp ISK balance.")
    @app_commands.describe(member="Member to check (admins only; defaults to yourself)")
    async def balance(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        target = member or interaction.user
        if member and member != interaction.user:
            # only admins can view others
            if config.ADMIN_ROLE_ID and interaction.guild:
                role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
                if not (role and role in interaction.user.roles):  # type: ignore[union-attr]
                    await interaction.followup.send("❌ You need the admin role.", ephemeral=True)
                    return

        isk = await db.get_balance(target.id)
        embed = discord.Embed(
            title="💰 Corp Balance",
            colour=discord.Colour.gold(),
        )
        embed.add_field(name="Member", value=target.mention, inline=True)
        embed.add_field(name="Balance", value=f"{isk:,.0f} ISK", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="deposit",
        description="Submit a screenshot of an ISK transfer to request a balance top-up.",
    )
    @app_commands.describe(screenshot="Screenshot of the ISK transfer confirmation")
    async def deposit(
        self, interaction: discord.Interaction, screenshot: discord.Attachment
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        data = await screenshot.read()
        tx = extract_transaction_from_image(data)

        if tx.amount <= 0:
            await interaction.followup.send(
                "❌ Could not detect a transfer amount. Please upload a clearer screenshot.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📥 Deposit Request Received",
            description=(
                f"Amount detected: **{tx.amount:,.0f} ISK**\n"
                "An officer will review your screenshot and credit your balance."
            ),
            colour=discord.Colour.blurple(),
        )
        embed.set_image(url=screenshot.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

        if config.ADMIN_CHANNEL_ID:
            ch = self.bot.get_channel(config.ADMIN_CHANNEL_ID)
            if ch:
                admin_embed = discord.Embed(
                    title="📥 Deposit Request",
                    colour=discord.Colour.orange(),
                )
                admin_embed.add_field(name="Member", value=interaction.user.mention)
                admin_embed.add_field(name="Detected Amount", value=f"{tx.amount:,.0f} ISK")
                if tx.sender:
                    admin_embed.add_field(name="From", value=tx.sender)
                admin_embed.add_field(
                    name="Approve",
                    value=f"`/admin credit member:{interaction.user.id} amount:{tx.amount:.0f}`",
                    inline=False,
                )
                admin_embed.set_image(url=screenshot.url)
                await ch.send(embed=admin_embed)  # type: ignore[union-attr]

    @app_commands.command(name="history", description="View your recent balance transactions.")
    async def history(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        txs = await db.get_transactions(interaction.user.id, limit=10)

        embed = discord.Embed(title="📜 Transaction History", colour=discord.Colour.blue())
        if not txs:
            embed.description = "No transactions found."
        else:
            lines = []
            for tx in txs:
                sign = "+" if tx["amount"] >= 0 else ""
                lines.append(
                    f"`{tx['created_at'][:10]}` **{sign}{tx['amount']:,.0f} ISK** "
                    f"— {tx['type']} {tx['description']}"
                )
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="richlist", description="Top-10 members by corp balance.")
    async def richlist(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        rows = await db.get_balance_leaderboard(10)
        embed = discord.Embed(title="💎 Rich List", colour=discord.Colour.gold())
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i + 1}."
            name = row["ingame_name"] or f"<@{row['discord_id']}>"
            lines.append(f"{medal} **{name}** — {row['isk']:,.0f} ISK")
        embed.description = "\n".join(lines) or "No data."
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Balance(bot))
