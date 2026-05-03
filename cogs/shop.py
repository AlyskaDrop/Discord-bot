"""Shop cog — corporation goods / market."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db


class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="shop", description="Browse the corporation shop.")
    @app_commands.describe(category="Filter by category (e.g. ships, modules, ore)")
    async def shop(
        self, interaction: discord.Interaction, category: str | None = None
    ) -> None:
        await interaction.response.defer()
        items = await db.get_shop_items(category)

        embed = discord.Embed(
            title=f"🛒 Corp Shop{f' — {category}' if category else ''}",
            colour=discord.Colour.green(),
        )
        if not items:
            embed.description = "No items available."
        else:
            categories: dict[str, list[str]] = {}
            for item in items:
                cat = item["category"]
                line = (
                    f"**{item['name']}** — {item['price']:,.0f} ISK "
                    f"(qty: {item['quantity']})\n"
                    f"_{item['description']}_"
                )
                categories.setdefault(cat, []).append(line)

            for cat, lines in list(categories.items())[:5]:
                embed.add_field(
                    name=cat.title(),
                    value="\n\n".join(lines[:5]),
                    inline=False,
                )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="shop_add", description="Add an item to the shop (officers only).")
    @app_commands.describe(
        name="Item name",
        description="Item description",
        price="Price in ISK",
        quantity="Quantity available",
        category="Category (e.g. ships, modules, ore)",
    )
    async def shop_add(
        self,
        interaction: discord.Interaction,
        name: str,
        price: float,
        quantity: int = 1,
        description: str = "",
        category: str = "misc",
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if config.OFFICER_ROLE_ID and interaction.guild:
            officer_role = interaction.guild.get_role(config.OFFICER_ROLE_ID)
            admin_role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
            has_perm = (officer_role and officer_role in interaction.user.roles) or (  # type: ignore[union-attr]
                admin_role and admin_role in interaction.user.roles  # type: ignore[union-attr]
            )
            if not has_perm:
                await interaction.followup.send("❌ Officers only.", ephemeral=True)
                return

        item_id = await db.add_shop_item(
            interaction.user.id, name, description, price, quantity, category
        )
        await interaction.followup.send(
            f"✅ Item **{name}** (#{item_id}) added to the shop.", ephemeral=True
        )

    @app_commands.command(name="shop_remove", description="Remove a shop item (officers only).")
    @app_commands.describe(item_id="The item ID to remove")
    async def shop_remove(
        self, interaction: discord.Interaction, item_id: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if config.OFFICER_ROLE_ID and interaction.guild:
            officer_role = interaction.guild.get_role(config.OFFICER_ROLE_ID)
            admin_role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
            has_perm = (officer_role and officer_role in interaction.user.roles) or (  # type: ignore[union-attr]
                admin_role and admin_role in interaction.user.roles  # type: ignore[union-attr]
            )
            if not has_perm:
                await interaction.followup.send("❌ Officers only.", ephemeral=True)
                return

        await db.remove_shop_item(item_id)
        await interaction.followup.send(f"✅ Item #{item_id} removed.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shop(bot))
