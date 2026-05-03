"""Calculators cog — profit, implant level, mining, production."""
from __future__ import annotations

import math

import discord
from discord import app_commands
from discord.ext import commands


# ── helpers ────────────────────────────────────────────────────────────────────

def _fmt(n: float) -> str:
    """Format ISK with thousand separators."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B ISK"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M ISK"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K ISK"
    return f"{n:,.0f} ISK"


# ── implant table (simplified Eve Echoes values) ──────────────────────────────
# Each level provides a percentage bonus to a given attribute
_IMPLANT_BONUSES: dict[int, float] = {
    1: 1.0,
    2: 2.0,
    3: 3.0,
    4: 4.0,
    5: 5.0,
    6: 6.0,
    7: 8.0,
    8: 10.0,
    9: 12.0,
    10: 15.0,
}

# Approximate ISK costs per implant slot level (per slot, rough market values)
_IMPLANT_COSTS: dict[int, float] = {
    1: 500_000,
    2: 1_500_000,
    3: 3_000_000,
    4: 6_000_000,
    5: 12_000_000,
    6: 25_000_000,
    7: 60_000_000,
    8: 150_000_000,
    9: 400_000_000,
    10: 1_000_000_000,
}


class Calculators(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /calc_profit ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="calc_profit",
        description="Calculate trade/industry profit margin.",
    )
    @app_commands.describe(
        buy_price="Purchase price per unit (ISK)",
        sell_price="Sale price per unit (ISK)",
        quantity="Number of units",
        broker_fee_pct="Broker fee percentage (default 2.5)",
        tax_pct="Sales tax percentage (default 1.5)",
    )
    async def calc_profit(
        self,
        interaction: discord.Interaction,
        buy_price: float,
        sell_price: float,
        quantity: int = 1,
        broker_fee_pct: float = 2.5,
        tax_pct: float = 1.5,
    ) -> None:
        total_buy = buy_price * quantity
        total_sell = sell_price * quantity
        fees = total_sell * (broker_fee_pct + tax_pct) / 100
        gross_profit = total_sell - total_buy
        net_profit = gross_profit - fees
        margin_pct = (net_profit / total_buy * 100) if total_buy else 0

        embed = discord.Embed(
            title="📊 Profit Calculator",
            colour=discord.Colour.green() if net_profit >= 0 else discord.Colour.red(),
        )
        embed.add_field(name="Buy Total", value=_fmt(total_buy), inline=True)
        embed.add_field(name="Sell Total", value=_fmt(total_sell), inline=True)
        embed.add_field(name="Fees", value=_fmt(fees), inline=True)
        embed.add_field(name="Net Profit", value=_fmt(net_profit), inline=True)
        embed.add_field(name="Margin", value=f"{margin_pct:.2f}%", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /calc_implant ──────────────────────────────────────────────────────────

    @app_commands.command(
        name="calc_implant",
        description="Calculate the bonus and cost for an implant level (1–10).",
    )
    @app_commands.describe(
        level="Implant level (1–10)",
        slots="Number of slots you are fitting",
        base_attribute="Your base attribute value (e.g. 100 for 100% efficiency)",
    )
    async def calc_implant(
        self,
        interaction: discord.Interaction,
        level: int,
        slots: int = 1,
        base_attribute: float = 100.0,
    ) -> None:
        level = max(1, min(10, level))
        slots = max(1, min(10, slots))

        bonus_pct = _IMPLANT_BONUSES[level]
        total_bonus = base_attribute * (1 + bonus_pct / 100 * slots) - base_attribute
        total_cost = _IMPLANT_COSTS[level] * slots

        embed = discord.Embed(
            title=f"🧠 Implant Level {level} Calculator",
            colour=discord.Colour.blurple(),
        )
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Bonus per slot", value=f"+{bonus_pct:.1f}%", inline=True)
        embed.add_field(name="Slots", value=str(slots), inline=True)
        embed.add_field(
            name="Total attribute bonus",
            value=f"+{total_bonus:.2f} (on base {base_attribute})",
            inline=False,
        )
        embed.add_field(
            name="Estimated cost",
            value=f"{_fmt(total_cost)} ({slots} × {_fmt(_IMPLANT_COSTS[level])})",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /calc_mining ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="calc_mining",
        description="Calculate expected ISK from a mining session.",
    )
    @app_commands.describe(
        ore_type="Name of the ore (e.g. Veldspar, Pyroxeres)",
        units="Number of units mined",
        price_per_unit="Market sell price per unit (ISK)",
        yield_pct="Refining yield percentage (default 72)",
    )
    async def calc_mining(
        self,
        interaction: discord.Interaction,
        ore_type: str,
        units: int,
        price_per_unit: float,
        yield_pct: float = 72.0,
    ) -> None:
        effective_yield = units * yield_pct / 100
        gross_isk = effective_yield * price_per_unit
        # approximate transport/broker cost at 3%
        net_isk = gross_isk * 0.97

        embed = discord.Embed(
            title=f"⛏️ Mining Calculator — {ore_type}",
            colour=discord.Colour.dark_grey(),
        )
        embed.add_field(name="Units Mined", value=f"{units:,}", inline=True)
        embed.add_field(name="Price / Unit", value=_fmt(price_per_unit), inline=True)
        embed.add_field(name="Refining Yield", value=f"{yield_pct:.0f}%", inline=True)
        embed.add_field(name="Effective Units", value=f"{effective_yield:,.1f}", inline=True)
        embed.add_field(name="Gross ISK", value=_fmt(gross_isk), inline=True)
        embed.add_field(name="Net ISK (−3% fees)", value=_fmt(net_isk), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /calc_production ───────────────────────────────────────────────────────

    @app_commands.command(
        name="calc_production",
        description="Estimate materials and costs for producing an item.",
    )
    @app_commands.describe(
        item_name="Name of the item to produce",
        runs="Number of production runs",
        material_cost_per_run="Total material cost per run (ISK)",
        sell_price="Expected sell price per unit (ISK)",
        me_bonus_pct="Material Efficiency bonus % (reduces material cost, default 0)",
        tax_pct="Industry tax % (default 5)",
    )
    async def calc_production(
        self,
        interaction: discord.Interaction,
        item_name: str,
        runs: int,
        material_cost_per_run: float,
        sell_price: float,
        me_bonus_pct: float = 0.0,
        tax_pct: float = 5.0,
    ) -> None:
        runs = max(1, runs)
        adjusted_mat_cost = material_cost_per_run * (1 - me_bonus_pct / 100)
        total_mat_cost = adjusted_mat_cost * runs
        tax = total_mat_cost * tax_pct / 100
        total_cost = total_mat_cost + tax
        total_revenue = sell_price * runs
        profit = total_revenue - total_cost
        margin = profit / total_cost * 100 if total_cost else 0

        embed = discord.Embed(
            title=f"🏭 Production Calculator — {item_name}",
            colour=discord.Colour.green() if profit >= 0 else discord.Colour.red(),
        )
        embed.add_field(name="Runs", value=str(runs), inline=True)
        embed.add_field(
            name="Mat Cost / Run",
            value=f"{_fmt(adjusted_mat_cost)} (ME {me_bonus_pct:.0f}%)",
            inline=True,
        )
        embed.add_field(name="Total Materials", value=_fmt(total_mat_cost), inline=True)
        embed.add_field(name="Industry Tax", value=_fmt(tax), inline=True)
        embed.add_field(name="Total Cost", value=_fmt(total_cost), inline=True)
        embed.add_field(name="Revenue", value=_fmt(total_revenue), inline=True)
        embed.add_field(name="Net Profit", value=_fmt(profit), inline=True)
        embed.add_field(name="Margin", value=f"{margin:.1f}%", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Calculators(bot))
