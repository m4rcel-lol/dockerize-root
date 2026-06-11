from __future__ import annotations

import asyncio
import logging
import sys

import discord
from discord import app_commands
from discord.ext import commands

from .checks import DockerizeCheckFailure
from .config import Config
from .database import Database
from .embeds import failure_embed, send_embed

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
EXTENSIONS = (
    "bot.cogs.setup",
    "bot.cogs.containers",
    "bot.cogs.channels",
    "bot.cogs.invites",
    "bot.cogs.admin",
)


class DockerizeBot(commands.Bot):
    config: Config
    database: Database

    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
        self.config = config
        self.database = Database(config.database_path)

    async def setup_hook(self) -> None:
        self.tree.on_error = self.on_app_command_error
        await self.database.initialize()
        logging.info("SQLite database initialized at %s", self.config.database_path)

        for extension in EXTENSIONS:
            await self.load_extension(extension)
            logging.info("Loaded extension %s", extension)

        synced = await self.tree.sync()
        logging.info("Synced %d slash command(s)", len(synced))

    async def on_ready(self) -> None:
        assert self.user is not None
        logging.info("Dockerize online as %s (%s)", self.user, self.user.id)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        root_error = getattr(error, "original", error)
        if isinstance(root_error, DockerizeCheckFailure):
            embed = failure_embed(self.config, "Command rejected", f"```console\nError: {root_error.message}\n```")
            await send_embed(interaction, embed, ephemeral=True)
            return
        if isinstance(root_error, app_commands.MissingPermissions):
            embed = failure_embed(self.config, "Permission denied", "You do not have permission to run this command.")
            await send_embed(interaction, embed, ephemeral=True)
            return
        if isinstance(root_error, app_commands.CommandOnCooldown):
            embed = failure_embed(self.config, "Runtime busy", f"Try again in `{root_error.retry_after:.1f}s`.")
            await send_embed(interaction, embed, ephemeral=True)
            return

        logging.exception("Unhandled app command error", exc_info=root_error)
        embed = failure_embed(
            self.config,
            "Runtime crashed safely",
            "```console\nError: an unexpected runtime error occurred.\n```\nThe bot did not crash, but the command could not finish.",
        )
        await send_embed(interaction, embed, ephemeral=True)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stdout)
    discord.utils.setup_logging(level=logging.INFO, root=False)
    config = Config.from_env()
    bot = DockerizeBot(config)
    async with bot:
        await bot.start(config.token)


def run() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logging.info("Dockerize shutdown requested")


if __name__ == "__main__":
    run()
