from __future__ import annotations

import logging
from typing import Iterable

import discord

from .checks import fetch_member_safe
from .database import Database

LOGGER = logging.getLogger(__name__)


def _owner_overwrite() -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        connect=True,
        speak=True,
        manage_channels=True,
    )


def _invited_overwrite() -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        connect=True,
        speak=True,
    )


def _staff_overwrite() -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        connect=True,
        speak=True,
        manage_channels=True,
        manage_messages=True,
    )


def _bot_overwrite() -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        connect=True,
        speak=True,
        manage_channels=True,
        manage_permissions=True,
        manage_messages=True,
    )


def build_private_overwrites(
    guild: discord.Guild,
    owner: discord.Member,
    staff_role: discord.Role | None,
    bot_member: discord.Member,
    invited_members: Iterable[discord.Member] = (),
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        owner: _owner_overwrite(),
        bot_member: _bot_overwrite(),
    }
    if staff_role is not None:
        overwrites[staff_role] = _staff_overwrite()
    for member in invited_members:
        overwrites[member] = _invited_overwrite()
    return overwrites


def build_public_overwrites(
    guild: discord.Guild,
    owner: discord.Member,
    staff_role: discord.Role | None,
    bot_member: discord.Member,
    invited_members: Iterable[discord.Member] = (),
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    overwrites = build_private_overwrites(guild, owner, staff_role, bot_member, invited_members)
    overwrites[guild.default_role] = discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        connect=True,
        speak=True,
        manage_channels=False,
    )
    return overwrites


def build_suspended_overwrites(
    guild: discord.Guild,
    owner: discord.Member | None,
    staff_role: discord.Role | None,
    bot_member: discord.Member,
    invited_members: Iterable[discord.Member] = (),
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        bot_member: _bot_overwrite(),
    }
    if owner is not None:
        overwrites[owner] = discord.PermissionOverwrite(view_channel=False)
    if staff_role is not None:
        overwrites[staff_role] = _staff_overwrite()
    for member in invited_members:
        overwrites[member] = discord.PermissionOverwrite(view_channel=False)
    return overwrites


async def _apply_overwrites_to_category_and_children(
    category: discord.CategoryChannel,
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite],
    *,
    reason: str,
) -> None:
    await category.edit(overwrites=overwrites, reason=reason)
    for channel in list(category.channels):
        try:
            await channel.edit(overwrites=overwrites, reason=reason)
        except (discord.Forbidden, discord.HTTPException):
            LOGGER.warning("Could not update overwrites for channel %s", channel.id)


async def _resolve_context(
    guild: discord.Guild,
    db: Database,
    container_row,
    staff_role: discord.Role | None,
) -> tuple[discord.Member | None, list[discord.Member], discord.Member, discord.CategoryChannel | None]:
    owner = await fetch_member_safe(guild, int(container_row["owner_id"]))
    invited_rows = await db.list_invites(guild.id, int(container_row["owner_id"]))
    invited: list[discord.Member] = []
    for row in invited_rows:
        member = await fetch_member_safe(guild, int(row["invited_user_id"]))
        if member is not None:
            invited.append(member)
    bot_member = guild.me
    if bot_member is None:
        raise RuntimeError("Bot member is not available in guild cache")
    category = guild.get_channel(int(container_row["category_id"])) if container_row["category_id"] else None
    if not isinstance(category, discord.CategoryChannel):
        category = None
    return owner, invited, bot_member, category


async def apply_container_private(guild: discord.Guild, db: Database, container_row, staff_role: discord.Role | None) -> None:
    owner, invited, bot_member, category = await _resolve_context(guild, db, container_row, staff_role)
    if category is None or owner is None:
        return
    overwrites = build_private_overwrites(guild, owner, staff_role, bot_member, invited)
    await _apply_overwrites_to_category_and_children(category, overwrites, reason="Dockerize private permission layer")


async def apply_container_public(guild: discord.Guild, db: Database, container_row, staff_role: discord.Role | None) -> None:
    owner, invited, bot_member, category = await _resolve_context(guild, db, container_row, staff_role)
    if category is None or owner is None:
        return
    overwrites = build_public_overwrites(guild, owner, staff_role, bot_member, invited)
    await _apply_overwrites_to_category_and_children(category, overwrites, reason="Dockerize public permission layer")


async def apply_container_suspended(guild: discord.Guild, db: Database, container_row, staff_role: discord.Role | None) -> None:
    owner, invited, bot_member, category = await _resolve_context(guild, db, container_row, staff_role)
    if category is None:
        return
    overwrites = build_suspended_overwrites(guild, owner, staff_role, bot_member, invited)
    await _apply_overwrites_to_category_and_children(category, overwrites, reason="Dockerize suspended permission layer")


async def apply_container_down(guild: discord.Guild, db: Database, container_row, staff_role: discord.Role | None) -> None:
    owner, invited, bot_member, category = await _resolve_context(guild, db, container_row, staff_role)
    if category is None:
        return
    overwrites = build_suspended_overwrites(guild, owner, staff_role, bot_member, invited)
    await _apply_overwrites_to_category_and_children(category, overwrites, reason="Dockerize stopped permission layer")


async def restore_container_permissions(guild: discord.Guild, db: Database, container_row, staff_role: discord.Role | None) -> None:
    if container_row["visibility"] == "public":
        await apply_container_public(guild, db, container_row, staff_role)
    else:
        await apply_container_private(guild, db, container_row, staff_role)
