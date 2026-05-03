"""ISK counter cog — extract ISK values from uploaded screenshots."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db
from utils.ocr import extract_isk_from_image


class IskCounter(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="isk_count",
        description="Extract an ISK value from a screenshot and optionally add it to your balance.",
    )
    @app_commands.describe(
        screenshot="Screenshot showing an ISK amount",
        add_to_balance="Add the detected amount to your corp balance? (admins only)",
    )
    async def isk_count(
        self,
        interaction: discord.Interaction,
        screenshot: discord.Attachment,
        add_to_balance: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        data = await screenshot.read()
        amount = extract_isk_from_image(data)

        if amount <= 0:
            await interaction.followup.send(
                "❌ Could not detect an ISK amount in the screenshot. "
                "Please make sure the amount is clearly visible.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="💰 ISK Detected",
            description=f"**{amount:,.0f} ISK** found in the screenshot.",
            colour=discord.Colour.gold(),
        )
        embed.set_image(url=screenshot.url)

        # Only admins can directly credit balance
        if add_to_balance:
            is_admin = False
            if config.ADMIN_ROLE_ID and interaction.guild:
                role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
                if role and role in interaction.user.roles:  # type: ignore[union-attr]
                    is_admin = True

            if not is_admin:
                embed.add_field(
                    name="⚠️ Note",
                    value="Only officers can directly credit balances. "
                    "Your screenshot has been forwarded for review.",
                )
                # forward to admin channel
                if config.ADMIN_CHANNEL_ID:
                    ch = self.bot.get_channel(config.ADMIN_CHANNEL_ID)
                    if ch:
                        fwd = discord.Embed(
                            title="💰 Balance Credit Request",
                            colour=discord.Colour.orange(),
                        )
                        fwd.add_field(name="Member", value=interaction.user.mention)
                        fwd.add_field(name="Amount", value=f"{amount:,.0f} ISK")
                        fwd.set_image(url=screenshot.url)
                        await ch.send(embed=fwd)  # type: ignore[union-attr]
            else:
                new_bal = await db.modify_balance(
                    interaction.user.id,
                    amount,
                    tx_type="isk_screenshot",
                    description=f"ISK credited from screenshot",
                )
                embed.add_field(
                    name="✅ Balance Updated",
                    value=f"New balance: **{new_bal:,.0f} ISK**",
                )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IskCounter(bot))
