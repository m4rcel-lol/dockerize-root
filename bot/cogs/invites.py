from __future__ import annotations

from discord.ext import commands


class InvitesCog(commands.Cog):
    """Invite-related commands live in ContainerCog so they appear under /container."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InvitesCog(bot))
