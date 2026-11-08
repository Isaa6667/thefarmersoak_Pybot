import os
import discord
from discord import app_commands
from discord.ext import commands

EMBED_COLOUR = discord.Colour(0x355E3B)
REVIEW_CHANNEL_ID = 1568717370149830877

def is_management():
    async def predicate(interaction: discord.Interaction):
        role_id = int(os.getenv("MANAGEMENT_ROLE_ID", "0"))
        if not role_id:
            raise app_commands.CheckFailure("Management role has not been configured.")
        if not any(role.id == role_id for role in interaction.user.roles):
            raise app_commands.CheckFailure("Only Management can use this command.")
        return True
    return app_commands.check(predicate)

class TrainingStatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    stats_group = app_commands.Group(name="training-stats", description="Training statistics and reports")

    @stats_group.command(name="overview", description="View pass, fail, and pending onboarding stats")
    @is_management()
    async def overview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        review_channel = self.bot.get_channel(REVIEW_CHANNEL_ID)
        if review_channel is None:
            try:
                review_channel = await self.bot.fetch_channel(REVIEW_CHANNEL_ID)
            except discord.HTTPException:
                await interaction.followup.send("Could not access the review channel.", ephemeral=True)
                return

        passed_count = 0
        failed_count = 0
        pending_count = 0

        async for message in review_channel.history(limit=200):
            if message.author == self.bot.user and message.embeds:
                embed = message.embeds[0]
                if embed.title == "New Staff Training Quiz":
                    if message.components and any(not child.disabled for row in message.components for child in row.children):
                        pending_count += 1
                elif embed.title == "Training Quiz Result":
                    if "PASSED" in embed.description.upper():
                        passed_count += 1
                    elif "FAILED" in embed.description.upper():
                        failed_count += 1

        embed = discord.Embed(
            title="The Farmers Oak | Training Overview",
            description="Performance breakdown of recent staff onboarding records:",
            colour=EMBED_COLOUR
        )
        embed.add_field(name="Pending Reviews", value=f"**{pending_count}**", inline=True)
        embed.add_field(name="Total Passed", value=f"**{passed_count}**", inline=True)
        embed.add_field(name="Total Failed", value=f"**{failed_count}**", inline=True)
        embed.set_footer(text="The Farmers Oak")

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TrainingStatsCog(bot))