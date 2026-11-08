import os
import discord
from discord import app_commands
from discord.ext import commands

REVIEW_CHANNEL_ID = 1568717370149830877
EMBED_COLOUR = discord.Colour(0x355E3B)

QUESTIONS = [
    "What must you do in the event of a fire?",
    "What should happen when a customer is unhappy?",
    "What order do you serve the food in?",
    "How many shifts must you attend a week?",
    "What should you do if a customer has a dietary requirement?",
    "Who should you report an issue to while on a shift?",
    "How long before the shift do you have to join?",
    "What must you use while talking to customers?",
    "What is the code for the POS system?",
    "Who are the Pub landlords?"
]


def is_management():
    async def predicate(interaction: discord.Interaction):
        role_id = int(os.getenv("MANAGEMENT_ROLE_ID", "0"))

        if not role_id:
            raise app_commands.CheckFailure(
                "Management role has not been configured."
            )

        if not any(role.id == role_id for role in interaction.user.roles):
            raise app_commands.CheckFailure(
                "Only Management can use this command."
            )

        return True

    return app_commands.check(predicate)


class QuizReviewView(discord.ui.View):

    def __init__(self, trainee_id: int):
        super().__init__(timeout=604800)
        self.trainee_id = trainee_id

    async def interaction_check(self, interaction):
        role_id = int(os.getenv("MANAGEMENT_ROLE_ID", "0"))

        if not any(role.id == role_id for role in interaction.user.roles):
            await interaction.response.send_message(
                "Only Management can mark training quizzes.",
                ephemeral=True
            )
            return False

        return True

    async def mark(self, interaction, result):
        await interaction.response.defer(ephemeral=True)

        trainee = interaction.guild.get_member(self.trainee_id)

        if trainee is None:
            try:
                trainee = await interaction.guild.fetch_member(
                    self.trainee_id
                )
            except discord.NotFound:
                trainee = None

        if trainee:
            try:
                embed = discord.Embed(
                    title="Training Quiz Result",
                    description=(
                        f"Your Farmers Oak training quiz has been "
                        f"**{result.upper()}**."
                    ),
                    colour=(
                        discord.Colour.green()
                        if result == "passed"
                        else discord.Colour.red()
                    )
                )

                embed.add_field(
                    name="Result",
                    value=result.title()
                )

                embed.set_footer(text="The Farmers Oak Training Academy")

                await trainee.send(embed=embed)

            except discord.Forbidden:
                await interaction.followup.send(
                    "The result was recorded, but the trainee has DMs disabled.",
                    ephemeral=True
                )
                return

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(view=self)

        await interaction.followup.send(
            f"Quiz marked as **{result.upper()}**.",
            ephemeral=True
        )

    @discord.ui.button(
        label="Pass",
        style=discord.ButtonStyle.success,
        custom_id="trainingquiz_pass"
    )
    async def pass_button(self, interaction, button):
        await self.mark(interaction, "passed")

    @discord.ui.button(
        label="Fail",
        style=discord.ButtonStyle.danger,
        custom_id="trainingquiz_fail"
    )
    async def fail_button(self, interaction, button):
        await self.mark(interaction, "failed")


class SecondQuizModal(discord.ui.Modal):
    def __init__(self, trainee):
        super().__init__(title="Training Quiz - Questions 6-10")
        self.trainee = trainee

        labels = [
            "Reporting issues",
            "Arrival time",
            "Customer communication",
            "POS code",
            "Pub landlords"
        ]

        self.answers = []

        for index, label in enumerate(labels, start=5):
            field = discord.ui.TextInput(
                label=label,
                placeholder=QUESTIONS[index],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )

            self.answers.append(field)
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):

        answers = interaction.client.quiz_answers.get(
            self.trainee.id, []
        )

        answers.extend([field.value for field in self.answers])

        channel = interaction.client.get_channel(REVIEW_CHANNEL_ID)

        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(
                    REVIEW_CHANNEL_ID
                )
            except discord.HTTPException:
                await interaction.response.send_message(
                    "The review channel could not be found.",
                    ephemeral=True
                )
                return

        embed = discord.Embed(
            title="New Staff Training Quiz",
            description=(
                f"A training quiz has been completed by "
                f"{self.trainee.mention}."
            ),
            colour=EMBED_COLOUR
        )

        embed.add_field(
            name="Trainee",
            value=f"{self.trainee} ({self.trainee.id})",
            inline=False
        )

        for index, (question, answer) in enumerate(
            zip(QUESTIONS, answers), start=1
        ):
            embed.add_field(
                name=f"Question {index}: {question}",
                value=answer[:1024],
                inline=False
            )

        embed.set_footer(
            text="The Farmers Oak | Awaiting Management Review"
        )

        view = QuizReviewView(self.trainee.id)

        await channel.send(embed=embed, view=view)

        interaction.client.quiz_answers.pop(
            self.trainee.id, None
        )

        await interaction.response.send_message(
            "Your quiz has been submitted successfully. "
            "Management will review your answers and send you your result.",
            ephemeral=True
        )


class FirstQuizModal(discord.ui.Modal):
    def __init__(self, trainee):
        super().__init__(title="Training Quiz - Questions 1-5")
        self.trainee = trainee

        labels = [
            "Fire procedure",
            "Unhappy customer",
            "Food service order",
            "Weekly shifts",
            "Dietary requirements"
        ]

        self.answers = []

        for index, label in enumerate(labels):
            field = discord.ui.TextInput(
                label=label,
                placeholder=QUESTIONS[index],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )

            self.answers.append(field)
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):

        interaction.client.quiz_answers[
            self.trainee.id
        ] = [field.value for field in self.answers]

        await interaction.response.send_modal(
            SecondQuizModal(self.trainee)
        )


class BeginQuizView(discord.ui.View):
    def __init__(self, trainee):
        super().__init__(timeout=3600)
        self.trainee = trainee

    async def interaction_check(self, interaction):
        if interaction.user.id != self.trainee.id:
            await interaction.response.send_message(
                "This quiz belongs to another trainee.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Begin Training Quiz",
        style=discord.ButtonStyle.success
    )
    async def begin(self, interaction, button):
        await interaction.response.send_modal(
            FirstQuizModal(self.trainee)
        )

class TrainingQuiz(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        if not hasattr(bot, "quiz_answers"):
            bot.quiz_answers = {}

    trainingquiz = app_commands.Group(
        name="trainingquiz",
        description="Staff training quiz management"
    )

    @trainingquiz.command(
        name="user",
        description="Send a staff training quiz to a member"
    )
    @app_commands.describe(
        user="The trainee who should receive the quiz"
    )
    @is_management()
    async def user(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):

        if user.bot:
            await interaction.response.send_message(
                "You cannot send a training quiz to a bot.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="The Farmers Oak | Staff Training Quiz",
            description=(
                "You have been assigned your staff training quiz.\n\n"
                "Please answer all ten questions carefully. "
                "Your answers will be sent to Management for manual marking."
            ),
            colour=EMBED_COLOUR
        )

        for index, question in enumerate(QUESTIONS, start=1):
            embed.add_field(
                name=f"Question {index}",
                value=question,
                inline=False
            )

        embed.set_footer(
            text="The Farmers Oak Training Academy"
        )

        try:
            await user.send(
                embed=embed,
                view=BeginQuizView(user)
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                f"I couldn't DM {user.mention}. "
                "They need to allow messages from server members.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Training quiz successfully sent to {user.mention}.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(TrainingQuiz(bot))
