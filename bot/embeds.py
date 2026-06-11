from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord

from .config import Config

LOGGER = logging.getLogger(__name__)

GENERAL_COLOR = 0x2EA7FF
SUCCESS_COLOR = 0x3DDC84
FAILURE_COLOR = 0xED4245
WARNING_COLOR = 0xFEE75C
SUSPENDED_COLOR = 0x8B0000

FOOTER = "Dockerize Runtime • container-isolated Discord environment"


def _stamp() -> datetime:
    return discord.utils.utcnow()


def base_embed(
    *,
    title: str,
    description: str | None = None,
    color: int = GENERAL_COLOR,
    fields: list[tuple[str, str, bool]] | None = None,
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, timestamp=_stamp())
    embed.set_footer(text=FOOTER)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value or "—", inline=inline)
    return embed


def docker_embed(config: Config, title: str, description: str | None = None, *, fields: list[tuple[str, str, bool]] | None = None) -> discord.Embed:
    return base_embed(title=f"{config.emoji_docker} {title}", description=description, color=GENERAL_COLOR, fields=fields)


def success_embed(config: Config, title: str, description: str | None = None, *, fields: list[tuple[str, str, bool]] | None = None) -> discord.Embed:
    return base_embed(title=f"{config.emoji_success} {title}", description=description, color=SUCCESS_COLOR, fields=fields)


def failure_embed(config: Config, title: str, description: str | None = None, *, fields: list[tuple[str, str, bool]] | None = None) -> discord.Embed:
    return base_embed(title=f"{config.emoji_failure} {title}", description=description, color=FAILURE_COLOR, fields=fields)


def warning_embed(config: Config, title: str, description: str | None = None, *, fields: list[tuple[str, str, bool]] | None = None) -> discord.Embed:
    return base_embed(title=f"{config.emoji_warning} {title}", description=description, color=WARNING_COLOR, fields=fields)


def suspended_embed(config: Config, title: str, description: str | None = None, *, fields: list[tuple[str, str, bool]] | None = None) -> discord.Embed:
    return base_embed(title=f"{config.emoji_failure} {title}", description=description, color=SUSPENDED_COLOR, fields=fields)


def terminal_embed(config: Config, title: str, console_text: str, *, color: int = GENERAL_COLOR) -> discord.Embed:
    return base_embed(
        title=f"{config.emoji_docker} {title}",
        description=f"```console\n{console_text.strip()}\n```",
        color=color,
    )


def table_block(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "```txt\nNo records found.\n```"

    widths = [len(header) for header in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    header_line = "   ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))
    row_lines = ["   ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))) for row in rows]
    return "```txt\n" + header_line + "\n" + "\n".join(row_lines) + "\n```"


async def send_embed(
    interaction: discord.Interaction,
    embed: discord.Embed,
    *,
    ephemeral: bool = False,
    view: discord.ui.View | None = None,
) -> None:
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral, view=view)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral, view=view)
    except discord.HTTPException:
        LOGGER.exception("Failed to send interaction embed")


async def edit_or_send(
    interaction: discord.Interaction,
    embed: discord.Embed,
    *,
    view: discord.ui.View | None = None,
    ephemeral: bool = False,
) -> None:
    try:
        if interaction.response.is_done():
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except discord.NotFound:
                await interaction.followup.send(embed=embed, ephemeral=ephemeral, view=view)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral, view=view)
    except discord.HTTPException:
        LOGGER.exception("Failed to edit/send interaction embed")


def dm_note(success: bool) -> str:
    return "DM delivered." if success else "Could not DM the user. They may have DMs disabled."


def format_discord_time(value: str | None) -> str:
    if not value:
        return "unknown"
    try:
        dt = datetime.fromisoformat(value)
        return f"<t:{int(dt.timestamp())}:R>"
    except ValueError:
        return value


def container_id(row: Any) -> str:
    try:
        return f"dkz-{int(row['id']):04x}"
    except Exception:
        return "dkz-????"
