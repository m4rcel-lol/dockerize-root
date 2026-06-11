from __future__ import annotations

import asyncio
import logging

import discord

from .embeds import edit_or_send, terminal_embed

LOGGER = logging.getLogger(__name__)

CREATE_FRAMES = [
    "$ docker compose up -d\n[+] Building Dockerize container...",
    "$ docker compose up -d\n[+] Creating private namespace...\n[+] Mounting channels...",
    "$ docker compose up -d\n[+] Creating private namespace...\n[+] Mounting channels...\n[+] Applying permission layers...",
    "$ docker compose up -d\n[+] Creating private namespace...\n[+] Mounting channels...\n[+] Applying permission layers...\n[+] Container started successfully.",
]

UP_FRAMES = [
    "$ docker start user-container\n[+] Resolving namespace...",
    "$ docker start user-container\n[+] Resolving namespace...\n[+] Recreating missing volumes...",
    "$ docker start user-container\n[+] Resolving namespace...\n[+] Recreating missing volumes...\n[+] Restoring permission layer...",
    "$ docker start user-container\n[+] Resolving namespace...\n[+] Recreating missing volumes...\n[+] Restoring permission layer...\n[+] Container is online.",
]

DOWN_FRAMES = [
    "$ docker stop user-container\n[+] Stopping runtime...",
    "$ docker stop user-container\n[+] Stopping runtime...\n[+] Locking user namespace...",
    "$ docker stop user-container\n[+] Stopping runtime...\n[+] Locking user namespace...\n[+] Staff inspection layer preserved...",
    "$ docker stop user-container\n[+] Stopping runtime...\n[+] Locking user namespace...\n[+] Staff inspection layer preserved...\n[+] Container stopped.",
]

DELETE_FRAMES = [
    "$ docker compose down --volumes\n[+] Stopping container...",
    "$ docker compose down --volumes\n[+] Stopping container...\n[+] Unmounting channels...",
    "$ docker compose down --volumes\n[+] Stopping container...\n[+] Unmounting channels...\n[+] Removing category...",
    "$ docker compose down --volumes\n[+] Stopping container...\n[+] Unmounting channels...\n[+] Removing category...\n[+] Cleaning database record...",
]

SUSPEND_FRAMES = [
    "$ docker container pause user-container\n[!] Freezing permissions...",
    "$ docker container pause user-container\n[!] Freezing permissions...\n[!] Locking owner access...",
    "$ docker container pause user-container\n[!] Freezing permissions...\n[!] Locking owner access...\n[!] Staff inspection mode enabled...",
]


async def play_terminal_animation(
    interaction: discord.Interaction,
    title: str,
    frames: list[str],
    final_embed: discord.Embed,
    *,
    delay: float = 0.75,
    ephemeral: bool = False,
) -> None:
    config = interaction.client.config  # type: ignore[attr-defined]
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True, ephemeral=ephemeral)

        for frame in frames[:6]:
            await interaction.edit_original_response(embed=terminal_embed(config, title, frame), view=None)
            await asyncio.sleep(delay)

        await interaction.edit_original_response(embed=final_embed, view=None)
    except (discord.HTTPException, discord.NotFound, RuntimeError):
        LOGGER.exception("Terminal animation failed; falling back to final embed")
        await edit_or_send(interaction, final_embed, ephemeral=ephemeral)
