"""Orders cog — corporation mission board."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db


class Orders(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="orders", description="List open corporation orders.")
    async def orders(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        rows = await db.get_orders("open")

        embed = discord.Embed(
            title="📋 Corporation Orders",
            colour=discord.Colour.blurple(),
        )
        if not rows:
            embed.description = "No open orders at the moment."
        else:
            for row in rows[:10]:
                embed.add_field(
                    name=f"#{row['id']} — {row['title']}",
                    value=(
                        f"{row['description'][:150]}\n"
                        f"💰 Reward: **{row['reward']:,.0f} ISK**"
                    ),
                    inline=False,
                )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="order_create", description="Create a new corporation order (officers only).")
    @app_commands.describe(
        title="Short order title",
        description="Detailed description of what needs to be done",
        reward="ISK reward for completion",
    )
    async def order_create(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        reward: float = 0.0,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        # officer check
        if config.OFFICER_ROLE_ID and interaction.guild:
            role = interaction.guild.get_role(config.OFFICER_ROLE_ID)
            if not (role and role in interaction.user.roles):  # type: ignore[union-attr]
                # also allow admin role
                admin_role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
                if not (admin_role and admin_role in interaction.user.roles):  # type: ignore[union-attr]
                    await interaction.followup.send(
                        "❌ Only officers can create orders.", ephemeral=True
                    )
                    return

        order_id = await db.create_order(interaction.user.id, title, description, reward)

        embed = discord.Embed(
            title="✅ Order Created",
            colour=discord.Colour.green(),
        )
        embed.add_field(name="Order ID", value=f"#{order_id}")
        embed.add_field(name="Title", value=title)
        embed.add_field(name="Reward", value=f"{reward:,.0f} ISK")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="order_close", description="Close an order (officers only).")
    @app_commands.describe(order_id="The order ID to close")
    async def order_close(
        self, interaction: discord.Interaction, order_id: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if config.OFFICER_ROLE_ID and interaction.guild:
            role = interaction.guild.get_role(config.OFFICER_ROLE_ID)
            admin_role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
            has_perm = (role and role in interaction.user.roles) or (  # type: ignore[union-attr]
                admin_role and admin_role in interaction.user.roles  # type: ignore[union-attr]
            )
            if not has_perm:
                await interaction.followup.send("❌ Officers only.", ephemeral=True)
                return

        await db.close_order(order_id)
        await interaction.followup.send(f"✅ Order #{order_id} closed.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Orders(bot))
