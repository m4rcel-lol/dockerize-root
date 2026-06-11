from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from ..checks import ensure_bot_can_manage
from ..embeds import success_embed

LOGGER = logging.getLogger(__name__)


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="setup", description="Initialize Dockerize in this server.")
    @app_commands.describe(command_channel="Channel where users may run Dockerize commands", staff_role="Role allowed to inspect/manage containers")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, command_channel: discord.TextChannel, staff_role: discord.Role) -> None:
        if interaction.guild is None:
            return
        await ensure_bot_can_manage(interaction)
        await self.bot.database.upsert_guild_settings(interaction.guild.id, command_channel.id, staff_role.id)  # type: ignore[attr-defined]
        LOGGER.info("Guild %s initialized Dockerize: channel=%s staff_role=%s", interaction.guild.id, command_channel.id, staff_role.id)

        embed = success_embed(
            self.bot.config,  # type: ignore[attr-defined]
            "Dockerize daemon initialized",
            (
                "The Dockerize runtime has been attached to this server.\n\n"
                f"Command Channel: {command_channel.mention}\n"
                f"Staff Role: {staff_role.mention}\n"
                "Container Mode: `user-isolated`\n"
                "Status: `online`"
            ),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupCog(bot))
