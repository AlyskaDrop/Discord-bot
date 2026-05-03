"""Admin cog — officer panel for approvals, credit, debit, role management."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db


def _is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    admin_role = interaction.guild.get_role(config.ADMIN_ROLE_ID)
    officer_role = interaction.guild.get_role(config.OFFICER_ROLE_ID)
    roles = interaction.user.roles  # type: ignore[union-attr]
    return bool(
        (admin_role and admin_role in roles)
        or (officer_role and officer_role in roles)
    )


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /admin_verify ──────────────────────────────────────────────────────────

    @app_commands.command(name="admin_verify", description="Verify a member's registration.")
    @app_commands.describe(member="Member to verify")
    async def admin_verify(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return

        await db.update_user(member.id, verified=1, corp_role="member")
        await interaction.followup.send(
            f"✅ {member.mention} verified as corp member.", ephemeral=True
        )

        # DM the member
        try:
            await member.send(
                f"🎉 Welcome to **{config.CORP_NAME}**! Your registration has been approved."
            )
        except discord.Forbidden:
            pass

    # ── /admin_credit ──────────────────────────────────────────────────────────

    @app_commands.command(name="admin_credit", description="Add ISK to a member's corp balance.")
    @app_commands.describe(member="Target member", amount="Amount to add (ISK)", reason="Reason")
    async def admin_credit(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: float,
        reason: str = "Admin credit",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return

        new_bal = await db.modify_balance(
            member.id, amount, tx_type="admin_credit", description=reason
        )
        embed = discord.Embed(
            title="💰 Balance Credited",
            colour=discord.Colour.green(),
        )
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Amount", value=f"+{amount:,.0f} ISK")
        embed.add_field(name="New Balance", value=f"{new_bal:,.0f} ISK")
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

        # log
        await self._log(interaction, embed)

    # ── /admin_debit ───────────────────────────────────────────────────────────

    @app_commands.command(name="admin_debit", description="Deduct ISK from a member's corp balance.")
    @app_commands.describe(member="Target member", amount="Amount to deduct (ISK)", reason="Reason")
    async def admin_debit(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: float,
        reason: str = "Admin debit",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return

        new_bal = await db.modify_balance(
            member.id, -amount, tx_type="admin_debit", description=reason
        )
        embed = discord.Embed(
            title="💸 Balance Debited",
            colour=discord.Colour.orange(),
        )
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Amount", value=f"-{amount:,.0f} ISK")
        embed.add_field(name="New Balance", value=f"{new_bal:,.0f} ISK")
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await self._log(interaction, embed)

    # ── /admin_give_role ───────────────────────────────────────────────────────

    @app_commands.command(name="admin_give_role", description="Grant a role to a member.")
    @app_commands.describe(member="Target member", role="Role to grant")
    async def admin_give_role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return
        try:
            await member.add_roles(role, reason=f"Granted by {interaction.user}")
            await interaction.followup.send(
                f"✅ Gave **{role.name}** to {member.mention}.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Missing permissions to assign that role.", ephemeral=True)

    # ── /admin_remove_role ─────────────────────────────────────────────────────

    @app_commands.command(name="admin_remove_role", description="Remove a role from a member.")
    @app_commands.describe(member="Target member", role="Role to remove")
    async def admin_remove_role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return
        try:
            await member.remove_roles(role, reason=f"Removed by {interaction.user}")
            await interaction.followup.send(
                f"✅ Removed **{role.name}** from {member.mention}.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Missing permissions.", ephemeral=True)

    # ── /admin_approve_kill ────────────────────────────────────────────────────

    @app_commands.command(name="admin_approve_kill", description="Approve a PvP kill and award points.")
    @app_commands.describe(kill_id="Kill ID to approve")
    async def admin_approve_kill(
        self, interaction: discord.Interaction, kill_id: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return

        # fetch kill
        async with db.connect() as conn:
            cur = await conn.execute(
                "SELECT * FROM kills WHERE id = ?", (kill_id,)
            )
            _row = await cur.fetchone()
            kill = dict(_row) if _row else {}

        if not kill:
            await interaction.followup.send(f"❌ Kill #{kill_id} not found.", ephemeral=True)
            return

        await db.approve_kill(kill_id)

        # award points to reporter
        async with db.connect() as conn:
            cur = await conn.execute(
                "SELECT discord_id FROM users WHERE id = ?", (kill["reporter_id"],)
            )
            row = await cur.fetchone()

        if row:
            pts = await db.add_points(row["discord_id"], pvp=config.PVP_KILL_POINTS)
            await interaction.followup.send(
                f"✅ Kill #{kill_id} approved! "
                f"+{config.PVP_KILL_POINTS} PvP points awarded. "
                f"Total PvP: {pts['pvp_points']}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(f"✅ Kill #{kill_id} approved.", ephemeral=True)

    # ── /admin_approve_comp ────────────────────────────────────────────────────

    @app_commands.command(name="admin_approve_comp", description="Approve a ship loss compensation.")
    @app_commands.describe(comp_id="Compensation ID to approve")
    async def admin_approve_comp(
        self, interaction: discord.Interaction, comp_id: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return

        async with db.connect() as conn:
            cur = await conn.execute(
                "SELECT c.*, u.discord_id FROM compensations c JOIN users u ON c.user_id = u.id WHERE c.id = ?",
                (comp_id,),
            )
            comp = dict(await cur.fetchone() or {})

        if not comp:
            await interaction.followup.send(f"❌ Compensation #{comp_id} not found.", ephemeral=True)
            return

        await db.resolve_compensation(comp_id, approve=True)
        new_bal = await db.modify_balance(
            comp["discord_id"],
            comp["amount_paid"],
            tx_type="compensation",
            description=f"Ship loss compensation #{comp_id}: {comp['ship_name']}",
        )
        await interaction.followup.send(
            f"✅ Compensation #{comp_id} approved. "
            f"**{comp['amount_paid']:,.0f} ISK** credited. New balance: {new_bal:,.0f} ISK.",
            ephemeral=True,
        )

    # ── /admin_reject_comp ─────────────────────────────────────────────────────

    @app_commands.command(name="admin_reject_comp", description="Reject a ship loss compensation.")
    @app_commands.describe(comp_id="Compensation ID to reject")
    async def admin_reject_comp(
        self, interaction: discord.Interaction, comp_id: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return
        await db.resolve_compensation(comp_id, approve=False)
        await interaction.followup.send(f"❌ Compensation #{comp_id} rejected.", ephemeral=True)

    # ── /admin_pending ─────────────────────────────────────────────────────────

    @app_commands.command(name="admin_pending", description="List all pending compensations.")
    async def admin_pending(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return

        comps = await db.get_pending_compensations()
        embed = discord.Embed(title="⏳ Pending Compensations", colour=discord.Colour.orange())
        if not comps:
            embed.description = "No pending compensations."
        else:
            lines = []
            for c in comps:
                name = c.get("ingame_name") or f"<@{c['discord_id']}>"
                lines.append(
                    f"**#{c['id']}** {name} — {c['ship_name']} — "
                    f"{c['ship_value']:,.0f} ISK → {c['amount_paid']:,.0f} ISK"
                )
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /admin_members ─────────────────────────────────────────────────────────

    @app_commands.command(name="admin_members", description="List all registered members.")
    async def admin_members(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            await interaction.followup.send("❌ Admin/Officer only.", ephemeral=True)
            return

        users = await db.get_all_users()
        embed = discord.Embed(title="👥 Registered Members", colour=discord.Colour.blue())
        lines = []
        for u in users[:25]:
            status = "✅" if u["verified"] else "⏳"
            lines.append(
                f"{status} <@{u['discord_id']}> — **{u['ingame_name'] or '—'}** [{u['corp_role']}]"
            )
        embed.description = "\n".join(lines) or "No members yet."
        if len(users) > 25:
            embed.set_footer(text=f"Showing 25 of {len(users)} members.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── internal ───────────────────────────────────────────────────────────────

    async def _log(self, interaction: discord.Interaction, embed: discord.Embed) -> None:
        if not config.LOG_CHANNEL_ID:
            return
        ch = self.bot.get_channel(config.LOG_CHANNEL_ID)
        if ch:
            log_embed = embed.copy()
            log_embed.add_field(
                name="Admin", value=interaction.user.mention, inline=False
            )
            await ch.send(embed=log_embed)  # type: ignore[union-attr]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
