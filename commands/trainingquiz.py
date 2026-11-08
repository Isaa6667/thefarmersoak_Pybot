
import os
import json
import re
import discord
from pathlib import Path
from discord import app_commands
from discord.ext import commands

REVIEW_CHANNEL_ID = 1568717370149830877
EMBED_COLOUR = discord.Colour(0x355E3B)
DATA_FILE = Path("quiz_data.json")

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

LABELS = [
    "Fire procedure",
    "Unhappy customer",
    "Food service order",
    "Weekly shifts",
    "Dietary requirements",
    "Reporting issues",
    "Arrival time",
    "Customer communication",
    "POS code",
    "Pub landlords"
]


def load_data():
    if not DATA_FILE.exists():
        return {}

    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}


def save_data(data):
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)


def is_management():
    async def predicate(interaction: discord.Interaction):
        role_id = int(os.getenv("MANAGEMENT_ROLE_ID", "0"))

        if not role_id:
            raise app_commands.CheckFailure(
                "MANAGEMENT_ROLE_ID has not been configured."
            )

        if not any(role.id == role_id for role in interaction.user.roles):
            raise app_commands.CheckFailure(
                "Only Management can use this command."
            )

        return True

    return app_commands.check(predicate)


def make_embed(title, description):
    return discord.Embed(
        title=title,
        description=description,
        colour=EMBED_COLOUR
    )


class QuizReviewView(discord.ui.View):
    def __init__(self, trainee_id):
        super().__init__(timeout=None)
        self.trainee_id = trainee_id

    async def interaction_check(self, interaction):
        role_id = int(os.getenv("MANAGEMENT_ROLE_ID", "0"))

        if not role_id or not any(
            role.id == role_id for role in interaction.user.roles
        ):
            await interaction.response.send_message(
                "Only Management can mark quizzes.",
                ephemeral=True
            )
            return False

        return True

    async def mark(self, interaction, result):
        await interaction.response.defer(ephemeral=True)

        data = load_data()
        review_key = str(interaction.message.id)

        reviews = data.setdefault("reviews", {})

        if review_key in reviews:
            await interaction.followup.send(
                "This quiz has already been marked.",
                ephemeral=True
            )
            return

        reviews[review_key] = result
        save_data(data)

        try:
            trainee = await interaction.client.fetch_user(
                self.trainee_id
            )

            embed = make_embed(
                "Staff Training Quiz Result",
                f"Your Farmers Oak training quiz has been "
                f"**{result.upper()}**."
            )

            embed.add_field(
                name="Result",
                value=result.title()
            )

            embed.set_footer(
                text="The Farmers Oak | Staff Training"
            )

            await trainee.send(embed=embed)

        except (discord.Forbidden, discord.NotFound):
            pass

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


class QuizModal(discord.ui.Modal):
    def __init__(self, trainee_id, part):
        self.trainee_id = trainee_id
        self.part = part

        super().__init__(
            title=(
                "Staff Quiz - Questions 1-5"
                if part == 1
                else "Staff Quiz - Questions 6-10"
            )
        )

        self.fields = []

        start = 0 if part == 1 else 5

        for i in range(start, start + 5):
            field = discord.ui.TextInput(
                label=LABELS[i],
                placeholder=QUESTIONS[i][:100],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )

            self.fields.append(field)
            self.add_item(field)

    async def on_submit(self, interaction):
        if interaction.user.id != self.trainee_id:
            await interaction.response.send_message(
                "This quiz belongs to another trainee.",
                ephemeral=True
            )
            return

        data = load_data()
        user_id = str(self.trainee_id)
        record = data.get(user_id, {})

        if self.part == 1:
            record = {
                "part1": [field.value for field in self.fields]
            }

            data[user_id] = record
            save_data(data)

            await interaction.response.send_message(
                "Part 1 saved successfully.",
                view=PartTwoView(self.trainee_id),
                ephemeral=True
            )
            return

        if len(record.get("part1", [])) != 5:
            await interaction.response.send_message(
                "Your first five answers could not be found. "
                "Please restart the quiz.",
                ephemeral=True
            )
            return

        if record.get("submitted"):
            await interaction.response.send_message(
                "You have already submitted this quiz.",
                ephemeral=True
            )
            return

        answers = record["part1"] + [
            field.value for field in self.fields
        ]

        channel = interaction.client.get_channel(
            REVIEW_CHANNEL_ID
        )

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

        embeds = []

        for start in range(0, 10, 5):
            embed = make_embed(
                "New Staff Training Quiz",
                f"Completed by {interaction.user.mention}"
            )

            embed.add_field(
                name="Trainee",
                value=f"{interaction.user} ({interaction.user.id})",
                inline=False
            )

            for i in range(start, start + 5):
                embed.add_field(
                    name=f"Question {i + 1}: {QUESTIONS[i]}",
                    value=answers[i][:1024],
                    inline=False
                )

            embed.set_footer(
                text=f"The Farmers Oak | Questions {start + 1}-{start + 5}"
            )

            embeds.append(embed)

        try:
            message = await channel.send(
                embeds=embeds,
                view=QuizReviewView(self.trainee_id)
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "There was an error submitting your quiz. "
                "Please contact Management.",
                ephemeral=True
            )
            return

        record["submitted"] = True
        record["review_message"] = message.id
        data[user_id] = record
        save_data(data)

        await interaction.response.send_message(
            "Your quiz has been submitted successfully. "
            "Management will review your answers.",
            ephemeral=True
        )


