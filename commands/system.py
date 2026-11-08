import discord
from discord import app_commands
from discord.ext import commands


class System(commands.GroupCog, group_name="system", group_description="Staff system administration"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check whether the bot is responding")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"Pong! Gateway latency: {round(self.bot.latency * 1000)}ms",
            ephemeral=True
        )

    @app_commands.command(name="status", description="Show bot status")
    async def status(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Bot status", color=discord.Color.green())
        embed.add_field(name="Status", value="Online", inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(System(bot))
