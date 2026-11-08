import os
import discord
from discord import app_commands
from discord.ext import commands

EMBED_COLOUR = discord.Colour(0x355E3B)

def is_management():
    async def predicate(interaction: discord.Interaction):
        role_id = int(os.getenv("MANAGEMENT_ROLE_ID", "0"))
        if not role_id:
            raise app_commands.CheckFailure("Management role has not been configured.")
        if not any(role.id == role_id for role in interaction.user.roles):
            raise app_commands.CheckFailure("Only Management can use this command.")
        return True
    return app_commands.check(predicate)

class StartQuizView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Start Staff Training Quiz", 
        style=discord.ButtonStyle.success, 
        custom_id="start_quiz_button"
    )
    async def start_quiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_id = int(os.getenv("MANAGEMENT_ROLE_ID", "0"))
        if not role_id or not any(role.id == role_id for role in interaction.user.roles):
            await interaction.response.send_message(
                "Only Management can initiate or assign the staff training quiz.",
                ephemeral=True
            )
            return

        # Triggered if user is Management
        await interaction.response.send_message(
            "Use `/trainingquiz user <member>` to assign the quiz to a trainee!",
            ephemeral=True
        )

class QuizEmbedModal(discord.ui.Modal, title="Create Quiz Announcement"):
    title_input = discord.ui.TextInput(
        label="Announcement Title",
        default="The Farmers Oak | Staff Training Quiz",
        required=True,
        max_length=256
    )

    instructions_input = discord.ui.TextInput(
        label="Quiz Instructions",
        style=discord.TextStyle.paragraph,
        default=(
            "Welcome to staff onboarding!\n\n"
            "Please ensure you have thoroughly reviewed `/training manual` before proceeding.\n"
            "Management will initiate your quiz session when you are ready."
        ),
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.title_input.value,
            description=self.instructions_input.value,
            colour=EMBED_COLOUR
        )
        embed.set_footer(text="The Farmers Oak")

        view = StartQuizView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"Quiz embed successfully posted in {interaction.channel.mention}!",
            ephemeral=True
        )

class MakeQuizEmbedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="makequizembed",
        description="Post the official quiz start embed in the current channel (Management only)"
    )
    @is_management()
    async def make_quiz_embed(self, interaction: discord.Interaction):
        modal = QuizEmbedModal()
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(MakeQuizEmbedCog(bot))