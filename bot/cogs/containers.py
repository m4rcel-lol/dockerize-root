from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from ..animations import CREATE_FRAMES, DELETE_FRAMES, DOWN_FRAMES, UP_FRAMES, play_terminal_animation
from ..checks import ensure_bot_can_manage, fetch_member_safe, safe_dm, sanitize_name, user_command_check
from ..database import utcnow_iso
from ..embeds import (
    container_id,
    dm_note,
    docker_embed,
    edit_or_send,
    failure_embed,
    format_discord_time,
    success_embed,
    table_block,
    warning_embed,
)
from ..permissions import (
    apply_container_down,
    apply_container_private,
    apply_container_public,
    build_private_overwrites,
    build_public_overwrites,
    restore_container_permissions,
)

LOGGER = logging.getLogger(__name__)


async def _staff_role(bot: commands.Bot, guild: discord.Guild) -> discord.Role | None:
    settings = await bot.database.get_guild_settings(guild.id)  # type: ignore[attr-defined]
    if not settings or not settings["staff_role_id"]:
        return None
    return guild.get_role(int(settings["staff_role_id"]))


def _category_name(container_name: str) -> str:
    return f"🐳 {container_name}"[:100]


def _suspended_name(member: discord.Member | discord.User) -> str:
    safe = sanitize_name(member.name, max_length=48, fallback="user")
    return f"suspended-{safe}"[:100]


def _channel_count(guild: discord.Guild, row: Any) -> int:
    if not row or not row["category_id"]:
        return 0
    category = guild.get_channel(int(row["category_id"]))
    if isinstance(category, discord.CategoryChannel):
        return len(category.channels)
    return 0


async def _delete_category_tree(category: discord.CategoryChannel | None, *, reason: str) -> None:
    if category is None:
        return
    for channel in list(category.channels):
        try:
            await channel.delete(reason=reason)
        except (discord.Forbidden, discord.HTTPException):
            LOGGER.warning("Failed to delete child channel %s", channel.id)
    try:
        await category.delete(reason=reason)
    except (discord.Forbidden, discord.HTTPException):
        LOGGER.warning("Failed to delete category %s", category.id)


async def _create_default_channels(category: discord.CategoryChannel) -> tuple[discord.TextChannel, discord.TextChannel, discord.TextChannel, discord.VoiceChannel]:
    terminal = await category.create_text_channel("terminal", reason="Dockerize system channel")
    logs = await category.create_text_channel("logs", reason="Dockerize system channel")
    general = await category.create_text_channel("general", reason="Dockerize system channel")
    runtime = await category.create_voice_channel("runtime", reason="Dockerize runtime voice channel")
    return terminal, logs, general, runtime


async def _ensure_runtime_objects(bot: commands.Bot, guild: discord.Guild, row: Any) -> Any:
    owner = await fetch_member_safe(guild, int(row["owner_id"]))
    if owner is None:
        return row
    staff_role = await _staff_role(bot, guild)
    bot_member = guild.me
    if bot_member is None:
        return row

    category = guild.get_channel(int(row["category_id"])) if row["category_id"] else None
    if not isinstance(category, discord.CategoryChannel):
        if row["visibility"] == "public":
            overwrites = build_public_overwrites(guild, owner, staff_role, bot_member)
        else:
            overwrites = build_private_overwrites(guild, owner, staff_role, bot_member)
        category = await guild.create_category(_category_name(row["container_name"]), overwrites=overwrites, reason="Dockerize recreated missing category")
        await bot.database.update_container(guild.id, owner.id, category_id=category.id)  # type: ignore[attr-defined]

    updated: dict[str, int] = {}
    system_channels: list[tuple[int, str, str, bool]] = []

    async def ensure_text(field: str, name: str) -> discord.TextChannel:
        channel_id = row[field]
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if not isinstance(channel, discord.TextChannel) or channel.category_id != category.id:
            channel = await category.create_text_channel(name, reason="Dockerize recreated missing system text channel")
            updated[field] = channel.id
        system_channels.append((channel.id, channel.name, "text", True))
        return channel

    async def ensure_voice(field: str, name: str) -> discord.VoiceChannel:
        channel_id = row[field]
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if not isinstance(channel, discord.VoiceChannel) or channel.category_id != category.id:
            channel = await category.create_voice_channel(name, reason="Dockerize recreated missing runtime voice channel")
            updated[field] = channel.id
        system_channels.append((channel.id, channel.name, "voice", True))
        return channel

    await ensure_text("terminal_channel_id", "terminal")
    await ensure_text("logs_channel_id", "logs")
    await ensure_text("general_channel_id", "general")
    await ensure_voice("voice_channel_id", "runtime")

    if updated:
        await bot.database.update_container(guild.id, owner.id, **updated)  # type: ignore[attr-defined]
    await bot.database.add_many_container_channels(guild.id, owner.id, system_channels)  # type: ignore[attr-defined]
    return await bot.database.get_container(guild.id, owner.id)  # type: ignore[attr-defined]


