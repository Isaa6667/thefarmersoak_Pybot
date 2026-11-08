import discord
from discord import app_commands
from discord.ext import commands

EMBED_COLOUR = discord.Colour(0x355E3B)

class CmdsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="cmds",
        description="Dynamically fetch and list all registered slash commands"
    )
    async def cmds(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        registered_cmds = self.bot.tree.get_commands()

        if not registered_cmds:
            await interaction.followup.send("No active commands found.", ephemeral=True)
            return

        embed = discord.Embed(
            title="The Farmers Oak | Command Directory",
            description="Here are all registered slash commands currently loaded:",
            colour=EMBED_COLOUR
        )

        for cmd in registered_cmds:
            if isinstance(cmd, app_commands.Group):
                sub_lines = [
                    f"`/{cmd.name} {sub_cmd.name}` - {sub_cmd.description or 'No description'}"
                    for sub_cmd in cmd.commands
                ]
                embed.add_field(
                    name=f"/{cmd.name}",
                    value="\n".join(sub_lines) if sub_lines else "No subcommands",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"/{cmd.name}",
                    value=f"`/{cmd.name}` - {cmd.description or 'No description'}",
                    inline=False
                )

        embed.set_footer(text="The Farmers Oak")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CmdsCog(bot))
