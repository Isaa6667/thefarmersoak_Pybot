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


class SecondQuizModal(discord.ui.Modal, title="Training Quiz - Questions 6-10"):
    def __init__(self):
        super().__init__()

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
                placeholder=QUESTIONS[index][:100],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )

            self.answers.append(field)
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):

        answers = interaction.client.quiz_answers.get(
            interaction.user.id, []
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
                f"{interaction.user.mention}."
            ),
            colour=EMBED_COLOUR
        )

        embed.add_field(
            name="Trainee",
            value=f"{interaction.user} ({interaction.user.id})",
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

        view = QuizReviewView(interaction.user.id)

        await channel.send(embed=embed, view=view)

        interaction.client.quiz_answers.pop(
            interaction.user.id, None
        )

        await interaction.response.send_message(
            "Your quiz has been submitted successfully. "
            "Management will review your answers and send you your result.",
            ephemeral=True
        )


class PartTwoPromptView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=1800)

    @discord.ui.button(label="Open Part 2 (Q6-10)", style=discord.ButtonStyle.primary)
    async def open_part_two(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SecondQuizModal())


class FirstQuizModal(discord.ui.Modal, title="Training Quiz - Questions 1-5"):
    def __init__(self):
        super().__init__()

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
                placeholder=QUESTIONS[index][:100],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )

            self.answers.append(field)
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):

        interaction.client.quiz_answers[
            interaction.user.id
        ] = [field.value for field in self.answers]

        view = PartTwoPromptView()
        await interaction.response.send_message(
            "Part 1 saved successfully! Click the button below to open **Part 2 (Questions 6-10)**.",
            view=view,
            ephemeral=True
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
        label="Begin Training Quiz (Part 1)",
        style=discord.ButtonStyle.success
    )
    async def begin(self, interaction, button):
        await interaction.response.send_modal(FirstQuizModal())


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
                "Please answer all ten questions carefully across two parts. "
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

    @trainingquiz.command(
        name="reset",
        description="Reset active or stuck quiz memory for a trainee"
    )
    @app_commands.describe(user="The trainee whose quiz state should be cleared")
    @is_management()
    async def reset(self, interaction: discord.Interaction, user: discord.Member):
        if user.id in self.bot.quiz_answers:
            self.bot.quiz_answers.pop(user.id, None)
            await interaction.response.send_message(
                f"Cleared stored quiz state for {user.mention}. They can now start fresh.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"{user.mention} does not have an active quiz session in memory.",
                ephemeral=True
            )

    @trainingquiz.command(
        name="stats",
        description="View current staff training academy statistics"
    )
    @is_management()
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        review_channel = self.bot.get_channel(REVIEW_CHANNEL_ID)
        if review_channel is None:
            try:
                review_channel = await self.bot.fetch_channel(REVIEW_CHANNEL_ID)
            except discord.HTTPException:
                await interaction.followup.send("Could not access the review channel to fetch stats.", ephemeral=True)
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
            title="The Farmers Oak | Training Academy Stats",
            description="Overview of recent staff onboarding performance (Last 200 submissions):",
            colour=EMBED_COLOUR
        )
        embed.add_field(name="Pending Reviews", value=f"**{pending_count}**", inline=True)
        embed.add_field(name="Total Passed", value=f"**{passed_count}**", inline=True)
        embed.add_field(name="Total Failed", value=f"**{failed_count}**", inline=True)
        embed.set_footer(text="The Farmers Oak Training Academy")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @trainingquiz.command(
        name="manual",
        description="View the staff training study manual and reference guide"
    )
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
                "**10. Pub Landlords:** Refer to the server pins or channel topics for current landlord names."
            ),
            colour=EMBED_COLOUR
        )
        embed.set_footer(text="The Farmers Oak Training Academy Reference Guide")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(TrainingQuiz(bot))