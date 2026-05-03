"""Compensation cog — submit ship loss screenshots for reimbursement."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db
from utils.ocr import extract_killmail_from_image


class Compensation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="compensation",
        description="Request compensation for a lost ship. Upload your loss-mail screenshot.",
    )
    @app_commands.describe(
        screenshot="Screenshot of the ship loss / kill-mail",
        ship_name="Ship name (override OCR result if needed)",
        ship_value="Approximate ISK value (override OCR result if needed)",
    )
    async def compensation(
        self,
        interaction: discord.Interaction,
        screenshot: discord.Attachment,
        ship_name: str | None = None,
        ship_value: float | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        data = await screenshot.read()
        kd = extract_killmail_from_image(data)

        final_ship = ship_name or kd.ship_name or "Unknown"
        final_value = ship_value if ship_value is not None else kd.isk_value

        if final_value <= 0:
            await interaction.followup.send(
                "❌ Could not detect the ship value. "
                "Please provide `ship_value` manually or upload a clearer screenshot.",
                ephemeral=True,
            )
            return

        comp_id = await db.request_compensation(
            interaction.user.id, final_ship, final_value
        )
        payout = final_value * config.COMPENSATION_BASE_PERCENT

        embed = discord.Embed(
            title="🚀 Compensation Request Submitted",
            colour=discord.Colour.blurple(),
        )
        embed.add_field(name="Request ID", value=f"#{comp_id}", inline=True)
        embed.add_field(name="Ship", value=final_ship, inline=True)
        embed.add_field(name="Declared Value", value=f"{final_value:,.0f} ISK", inline=True)
        embed.add_field(
            name="Expected Payout",
            value=f"{payout:,.0f} ISK ({config.COMPENSATION_BASE_PERCENT * 100:.0f}%)",
            inline=True,
        )
        embed.set_image(url=screenshot.url)
        embed.set_footer(text="An officer will review your request.")
        await interaction.followup.send(embed=embed, ephemeral=True)

        if config.ADMIN_CHANNEL_ID:
            ch = self.bot.get_channel(config.ADMIN_CHANNEL_ID)
            if ch:
                admin_embed = discord.Embed(
                    title=f"🚀 Compensation Request #{comp_id}",
                    colour=discord.Colour.orange(),
                )
                admin_embed.add_field(name="Member", value=interaction.user.mention)
                admin_embed.add_field(name="Ship", value=final_ship)
                admin_embed.add_field(name="Value", value=f"{final_value:,.0f} ISK")
                admin_embed.add_field(name="Payout", value=f"{payout:,.0f} ISK")
                admin_embed.add_field(
                    name="Actions",
                    value=(
                        f"`/admin approve_comp comp_id:{comp_id}` — approve\n"
                        f"`/admin reject_comp comp_id:{comp_id}` — reject"
                    ),
                    inline=False,
                )
                admin_embed.set_image(url=screenshot.url)
                await ch.send(embed=admin_embed)  # type: ignore[union-attr]

    @app_commands.command(
        name="comp_status",
        description="Check the status of your compensation requests.",
    )
    async def comp_status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        user = await db.get_user(interaction.user.id)
        if not user:
            await interaction.followup.send("❌ You are not registered.", ephemeral=True)
            return

        # get all comps for this user
        async with db.connect() as conn:
            cur = await conn.execute(
                "SELECT * FROM compensations WHERE user_id = ? ORDER BY requested_at DESC LIMIT 10",
                (user["id"],),
            )
            rows = [dict(r) for r in await cur.fetchall()]

        embed = discord.Embed(title="🚀 Compensation Requests", colour=discord.Colour.blue())
        if not rows:
            embed.description = "No requests found."
        else:
            lines = []
            for row in rows:
                status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(
                    row["status"], "❓"
                )
                lines.append(
                    f"{status_emoji} **#{row['id']}** {row['ship_name']} — "
                    f"{row['ship_value']:,.0f} ISK → {row['amount_paid']:,.0f} ISK [{row['status']}]"
                )
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Compensation(bot))