class ContainerCog(commands.Cog):
    container = app_commands.Group(name="container", description="Manage your Dockerize container.")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @container.command(name="create", description="Create your private Dockerize container.")
    @app_commands.describe(name="Container name, for example marcel or projects")
    @user_command_check(allow_inside_container=False)
    async def create(self, interaction: discord.Interaction, name: str) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.defer(thinking=True)
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        await ensure_bot_can_manage(interaction)

        existing = await db.get_container(interaction.guild.id, interaction.user.id)
        if existing:
            await edit_or_send(
                interaction,
                failure_embed(config, "Container failed to start", "```console\nError: container already exists for this user\n```\nYou already have a Dockerize container in this server."),
                ephemeral=True,
            )
            return

        staff_role = await _staff_role(self.bot, interaction.guild)
        bot_member = interaction.guild.me
        if bot_member is None:
            await edit_or_send(interaction, failure_embed(config, "Container failed to start", "Bot member could not be resolved."), ephemeral=True)
            return

        container_name = sanitize_name(name, prefix="container-", max_length=64, fallback=f"container-{interaction.user.name}")
        visibility = config.default_container_visibility
        overwrites = (
            build_public_overwrites(interaction.guild, interaction.user, staff_role, bot_member)
            if visibility == "public"
            else build_private_overwrites(interaction.guild, interaction.user, staff_role, bot_member)
        )

        category: discord.CategoryChannel | None = None
        try:
            category = await interaction.guild.create_category(_category_name(container_name), overwrites=overwrites, reason="Dockerize container create")
            terminal, logs, general, runtime = await _create_default_channels(category)
            await db.create_container(
                guild_id=interaction.guild.id,
                owner_id=interaction.user.id,
                container_name=container_name,
                category_id=category.id,
                terminal_channel_id=terminal.id,
                logs_channel_id=logs.id,
                general_channel_id=general.id,
                voice_channel_id=runtime.id,
                status="up",
                visibility=visibility,
            )
            await db.add_many_container_channels(
                interaction.guild.id,
                interaction.user.id,
                [
                    (terminal.id, terminal.name, "text", True),
                    (logs.id, logs.name, "text", True),
                    (general.id, general.name, "text", True),
                    (runtime.id, runtime.name, "voice", True),
                ],
            )
        except Exception:
            LOGGER.exception("Container creation failed")
            await _delete_category_tree(category, reason="Dockerize rollback after failed create")
            await edit_or_send(interaction, failure_embed(config, "Container failed to start", "```console\nError: Discord rejected the category/channel allocation.\n```"), ephemeral=True)
            return

        dm_ok = await safe_dm(
            interaction.user,
            docker_embed(config, "Your Dockerize container is online", "Your private container has been created and started."),
        )
        LOGGER.info("Container created guild=%s owner=%s name=%s", interaction.guild.id, interaction.user.id, container_name)

        final = success_embed(
            config,
            "Container started",
            (
                "Your Dockerize container is now online.\n\n"
                f"Container: `{container_name}`\n"
                "Status: `up`\n"
                f"Visibility: `{visibility}`\n"
                "Channels:\n"
                f"{terminal.mention}\n{logs.mention}\n{general.mention}\n🔊 {runtime.mention}\n\n"
                f"Notification: `{dm_note(dm_ok)}`"
            ),
        )
        await play_terminal_animation(interaction, "docker compose up -d", CREATE_FRAMES, final)

    @container.command(name="up", description="Start your existing Dockerize container.")
    @user_command_check()
    async def up(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        await interaction.response.defer(thinking=True)
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await edit_or_send(interaction, failure_embed(config, "Container not found", "```console\nError: no container exists for this user\n```"), ephemeral=True)
            return
        if row["status"] == "suspended":
            await edit_or_send(interaction, failure_embed(config, "Container locked", "This container is suspended by staff and cannot be started."), ephemeral=True)
            return

        row = await _ensure_runtime_objects(self.bot, interaction.guild, row)
        await db.update_container(interaction.guild.id, interaction.user.id, status="up", suspended_reason=None)
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        await restore_container_permissions(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))

        dm_ok = await safe_dm(interaction.user, docker_embed(config, "Your Dockerize container is online", "Your container was put up and permission layers were restored."))
        final = success_embed(config, "Container started", f"Container: `{row['container_name']}`\nStatus: `up`\nNotification: `{dm_note(dm_ok)}`")
        await play_terminal_animation(interaction, "docker start", UP_FRAMES, final)

    @container.command(name="down", description="Stop your container without deleting it.")
    @user_command_check()
    async def down(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        await interaction.response.defer(thinking=True)
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await edit_or_send(interaction, failure_embed(config, "Container not found", "```console\nError: no container exists for this user\n```"), ephemeral=True)
            return
        if row["status"] == "suspended":
            await edit_or_send(interaction, failure_embed(config, "Container locked", "Suspended containers can only be changed by staff."), ephemeral=True)
            return

        await apply_container_down(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
        await db.update_container(interaction.guild.id, interaction.user.id, status="down")
        dm_ok = await safe_dm(interaction.user, docker_embed(config, "Your Dockerize container was stopped", "Your category is hidden from users, but staff can still inspect it."))
        final = docker_embed(config, "Container stopped", f"Container: `{row['container_name']}`\nStatus: `down`\nNotification: `{dm_note(dm_ok)}`")
        await play_terminal_animation(interaction, "docker stop", DOWN_FRAMES, final)

    @container.command(name="delete", description="Delete your Dockerize container permanently.")
    @app_commands.describe(confirm="Must be true to permanently delete your container")
    @user_command_check()
    async def delete(self, interaction: discord.Interaction, confirm: bool) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        if not confirm:
            await interaction.response.send_message(embed=failure_embed(config, "Deletion not confirmed", "Run `/container delete confirm:true` to remove your container."), ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await edit_or_send(interaction, failure_embed(config, "Container not found", "```console\nError: no container exists for this user\n```"), ephemeral=True)
            return

        category = interaction.guild.get_channel(int(row["category_id"])) if row["category_id"] else None
        await _delete_category_tree(category if isinstance(category, discord.CategoryChannel) else None, reason="Dockerize user container delete")
        await db.delete_container(interaction.guild.id, interaction.user.id)
        dm_ok = await safe_dm(interaction.user, failure_embed(config, "Your Dockerize container was deleted", "Your container category, channels, invite records, and database record were removed."))
        LOGGER.info("Container deleted guild=%s owner=%s", interaction.guild.id, interaction.user.id)
        final = failure_embed(config, "Container deleted", f"Container: `{row['container_name']}`\nStatus: `deleted`\nNotification: `{dm_note(dm_ok)}`")
        await play_terminal_animation(interaction, "docker compose down", DELETE_FRAMES, final)

    @container.command(name="status", description="Show your Dockerize container status.")
    @user_command_check()
    async def status(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await interaction.response.send_message(embed=failure_embed(config, "Container not found", "You do not have a Dockerize container yet."), ephemeral=True)
            return
        invites = await db.list_invites(interaction.guild.id, interaction.user.id)
        table = table_block(
            ["CONTAINER ID", "OWNER", "STATUS", "VISIBILITY", "CHANNELS"],
            [[container_id(row), interaction.user.name[:12], row["status"], row["visibility"], str(_channel_count(interaction.guild, row))]],
        )
        embed = docker_embed(
            config,
            "docker ps",
            (
                f"{table}\n"
                f"Container: `{row['container_name']}`\n"
                f"Owner: {interaction.user.mention}\n"
                f"Created: {format_discord_time(row['created_at'])}\n"
                f"Invited users: `{len(invites)}`\n"
                f"Inspection active: `{'yes' if row['inspection_active'] else 'no'}`\n"
                f"Suspended: `{'yes' if row['status'] == 'suspended' else 'no'}`"
            ),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @container.command(name="public", description="Make your container visible to everyone.")
    @user_command_check()
    async def public(self, interaction: discord.Interaction) -> None:
        await self._set_visibility(interaction, "public")

    @container.command(name="private", description="Make your container private again.")
    @user_command_check()
    async def private(self, interaction: discord.Interaction) -> None:
        await self._set_visibility(interaction, "private")

    async def _set_visibility(self, interaction: discord.Interaction, visibility: str) -> None:
        if interaction.guild is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await edit_or_send(interaction, failure_embed(config, "Container not found", "You do not have a container yet."), ephemeral=True)
            return
        if row["status"] == "suspended":
            await edit_or_send(interaction, failure_embed(config, "Container locked", "Suspended containers cannot change visibility."), ephemeral=True)
            return
        await db.update_container(interaction.guild.id, interaction.user.id, visibility=visibility)
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if visibility == "public":
            await apply_container_public(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
            embed = success_embed(config, "Container published", f"`{row['container_name']}` is now public. Everyone can view/send/connect inside it.")
        else:
            await apply_container_private(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
            embed = success_embed(config, "Container privatized", f"`{row['container_name']}` is private again. Invited users and staff still have access.")
        await edit_or_send(interaction, embed, ephemeral=True)

    @container.command(name="invite", description="Invite a user into your private container.")
    @app_commands.describe(user="User to invite")
    @user_command_check()
    async def invite(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await interaction.response.send_message(embed=failure_embed(config, "Invite failed", "You do not have a container yet."), ephemeral=True)
            return
        if row["status"] == "suspended":
            await interaction.response.send_message(embed=failure_embed(config, "Invite failed", "Suspended containers cannot invite users."), ephemeral=True)
            return
        if user.id == interaction.user.id:
            await interaction.response.send_message(embed=failure_embed(config, "Invite failed", "You already own this container."), ephemeral=True)
            return
        if user.bot and not config.allow_bot_invites:
            await interaction.response.send_message(embed=failure_embed(config, "Invite failed", "Bot invites are disabled by configuration."), ephemeral=True)
            return
        invited_container = await db.get_container(interaction.guild.id, user.id)
        if invited_container and invited_container["status"] == "suspended":
            await interaction.response.send_message(embed=failure_embed(config, "Invite failed", "This user has a suspended container in this server."), ephemeral=True)
            return

        await db.add_invite(interaction.guild.id, interaction.user.id, user.id)
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        await restore_container_permissions(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
        dm_ok = await safe_dm(
            user,
            docker_embed(
                config,
                "You were invited to a Dockerize container",
                (
                    f"{interaction.user.mention} invited you to access their container in **{interaction.guild.name}**.\n\n"
                    f"Container: `{row['container_name']}`\n"
                    f"Status: `{row['status']}`\n"
                    f"Visibility: `{row['visibility']}`"
                ),
            ),
        )
        embed = success_embed(config, "Container access granted", f"{user.mention} was invited to `{row['container_name']}`.\nNotification: `{dm_note(dm_ok)}`")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @container.command(name="uninvite", description="Remove a user from your container.")
    @app_commands.describe(user="User to remove")
    @user_command_check()
    async def uninvite(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await interaction.response.send_message(embed=failure_embed(config, "Uninvite failed", "You do not have a container yet."), ephemeral=True)
            return
        await db.remove_invite(interaction.guild.id, interaction.user.id, user.id)
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if row["status"] == "suspended":
            await apply_container_down(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
        else:
            await restore_container_permissions(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
        dm_ok = await safe_dm(user, warning_embed(config, "Container access removed", f"Your access to {interaction.user.mention}'s Dockerize container was removed."))
        embed = success_embed(config, "Container access removed", f"{user.mention} was removed from `{row['container_name']}`.\nNotification: `{dm_note(dm_ok)}`")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @container.command(name="invites", description="List users invited to your container.")
    @user_command_check()
    async def invites(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, interaction.user.id)
        if not row:
            await interaction.response.send_message(embed=failure_embed(config, "Container not found", "You do not have a container yet."), ephemeral=True)
            return
        invites = await db.list_invites(interaction.guild.id, interaction.user.id)
        if not invites:
            description = "No users are invited to this container."
        else:
            description = "\n".join(f"• <@{invite['invited_user_id']}>" for invite in invites)
        embed = docker_embed(config, "Container invite table", f"Container: `{row['container_name']}`\n\n{description}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ContainerCog(bot))
