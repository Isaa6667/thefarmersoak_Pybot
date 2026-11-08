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

class TrainingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    training_group = app_commands.Group(name="training", description="Staff training system and study commands")

    @training_group.command(name="manual", description="View the staff training manual and reference guide")
    async def manual(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="The Farmers Oak | Staff Training Manual",
            description=(
                "Here are the reference guidelines and answers to help you pass your training quiz.\n\n"
                "**1. Fire Procedure:** Evacuate immediately via the nearest fire exit and gather at the assembly point.\n"
                "**2. Unhappy Customers:** Remain calm, apologize sincerely, and fetch a manager if necessary.\n"
                "**3. Food Service Order:** Drinks first, starters second, mains third, and clear plates between courses.\n"
                "**4. Weekly Shifts:** Staff must attend a minimum of 2 shifts per week.\n"
                "**5. Dietary Requirements:** Always check with the kitchen and note allergies clearly on the POS.\n"
                "**6. Reporting Issues:** Report all maintenance or staff issues directly to Management.\n"
                "**7. Arrival Time:** Join voice/shift channels at least 10 minutes before start time.\n"
                "**8. Customer Communication:** Always use polite, welcoming language and professional tone.\n"
                "**9. POS System Code:** Check internal staff pins or ask a manager on duty.\n"
                "**10. Pub Landlords:** Refer to the server pins or channel topics for current landlord names.\n"
                "**11. Training Sessions:** Staff must successfully attend both theory training and practical sessions."
            ),
            colour=EMBED_COLOUR
        )
        embed.set_footer(text="The Farmers Oak")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @training_group.command(name="info", description="View requirements for completing staff onboarding")
    async def info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="The Farmers Oak | Staff Onboarding",
            description=(
                "Welcome to staff training! Here is what you need to complete:\n\n"
                "• Receive your quiz via a management command (`/trainingquiz user`)\n"
                "• Complete both Part 1 and Part 2 via the secure modals\n"
                "• Attend both theory training and practical sessions\n"
                "• Wait for management review and approval\n\n"
                "Use `/training manual` to review the required guidelines before starting."
            ),
            colour=EMBED_COLOUR
        )
        embed.set_footer(text="The Farmers Oak")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TrainingSystem(bot))