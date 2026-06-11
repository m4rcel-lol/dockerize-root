from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from .database import Database

LOGGER = logging.getLogger(__name__)
_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]+")
SYSTEM_CHANNEL_NAMES = {"terminal", "logs", "general", "runtime"}


class DockerizeCheckFailure(app_commands.CheckFailure):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def sanitize_name(raw: str, *, prefix: str = "", max_length: int = 48, fallback: str = "container") -> str:
    text = raw.strip().lower().replace(" ", "-")
    text = _NAME_RE.sub("-", text)
    text = re.sub(r"-+", "-", text).strip("-_")
    if not text:
        text = fallback
    if prefix and not text.startswith(prefix):
        text = f"{prefix}{text}"
    return text[:max_length].strip("-") or fallback


def sanitize_channel_name(raw: str) -> str:
    return sanitize_name(raw, max_length=32, fallback="channel")


async def get_settings(interaction: discord.Interaction):
    if interaction.guild is None:
        raise DockerizeCheckFailure("Dockerize commands only work inside a server.")
    db: Database = interaction.client.database  # type: ignore[attr-defined]
    return await db.get_guild_settings(interaction.guild.id)


async def is_staff_member(interaction: discord.Interaction) -> bool:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        return False
    if interaction.user.guild_permissions.administrator:
        return True
    db: Database = interaction.client.database  # type: ignore[attr-defined]
    settings = await db.get_guild_settings(interaction.guild.id)
    if not settings or not settings["staff_role_id"]:
        return False
    staff_role = interaction.guild.get_role(int(settings["staff_role_id"]))
    return staff_role is not None and staff_role in interaction.user.roles


async def ensure_bot_can_manage(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        raise DockerizeCheckFailure("This command can only run inside a server.")
    me = interaction.guild.me
    if me is None:
        raise DockerizeCheckFailure("I could not resolve my server member object.")
    perms = me.guild_permissions
    missing: list[str] = []
    if not perms.manage_channels:
        missing.append("Manage Channels")
    if not perms.view_channel:
        missing.append("View Channels")
    if not perms.send_messages:
        missing.append("Send Messages")
    if not perms.embed_links:
        missing.append("Embed Links")
    if missing:
        raise DockerizeCheckFailure("I am missing required permissions: " + ", ".join(missing))


async def _is_inside_own_container(interaction: discord.Interaction) -> bool:
    if interaction.guild is None or interaction.channel is None:
        return False
    db: Database = interaction.client.database  # type: ignore[attr-defined]
    container = await db.get_container(interaction.guild.id, interaction.user.id)
    if not container or not container["category_id"]:
        return False
    category_id = int(container["category_id"])
    channel = interaction.channel
    if isinstance(channel, discord.CategoryChannel):
        return channel.id == category_id
    return getattr(channel, "category_id", None) == category_id


def user_command_check(*, allow_inside_container: bool = True):
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise DockerizeCheckFailure("Dockerize commands only work inside a server.")
        if await is_staff_member(interaction):
            return True
        settings = await get_settings(interaction)
        if not settings:
            raise DockerizeCheckFailure("Dockerize daemon is not initialized. Ask staff to run `/setup` first.")
        allowed_channel_id = int(settings["command_channel_id"])
        if interaction.channel_id == allowed_channel_id:
            return True
        if allow_inside_container and await _is_inside_own_container(interaction):
            return True
        raise DockerizeCheckFailure(f"Use Dockerize commands in <#{allowed_channel_id}> or inside your own container.")

    return app_commands.check(predicate)


def staff_only_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise DockerizeCheckFailure("Admin commands only work inside a server.")
        if await is_staff_member(interaction):
            return True
        raise DockerizeCheckFailure("You need Administrator permission or the configured Dockerize staff role.")

    return app_commands.check(predicate)


async def fetch_member_safe(guild: discord.Guild, user_id: int) -> discord.Member | None:
    member = guild.get_member(user_id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def safe_dm(user: discord.abc.User, embed: discord.Embed) -> bool:
    try:
        await user.send(embed=embed)
        return True
    except (discord.Forbidden, discord.HTTPException):
        LOGGER.warning("Could not DM user %s", getattr(user, "id", "unknown"))
        return False


def bool_word(value: bool) -> str:
    return "yes" if value else "no"
