from __future__ import annotations

import logging
from math import ceil

import discord
from discord import app_commands
from discord.ext import commands

from ..animations import DELETE_FRAMES, SUSPEND_FRAMES, play_terminal_animation
from ..checks import safe_dm, staff_only_check
from ..embeds import (
    container_id,
    dm_note,
    docker_embed,
    edit_or_send,
    failure_embed,
    format_discord_time,
    success_embed,
    suspended_embed,
    table_block,
    warning_embed,
)
from ..permissions import apply_container_private, apply_container_public, apply_container_suspended, restore_container_permissions
from ..views import ContainerListView
from .containers import _category_name, _channel_count, _delete_category_tree, _staff_role, _suspended_name

LOGGER = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    admin = app_commands.Group(name="admin", description="Dockerize staff controls.")
    admin_container = app_commands.Group(name="container", description="Inspect and moderate containers.", parent=admin)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @admin_container.command(name="check", description="Mark a user's container as being inspected by staff.")
    @app_commands.describe(user="Container owner", reason="Why staff is checking this container")
    @staff_only_check()
    async def check(self, interaction: discord.Interaction, user: discord.Member, reason: str) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, user.id)
        if not row:
            await interaction.response.send_message(embed=failure_embed(config, "Inspection failed", "That user does not have a Dockerize container."), ephemeral=True)
            return
        await db.update_container(interaction.guild.id, user.id, inspection_active=1)
        dm_ok = await safe_dm(
            user,
            warning_embed(
                config,
                "Your Dockerize container is being checked",
                (
                    "A server staff member has started checking your container.\n\n"
                    f"Reason: {reason}\n"
                    "This does not mean you are suspended. It means staff is reviewing the container."
                ),
            ),
        )
        LOGGER.info("Container inspection started guild=%s owner=%s staff=%s reason=%s", interaction.guild.id, user.id, interaction.user.id, reason)
        embed = warning_embed(
            config,
            "Container inspection started",
            f"```console\n$ docker inspect {row['container_name']}\n[!] Staff inspection mode enabled\n[!] Owner notified\n```\nReason: {reason}\nNotification: `{dm_note(dm_ok)}`",
        )
        await interaction.response.send_message(embed=embed)

    @admin_container.command(name="suspend", description="Suspend a user's Dockerize container.")
    @app_commands.describe(user="Container owner", reason="Why this container is being suspended")
    @staff_only_check()
    async def suspend(self, interaction: discord.Interaction, user: discord.Member, reason: str) -> None:
        if interaction.guild is None:
            return
        await interaction.response.defer(thinking=True)
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, user.id)
        if not row:
            await edit_or_send(interaction, failure_embed(config, "Suspension failed", "That user does not have a Dockerize container."), ephemeral=True)
            return
        category = interaction.guild.get_channel(int(row["category_id"])) if row["category_id"] else None
        if isinstance(category, discord.CategoryChannel):
            try:
                await category.edit(name=_suspended_name(user), reason="Dockerize staff suspension")
            except discord.HTTPException:
                LOGGER.warning("Could not rename suspended category %s", category.id)
        await db.update_container(interaction.guild.id, user.id, status="suspended", inspection_active=1, suspended_reason=reason)
        row = await db.get_container(interaction.guild.id, user.id)
        await apply_container_suspended(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
        dm_ok = await safe_dm(user, suspended_embed(config, "Your Dockerize container was suspended", f"Reason: {reason}\n\nYou can no longer access the container until staff unsuspends it."))
        LOGGER.info("Container suspended guild=%s owner=%s staff=%s reason=%s", interaction.guild.id, user.id, interaction.user.id, reason)
        final = suspended_embed(config, "Runtime suspended", f"Container: `{row['container_name']}`\nOwner: {user.mention}\nReason: {reason}\nNotification: `{dm_note(dm_ok)}`")
        await play_terminal_animation(interaction, "docker container pause", SUSPEND_FRAMES, final)

    @admin_container.command(name="unsuspend", description="Unsuspend a user's Dockerize container.")
    @app_commands.describe(user="Container owner")
    @staff_only_check()
    async def unsuspend(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, user.id)
        if not row:
            await edit_or_send(interaction, failure_embed(config, "Unsuspend failed", "That user does not have a Dockerize container."), ephemeral=True)
            return
        category = interaction.guild.get_channel(int(row["category_id"])) if row["category_id"] else None
        if isinstance(category, discord.CategoryChannel):
            try:
                await category.edit(name=_category_name(row["container_name"]), reason="Dockerize staff unsuspension")
            except discord.HTTPException:
                LOGGER.warning("Could not rename unsuspended category %s", category.id)
        await db.update_container(interaction.guild.id, user.id, status="up", inspection_active=0, suspended_reason=None)
        row = await db.get_container(interaction.guild.id, user.id)
        await restore_container_permissions(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
        dm_ok = await safe_dm(user, success_embed(config, "Your Dockerize container was unsuspended", "Your container access has been restored."))
        embed = success_embed(config, "Runtime unsuspended", f"Container: `{row['container_name']}`\nOwner: {user.mention}\nStatus: `up`\nNotification: `{dm_note(dm_ok)}`")
        await edit_or_send(interaction, embed, ephemeral=True)

    @admin_container.command(name="delete", description="Delete another user's Dockerize container.")
    @app_commands.describe(user="Container owner", reason="Why staff is deleting this container")
    @staff_only_check()
    async def delete(self, interaction: discord.Interaction, user: discord.Member, reason: str) -> None:
        if interaction.guild is None:
            return
        await interaction.response.defer(thinking=True)
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, user.id)
        if not row:
            await edit_or_send(interaction, failure_embed(config, "Deletion failed", "That user does not have a Dockerize container."), ephemeral=True)
            return
        category = interaction.guild.get_channel(int(row["category_id"])) if row["category_id"] else None
        await _delete_category_tree(category if isinstance(category, discord.CategoryChannel) else None, reason="Dockerize staff container delete")
        await db.delete_container(interaction.guild.id, user.id)
        dm_ok = await safe_dm(user, failure_embed(config, "Your Dockerize container was deleted by staff", f"Reason: {reason}"))
        LOGGER.info("Container staff-deleted guild=%s owner=%s staff=%s reason=%s", interaction.guild.id, user.id, interaction.user.id, reason)
        final = failure_embed(config, "Container deleted", f"Container: `{row['container_name']}`\nOwner: {user.mention}\nReason: {reason}\nNotification: `{dm_note(dm_ok)}`")
        await play_terminal_animation(interaction, "docker compose down", DELETE_FRAMES, final)

    @admin_container.command(name="list", description="List all Dockerize containers in this server.")
    @staff_only_check()
    async def list(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        containers = await db.list_guild_containers(interaction.guild.id)
        per_page = 8
        pages: list[discord.Embed] = []
        total_pages = max(1, ceil(len(containers) / per_page))
        for page_index in range(total_pages):
            chunk = containers[page_index * per_page : (page_index + 1) * per_page]
            rows = []
            for row in chunk:
                rows.append([
                    container_id(row),
                    f"@{row['owner_id']}",
                    row["status"],
                    row["visibility"],
                ])
            embed = docker_embed(
                config,
                f"Container registry ({page_index + 1}/{total_pages})",
                table_block(["CONTAINER ID", "OWNER", "STATUS", "VISIBILITY"], rows),
            )
            pages.append(embed)
        view = ContainerListView(author_id=interaction.user.id, pages=pages) if len(pages) > 1 else None
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

    @admin_container.command(name="info", description="Show detailed information about a user's Dockerize container.")
    @app_commands.describe(user="Container owner")
    @staff_only_check()
    async def info(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if interaction.guild is None:
            return
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, user.id)
        if not row:
            await interaction.response.send_message(embed=failure_embed(config, "Info failed", "That user does not have a Dockerize container."), ephemeral=True)
            return
        invites = await db.list_invites(interaction.guild.id, user.id)
        channels = await db.list_container_channels(interaction.guild.id, user.id)
        category = interaction.guild.get_channel(int(row["category_id"])) if row["category_id"] else None
        fields = [
            ("Container ID", container_id(row), True),
            ("Owner", user.mention, True),
            ("Status", row["status"], True),
            ("Visibility", row["visibility"], True),
            ("Category", category.mention if isinstance(category, discord.CategoryChannel) else "missing", True),
            ("Channels", str(_channel_count(interaction.guild, row)), True),
            ("Invited", str(len(invites)), True),
            ("Inspection", "active" if row["inspection_active"] else "inactive", True),
            ("Created", format_discord_time(row["created_at"]), True),
        ]
        if row["suspended_reason"]:
            fields.append(("Suspended reason", row["suspended_reason"], False))
        channel_rows = [[f"#{c['channel_name']}", c["channel_type"], "system" if c["is_system"] else "user"] for c in channels]
        embed = docker_embed(config, "Container information", f"Container: `{row['container_name']}`\n{table_block(['CHANNEL', 'TYPE', 'KIND'], channel_rows)}", fields=fields)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_container.command(name="force-private", description="Force a user's container into private mode.")
    @app_commands.describe(user="Container owner")
    @staff_only_check()
    async def force_private(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self._force_visibility(interaction, user, "private")

    @admin_container.command(name="force-public", description="Force a user's container into public mode.")
    @app_commands.describe(user="Container owner")
    @staff_only_check()
    async def force_public(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self._force_visibility(interaction, user, "public")

    async def _force_visibility(self, interaction: discord.Interaction, user: discord.Member, visibility: str) -> None:
        if interaction.guild is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        config = self.bot.config  # type: ignore[attr-defined]
        db = self.bot.database  # type: ignore[attr-defined]
        row = await db.get_container(interaction.guild.id, user.id)
        if not row:
            await edit_or_send(interaction, failure_embed(config, "Visibility update failed", "That user does not have a Dockerize container."), ephemeral=True)
            return
        await db.update_container(interaction.guild.id, user.id, visibility=visibility)
        row = await db.get_container(interaction.guild.id, user.id)
        if row["status"] == "suspended":
            await apply_container_suspended(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
            note = "Suspended permission layer remains active."
        elif visibility == "public":
            await apply_container_public(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
            note = "Everyone can now view/send/connect inside the container."
        else:
            await apply_container_private(interaction.guild, db, row, await _staff_role(self.bot, interaction.guild))
            note = "Only owner, invited users, staff, and bot can access it."
        embed = success_embed(config, f"Container forced {visibility}", f"Container: `{row['container_name']}`\nOwner: {user.mention}\n{note}")
        await edit_or_send(interaction, embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
