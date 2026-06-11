from __future__ import annotations

import discord


class ContainerListView(discord.ui.View):
    def __init__(self, *, author_id: int, pages: list[discord.Embed], timeout: float = 120.0) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.pages = pages
        self.index = 0
        self._refresh_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This paginator is not yours.", ephemeral=True)
            return False
        return True

    def _refresh_buttons(self) -> None:
        self.previous.disabled = self.index <= 0
        self.next.disabled = self.index >= len(self.pages) - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.index = max(0, self.index - 1)
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.index = min(len(self.pages) - 1, self.index + 1)
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)
