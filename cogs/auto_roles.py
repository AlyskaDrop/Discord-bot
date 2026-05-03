"""Auto-roles cog — automatically assign roles based on points or balance thresholds."""
from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db


class AutoRoles(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── background task ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Seed default auto-role thresholds if the DB is empty."""
        rows = await db.get_auto_roles()
        if not rows:
            for threshold, role_name in config.AUTO_ROLE_THRESHOLDS:
                await db.add_auto_role(
                    role_id="0",  # placeholder — admin sets real IDs later
                    role_name=role_name,
                    condition_type="total_points",
                    condition_value=threshold,
                )

    async def _check_member(self, guild: discord.Guild, member: discord.Member) -> None:
        """Check and assign auto-roles for a single member."""
        pts = await db.get_points(member.id)
        total = pts["pvp_points"] + pts["pve_points"]
        balance = await db.get_balance(member.id)

        auto_roles = await db.get_auto_roles()
        for ar in auto_roles:
            if ar["role_id"] == "0":
                continue  # not yet configured
            role = guild.get_role(int(ar["role_id"]))
            if not role:
                continue

            value: float = (
                total if ar["condition_type"] == "total_points"
                else balance if ar["condition_type"] == "balance"
                else pts["pvp_points"] if ar["condition_type"] == "pvp_points"
                else pts["pve_points"]
            )

            if value >= ar["condition_value"]:
                if role not in member.roles:
                    try:
                        await member.add_roles(role, reason="Auto-role: threshold reached")
                        # notify in log channel
                        if config.LOG_CHANNEL_ID:
                            ch = self.bot.get_channel(config.LOG_CHANNEL_ID)
                            if ch:
                                await ch.send(  # type: ignore[union-attr]
                                    f"🏅 {member.mention} earned the **{role.name}** role "
                                    f"({ar['condition_type']} ≥ {ar['condition_value']})."
                                )
                    except discord.Forbidden:
                        pass

    async def check_all_members(self, guild: discord.Guild) -> None:
        for member in guild.members:
            if not member.bot:
                await self._check_member(guild, member)
                await asyncio.sleep(0.1)

    # ── /autorole_add ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="autorole_add",
        description="Add an automatic role threshold (admins only).",
    )
    @app_commands.describe(
        role="The role to auto-assign",
        condition_type="Condition type: total_points | pvp_points | pve_points | balance",
        condition_value="Minimum value to trigger the role assignment",
    )
    async def autorole_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        condition_value: int,
        condition_type: str = "total_points",
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if config.ADMIN_ROLE_ID and interaction.guild:
            admin_role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
            if not (admin_role and admin_role in interaction.user.roles):  # type: ignore[union-attr]
                await interaction.followup.send("❌ Admins only.", ephemeral=True)
                return

        valid_types = {"total_points", "pvp_points", "pve_points", "balance"}
        if condition_type not in valid_types:
            await interaction.followup.send(
                f"❌ condition_type must be one of: {', '.join(valid_types)}",
                ephemeral=True,
            )
            return

        await db.add_auto_role(
            str(role.id), role.name, condition_type, condition_value
        )
        await interaction.followup.send(
            f"✅ Auto-role **{role.name}** added: "
            f"`{condition_type}` ≥ **{condition_value}**.",
            ephemeral=True,
        )

    # ── /autorole_remove ────────────────────────────────────────────────────────

    @app_commands.command(name="autorole_remove", description="Remove an auto-role rule.")
    @app_commands.describe(role="The role whose auto-assign rule should be removed")
    async def autorole_remove(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if config.ADMIN_ROLE_ID and interaction.guild:
            admin_role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
            if not (admin_role and admin_role in interaction.user.roles):  # type: ignore[union-attr]
                await interaction.followup.send("❌ Admins only.", ephemeral=True)
                return

        await db.remove_auto_role(str(role.id))
        await interaction.followup.send(
            f"✅ Auto-role rule for **{role.name}** removed.", ephemeral=True
        )

    # ── /autorole_list ──────────────────────────────────────────────────────────

    @app_commands.command(name="autorole_list", description="List all auto-role rules.")
    async def autorole_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        rows = await db.get_auto_roles()
        embed = discord.Embed(title="🏅 Auto-Role Rules", colour=discord.Colour.gold())
        if not rows:
            embed.description = "No rules configured."
        else:
            lines = []
            for ar in rows:
                rid = int(ar["role_id"]) if ar["role_id"] != "0" else 0
                role_mention = f"<@&{rid}>" if rid else ar["role_name"]
                lines.append(
                    f"• {role_mention} — `{ar['condition_type']}` ≥ **{ar['condition_value']}**"
                )
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /autorole_run ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="autorole_run",
        description="Manually run auto-role check for all members (admins only).",
    )
    async def autorole_run(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if config.ADMIN_ROLE_ID and interaction.guild:
            admin_role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
            if not (admin_role and admin_role in interaction.user.roles):  # type: ignore[union-attr]
                await interaction.followup.send("❌ Admins only.", ephemeral=True)
                return

        if not interaction.guild:
            return

        asyncio.create_task(self.check_all_members(interaction.guild))
        await interaction.followup.send(
            "✅ Auto-role check started in the background.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoRoles(bot))
