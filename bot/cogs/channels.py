from __future__ import annotations

import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from ..checks import SYSTEM_CHANNEL_NAMES, is_staff_member, sanitize_channel_name, user_command_check
from ..embeds import docker_embed, failure_embed, success_embed, table_block

LOGGER = logging.getLogger(__name__)


class ChannelCog(commands.Cog):
    channel = app_commands.Group(name="channel", description="Mount and unmount channels inside your Dockerize container.")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @channel.command(name="create", description="Create a text or voice channel inside your container.")
    @app_commands.rename(kind="type")
    @app_commands.describe(name="New channel name", kind="Channel type")
    @app_commands.choices(
        kind=[
            app_commands.Choice(name="text", value="text"),
            app_commands.Choice(name="voice", value="voice"),
        ]
    )
    @user_command_check()
    async def create(self, interaction: discord.Interaction, name: str, kind: app_commands.Choice[str]) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await interaction.response.send_message(embed=failure_embed(config, "Channel allocation failed", "You do not have a Dockerize container yet."), ephemeral=True)
            return
        if row["status"] != "up":
            await interaction.response.send_message(embed=failure_embed(config, "Channel allocation failed", "Your container must be `up` before mounting channels."), ephemeral=True)
            return
        category = interaction.guild.get_channel(int(row["category_id"])) if row["category_id"] else None
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(embed=failure_embed(config, "Channel allocation failed", "Container category is missing. Run `/container up` first."), ephemeral=True)
            return
        if len(category.channels) >= config.max_channels_per_container:
            await interaction.response.send_message(embed=failure_embed(config, "Channel allocation failed", "You reached the maximum channel limit for this container."), ephemeral=True)
            return

        channel_name = sanitize_channel_name(name)
        try:
            if kind.value == "voice":
                created = await category.create_voice_channel(channel_name, reason="Dockerize user channel mount")
                channel_type = "voice"
            else:
                created = await category.create_text_channel(channel_name, reason="Dockerize user channel mount")
                channel_type = "text"
            await db.add_container_channel(interaction.guild.id, interaction.user.id, created.id, created.name, channel_type, False)
        except (discord.Forbidden, discord.HTTPException):
            LOGGER.exception("Failed to create channel")
            await interaction.response.send_message(embed=failure_embed(config, "Channel allocation failed", "Discord rejected the channel creation request."), ephemeral=True)
            return

        display = created.mention if hasattr(created, "mention") else f"`{created.name}`"
        embed = success_embed(config, "Channel mounted", f"The channel {display} was created inside your container.")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @channel.command(name="delete", description="Delete a channel from your container.")
    @app_commands.describe(channel="Channel to delete", confirm="Must be true", force="Staff-only: allow deleting system channels")
    @user_command_check()
    async def delete(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | discord.VoiceChannel,
        confirm: bool,
        force: bool = False,
    ) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        if not confirm:
            await interaction.response.send_message(embed=failure_embed(config, "Channel unmount cancelled", "Set `confirm:true` to delete the channel."), ephemeral=True)
            return
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        staff = await is_staff_member(interaction)
        if not row and staff:
            # Staff may force-delete a system channel inside any registered category.
            channel_record = await db.get_channel_record(interaction.guild.id, channel.id)
            if channel_record:
                row = await db.get_container(interaction.guild.id, int(channel_record["owner_id"]))
        if not row:
            await interaction.response.send_message(embed=failure_embed(config, "Channel unmount failed", "You do not have a Dockerize container yet."), ephemeral=True)
            return
        if channel.category_id != int(row["category_id"]):
            await interaction.response.send_message(embed=failure_embed(config, "Channel unmount failed", "That channel is not inside your container."), ephemeral=True)
            return

        record = await db.get_channel_record(interaction.guild.id, channel.id)
        is_system = bool(record and record["is_system"]) or channel.name in SYSTEM_CHANNEL_NAMES
        if is_system and not (force and staff):
            await interaction.response.send_message(
                embed=failure_embed(config, "Channel unmount failed", "System channels cannot be deleted unless staff uses `force:true`."),
                ephemeral=True,
            )
            return

        try:
            await channel.delete(reason="Dockerize channel unmount")
            await db.remove_container_channel(interaction.guild.id, channel.id)
        except (discord.Forbidden, discord.HTTPException):
            LOGGER.exception("Failed to delete channel")
            await interaction.response.send_message(embed=failure_embed(config, "Channel unmount failed", "Discord rejected the channel deletion request."), ephemeral=True)
            return

        embed = success_embed(config, "Channel unmounted", f"`#{channel.name}` was deleted from `{row['container_name']}`.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @channel.command(name="list", description="List channels mounted inside your container.")
    @user_command_check()
    async def list(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await interaction.response.send_message(embed=failure_embed(config, "Container not found", "You do not have a Dockerize container yet."), ephemeral=True)
            return
        channels = await db.list_container_channels(interaction.guild.id, interaction.user.id)
        rows: list[list[str]] = []
        for ch in channels:
            exists = interaction.guild.get_channel(int(ch["channel_id"])) is not None
            rows.append([
                f"#{ch['channel_name']}",
                ch["channel_type"],
                "system" if ch["is_system"] else "user",
                "mounted" if exists else "missing",
            ])
        table = table_block(["CHANNEL", "TYPE", "KIND", "STATE"], rows)
        embed = docker_embed(config, "Mounted channel volumes", f"Container: `{row['container_name']}`\n{table}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ChannelCog(bot))
