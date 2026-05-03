"""AI Agent cog — conversational assistant powered by OpenAI."""
from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config

_SYSTEM_PROMPT = (
    "You are GHOST-AI, the intelligent assistant of the Weeping Ghosts corporation "
    "in Eve Echoes. You help members with game mechanics, corp rules, market advice, "
    "PvP tactics, fitting advice, and general questions about Eve Echoes. "
    "Be concise, helpful, and in character as a space corporation AI."
)

# Conversation history stored per user (discord_id → list of messages)
_histories: dict[int, list[dict]] = {}
_MAX_HISTORY = 10  # keep last N exchanges


class AIAgent(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._client = None

    def _get_client(self):
        if not config.OPENAI_API_KEY:
            return None
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            except ImportError:
                return None
        return self._client

    @app_commands.command(
        name="ai",
        description="Ask the GHOST-AI assistant a question about Eve Echoes or corp matters.",
    )
    @app_commands.describe(question="Your question for the AI")
    async def ai(self, interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer(ephemeral=True)

        client = self._get_client()
        if not client:
            await interaction.followup.send(
                "⚠️ AI agent is not configured. Set `OPENAI_API_KEY` in your `.env` file.",
                ephemeral=True,
            )
            return

        uid = interaction.user.id
        history = _histories.setdefault(uid, [])
        history.append({"role": "user", "content": question})

        messages = [{"role": "system", "content": _SYSTEM_PROMPT}] + history[
            -_MAX_HISTORY * 2 :
        ]

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
                temperature=0.7,
            )
            answer = response.choices[0].message.content or "(no response)"
        except Exception as exc:
            answer = f"❌ AI error: {exc}"

        history.append({"role": "assistant", "content": answer})
        # trim history
        while len(history) > _MAX_HISTORY * 2:
            history.pop(0)

        embed = discord.Embed(
            title="🤖 GHOST-AI",
            colour=discord.Colour.purple(),
        )
        embed.add_field(name="You asked", value=question[:1024], inline=False)
        embed.add_field(name="Answer", value=answer[:1024], inline=False)
        embed.set_footer(text="GHOST-AI may make mistakes — always verify in-game.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="ai_reset", description="Clear your AI conversation history.")
    async def ai_reset(self, interaction: discord.Interaction) -> None:
        _histories.pop(interaction.user.id, None)
        await interaction.response.send_message(
            "🗑️ Conversation history cleared.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AIAgent(bot))
