"""Registration cog — players register by uploading a character screenshot."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import database as db
from utils.ocr import extract_character_name


class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /register ──────────────────────────────────────────────────────────────

    @app_commands.command(
        name="register",
        description="Register in the Weeping Ghosts corporation database.",
    )
    @app_commands.describe(
        ingame_name="Your in-game character name (optional if you upload a screenshot)",
        screenshot="Screenshot of your character profile (optional)",
    )
    async def register(
        self,
        interaction: discord.Interaction,
        ingame_name: str | None = None,
        screenshot: discord.Attachment | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        existing = await db.get_user(interaction.user.id)
        if existing and existing["verified"]:
            await interaction.followup.send(
                "✅ You are already registered and verified!", ephemeral=True
            )
            return

        detected_name = ingame_name or ""

        # OCR fallback
        if screenshot and not detected_name:
            data = await screenshot.read()
            detected_name = extract_character_name(data)

        if not detected_name:
            await interaction.followup.send(
                "❌ Could not determine your in-game name. "
                "Please provide your name or upload a character screenshot.",
                ephemeral=True,
            )
            return

        user = await db.create_user(interaction.user.id, detected_name)
        await db.update_user(interaction.user.id, ingame_name=detected_name)

        # Assign pending member role if configured
        if config.MEMBER_ROLE_ID:
            guild = interaction.guild
            if guild:
                role = guild.get_role(config.MEMBER_ROLE_ID)
                if role:
                    try:
                        await interaction.user.add_roles(role, reason="Corp registration")
                    except discord.Forbidden:
                        pass

        embed = discord.Embed(
            title="📋 Registration Received",
            description=(
                f"Welcome, **{detected_name}**!\n\n"
                "Your registration is pending officer review.\n"
                "You will be notified when your application is approved."
            ),
            colour=discord.Colour.blurple(),
        )
        embed.set_footer(text=config.CORP_NAME)
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Notify admin channel
        if config.ADMIN_CHANNEL_ID:
            admin_ch = self.bot.get_channel(config.ADMIN_CHANNEL_ID)
            if admin_ch:
                admin_embed = discord.Embed(
                    title="🆕 New Registration",
                    colour=discord.Colour.orange(),
                )
                admin_embed.add_field(name="Discord", value=interaction.user.mention)
                admin_embed.add_field(name="In-Game Name", value=detected_name)
                if screenshot:
                    admin_embed.set_image(url=screenshot.url)
                await admin_ch.send(embed=admin_embed)  # type: ignore[union-attr]

    # ── /profile ───────────────────────────────────────────────────────────────

    @app_commands.command(name="profile", description="View your or another member's profile.")
    @app_commands.describe(member="The member to look up (defaults to yourself)")
    async def profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        target = member or interaction.user
        user = await db.get_user(target.id)

        if not user:
            await interaction.followup.send(
                f"❌ {target.mention} is not registered.", ephemeral=True
            )
            return

        pts = await db.get_points(target.id)
        balance = await db.get_balance(target.id)

        embed = discord.Embed(
            title=f"👤 {user['ingame_name'] or target.display_name}",
            colour=discord.Colour.blue(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Discord", value=target.mention, inline=True)
        embed.add_field(
            name="Status",
            value="✅ Verified" if user["verified"] else "⏳ Pending",
            inline=True,
        )
        embed.add_field(name="Corp Role", value=user["corp_role"].title(), inline=True)
        embed.add_field(
            name="Balance",
            value=f"{balance:,.0f} ISK",
            inline=True,
        )
        embed.add_field(name="PvP Points", value=str(pts["pvp_points"]), inline=True)
        embed.add_field(name="PvE Points", value=str(pts["pve_points"]), inline=True)
        embed.add_field(name="Registered", value=user["registered_at"][:10], inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Registration(bot))