class PartTwoView(discord.ui.View):
    def __init__(self, trainee_id):
        super().__init__(timeout=1800)
        self.trainee_id = trainee_id

    @discord.ui.button(
        label="Open Part 2 (Q6-10)",
        style=discord.ButtonStyle.primary
    )
    async def open_part_two(self, interaction, button):
        if interaction.user.id != self.trainee_id:
            await interaction.response.send_message(
                "This quiz belongs to another trainee.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            QuizModal(self.trainee_id, 2)
        )


class BeginQuizView(discord.ui.View):
    def __init__(self, trainee_id):
        super().__init__(timeout=None)
        self.trainee_id = trainee_id

    @discord.ui.button(
        label="Begin Staff Quiz",
        style=discord.ButtonStyle.success
    )
    async def begin(self, interaction, button):
        if interaction.user.id != self.trainee_id:
            await interaction.response.send_message(
                "This quiz belongs to another trainee.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            QuizModal(self.trainee_id, 1)
        )


class PublicQuizPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Start Staff Quiz",
        style=discord.ButtonStyle.success,
        custom_id="farmersoak_public_training_quiz"
    )
    async def start_quiz(self, interaction, button):
        if interaction.user.bot:
            await interaction.response.send_message(
                "Bots cannot complete quizzes.",
                ephemeral=True
            )
            return

        try:
            embed = make_embed(
                "The Farmers Oak | Staff Training Quiz",
                "You have been assigned the staff training quiz.\n\n"
                "Complete all ten questions across two parts. "
                "Your answers will be sent to Management for review."
            )

            await interaction.user.send(
                embed=embed,
                view=BeginQuizView(interaction.user.id)
            )

            await interaction.response.send_message(
                "Your quiz has been sent to your DMs.",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I couldn't DM you. Please enable direct messages "
                "from server members and try again.",
                ephemeral=True
            )


class TrainingQuiz(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="quizembed",
        description="Post the public staff training quiz embed"
    )
    @is_management()
    async def quizembed(self, interaction: discord.Interaction):

        embed = make_embed(
            "The Farmers Oak | Staff Training",
            "Welcome to the Farmers Oak staff training quiz.\n\n"
            "All staff members are required to complete this quiz "
            "to demonstrate their understanding of our procedures "
            "and customer service standards.\n\n"
            "**How to begin**\n"
            "1. Click the button below.\n"
            "2. Complete all ten questions.\n"
            "3. Submit your answers for Management review.\n\n"
            "Your results will be sent directly to your DMs."
        )

        embed.set_footer(
            text="The Farmers Oak | Staff Training"
        )

        await interaction.response.defer(ephemeral=True)

        await interaction.channel.send(
            embed=embed,
            view=PublicQuizPanelView()
        )

        await interaction.followup.send(
            "Training quiz embed posted successfully.",
            ephemeral=True
        )

    @app_commands.command(
        name="quiz",
        description="Send training quizzes to selected staff members"
    )
    @app_commands.describe(
        users="Enter Discord mentions separated by spaces or commas"
    )
    @is_management()
    async def quiz(
        self,
        interaction: discord.Interaction,
        users: str
    ):

        user_ids = list(dict.fromkeys(
            re.findall(r"<@!?(\d+)>", users)
        ))

        if not user_ids:
            await interaction.response.send_message(
                "Please mention at least one valid Discord user.",
                ephemeral=True
            )
            return

        if len(user_ids) > 10:
            await interaction.response.send_message(
                "You can send quizzes to a maximum of 10 users at once.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        sent = []
        failed = []

        for user_id in user_ids:
            try:
                user = await self.bot.fetch_user(int(user_id))

                if user.bot:
                    failed.append(f"{user.mention} (Bot account)")
                    continue

                data = load_data()
                existing = data.get(str(user.id), {})

                if existing.get("submitted"):
                    failed.append(f"{user.mention} (Already submitted)")
                    continue

                await user.send(
                    embed=make_embed(
                        "The Farmers Oak | Staff Training Quiz",
                        "You have been assigned the staff training quiz.\n\n"
                        "Please complete all ten questions across two parts.\n\n"
                        "Your answers will be sent to Management for review."
                    ),
                    view=BeginQuizView(user.id)
                )

                sent.append(user.mention)

            except (discord.Forbidden, discord.NotFound):
                failed.append(f"<@{user_id}> (Could not DM)")

        result = make_embed(
            "Staff Training Quiz Distribution",
            "The quiz distribution has finished."
        )

        result.add_field(
            name=f"Successfully sent ({len(sent)})",
            value="\n".join(sent) if sent else "None",
            inline=False
        )

        result.add_field(
            name=f"Failed ({len(failed)})",
            value="\n".join(failed) if failed else "None",
            inline=False
        )

        await interaction.followup.send(
            embed=result,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(TrainingQuiz(bot))

    bot.add_view(PublicQuizPanelView())
