
import os
import json
import re
import uuid

from pathlib import Path
from datetime import datetime, timezone

import discord
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


def current_time():
    return datetime.now(timezone.utc).isoformat()


def default_data():
    return {
        "attempts": {},
        "begin_messages": {},
        "legacy": {}
    }


def load_data():
    if not DATA_FILE.exists():
        return default_data()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return default_data()

        # Preserve data from the previous version.
        if "attempts" not in data:
            return {
                "attempts": {},
                "begin_messages": {},
                "legacy": data
            }

        data.setdefault("attempts", {})
        data.setdefault("begin_messages", {})
        data.setdefault("legacy", {})

        return data

    except (json.JSONDecodeError, OSError):
        return default_data()


def save_data(data):
    temporary_file = DATA_FILE.with_suffix(".tmp")

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

    temporary_file.replace(DATA_FILE)


def make_embed(title, description):
    return discord.Embed(
        title=title,
        description=description,
        colour=EMBED_COLOUR
    )


def is_management():
    async def predicate(interaction: discord.Interaction):
        role_id = int(os.getenv("MANAGEMENT_ROLE_ID", "0"))

        if not role_id:
            raise app_commands.CheckFailure(
                "MANAGEMENT_ROLE_ID has not been configured."
            )

        user_roles = getattr(interaction.user, "roles", [])

        if not any(role.id == role_id for role in user_roles):
            raise app_commands.CheckFailure(
                "Only Management can use this command."
            )

        return True

    return app_commands.check(predicate)


def create_attempt(user: discord.User):
    data = load_data()

    attempt_id = uuid.uuid4().hex

    data["attempts"][attempt_id] = {
        "attempt_id": attempt_id,
        "user_id": user.id,
        "username": str(user),
        "created_at": current_time(),
        "part1": [],
        "answers": [],
        "submitted": False,
        "result": None,
        "reviewed_by": None,
        "reviewed_by_name": None,
        "reviewed_at": None,
        "review_message": None
    }

    save_data(data)

    return attempt_id


def save_begin_message(message_id, user_id):
    data = load_data()

    data["begin_messages"][str(message_id)] = user_id

    save_data(data)


class QuizReviewView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction):
        role_id = int(os.getenv("MANAGEMENT_ROLE_ID", "0"))

        user_roles = getattr(interaction.user, "roles", [])

        if not role_id or not any(
            role.id == role_id for role in user_roles
        ):
            await interaction.response.send_message(
                "Only Management can mark quizzes.",
                ephemeral=True
            )
            return False

        return True

    async def mark(self, interaction, result):
        data = load_data()

        attempt = None

        for record in data["attempts"].values():
            if record.get("review_message") == interaction.message.id:
                attempt = record
                break

        if attempt is None:
            await interaction.response.send_message(
                "The quiz record could not be found.",
                ephemeral=True
            )
            return

        if attempt.get("result") is not None:
            await interaction.response.send_message(
                "This quiz has already been marked.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        attempt["result"] = result
        attempt["reviewed_by"] = interaction.user.id
        attempt["reviewed_by_name"] = str(interaction.user)
        attempt["reviewed_at"] = current_time()

        save_data(data)

        trainee_id = attempt["user_id"]

        try:
            trainee = await interaction.client.fetch_user(trainee_id)

            result_text = "PASSED" if result == "passed" else "FAILED"

            embed = make_embed(
                "Staff Training Quiz Result",
                f"Your Farmers Oak training quiz has been **{result_text}**."
            )

            embed.add_field(
                name="Result",
                value=result_text,
                inline=True
            )

            embed.add_field(
                name="Reviewed by",
                value=interaction.user.mention,
                inline=True
            )

            embed.add_field(
                name="Quiz attempt",
                value=attempt["attempt_id"][:12],
                inline=False
            )

            embed.set_footer(
                text="The Farmers Oak | Staff Training"
            )

            await trainee.send(embed=embed)

        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
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
        custom_id="farmersoak_quiz_pass"
    )
    async def pass_button(self, interaction, button):
        await self.mark(interaction, "passed")

    @discord.ui.button(
        label="Fail",
        style=discord.ButtonStyle.danger,
        custom_id="farmersoak_quiz_fail"
    )
    async def fail_button(self, interaction, button):
        await self.mark(interaction, "failed")


class QuizModal(discord.ui.Modal):

    def __init__(self, trainee_id, attempt_id, part):
        self.trainee_id = trainee_id
        self.attempt_id = attempt_id
        self.part = part

        super().__init__(
            title=(
                "Staff Quiz - Questions 1-5"
                if part == 1
                else "Staff Quiz - Questions 6-10"
            )
        )

        self.answer_fields = []

        start = 0 if part == 1 else 5

        for i in range(start, start + 5):
            field = discord.ui.TextInput(
                label=LABELS[i],
                placeholder=QUESTIONS[i][:100],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )

            self.answer_fields.append(field)
            self.add_item(field)

    async def on_submit(self, interaction):
        if interaction.user.id != self.trainee_id:
            await interaction.response.send_message(
                "This quiz belongs to another trainee.",
                ephemeral=True
            )
            return

        data = load_data()
        attempt = data["attempts"].get(self.attempt_id)

        if attempt is None:
            await interaction.response.send_message(
                "This quiz attempt could not be found. Please start again.",
                ephemeral=True
            )
            return

        if attempt.get("submitted"):
            await interaction.response.send_message(
                "This quiz has already been submitted.",
                ephemeral=True
            )
            return

        answers = [field.value for field in self.answer_fields]

        if self.part == 1:
            attempt["part1"] = answers
            save_data(data)

            await interaction.response.send_message(
                "Your first five answers have been saved.",
                view=PartTwoView(self.trainee_id, self.attempt_id),
                ephemeral=True
            )
            return

        if len(attempt.get("part1", [])) != 5:
            await interaction.response.send_message(
                "Your first five answers could not be found. "
                "Please start the quiz again.",
                ephemeral=True
            )
            return

        all_answers = attempt["part1"] + answers

        channel = interaction.client.get_channel(REVIEW_CHANNEL_ID)

        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(
                    REVIEW_CHANNEL_ID
                )
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                await interaction.response.send_message(
                    "The review channel could not be found. "
                    "Please contact Management.",
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

            embed.add_field(
                name="Attempt ID",
                value=self.attempt_id[:12],
                inline=False
            )

            for i in range(start, start + 5):
                embed.add_field(
                    name=f"Question {i + 1}: {QUESTIONS[i]}",
                    value=all_answers[i][:1024],
                    inline=False
                )

            embed.set_footer(
                text=f"The Farmers Oak | Questions {start + 1}-{start + 5}"
            )

            embeds.append(embed)

        try:
            message = await channel.send(
                embeds=embeds,
                view=QuizReviewView()
            )

        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message(
                "There was an error submitting your quiz. "
                "Please contact Management.",
                ephemeral=True
            )
            return

        attempt["answers"] = all_answers
        attempt["submitted"] = True
        attempt["submitted_at"] = current_time()
        attempt["review_message"] = message.id

        save_data(data)

        await interaction.response.send_message(
            "Your quiz has been submitted successfully. "
            "Management will review your answers.",
            ephemeral=True
        )


class PartTwoView(discord.ui.View):

    def __init__(self, trainee_id, attempt_id):
        super().__init__(timeout=1800)

        self.trainee_id = trainee_id
        self.attempt_id = attempt_id

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
            QuizModal(
                self.trainee_id,
                self.attempt_id,
                2
            )
        )


class BeginQuizView(discord.ui.View):

    def __init__(self, trainee_id):
        super().__init__(timeout=None)

        self.trainee_id = trainee_id

        button = discord.ui.Button(
            label="Begin Staff Quiz",
            style=discord.ButtonStyle.success,
            custom_id=f"farmersoak_begin:{trainee_id}"
        )

        button.callback = self.begin
        self.add_item(button)

    async def begin(self, interaction):
        if interaction.user.id != self.trainee_id:
            await interaction.response.send_message(
                "This quiz belongs to another trainee.",
                ephemeral=True
            )
            return

        attempt_id = create_attempt(interaction.user)

        await interaction.response.send_modal(
            QuizModal(
                self.trainee_id,
                attempt_id,
                1
            )
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

        embed = make_embed(
            "The Farmers Oak | Staff Training Quiz",
            "You have been assigned the staff training quiz.\n\n"
            "Complete all ten questions across two parts. "
            "Your answers will be sent to Management for review."
        )

        try:
            message = await interaction.user.send(
                embed=embed,
                view=BeginQuizView(interaction.user.id)
            )

            save_begin_message(
                message.id,
                interaction.user.id
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
                    failed.append(f"<@{user_id}> (Bot account)")
                    continue

                message = await user.send(
                    embed=make_embed(
                        "The Farmers Oak | Staff Training Quiz",
                        "You have been assigned the staff training quiz.\n\n"
                        "Please complete all ten questions across two parts.\n\n"
                        "Your answers will be sent to Management for review."
                    ),
                    view=BeginQuizView(user.id)
                )

                save_begin_message(message.id, user.id)

                sent.append(user.mention)

            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
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

    @app_commands.command(
        name="quizresults",
        description="View a staff member's training quiz results"
    )
    @app_commands.describe(
        user="The staff member whose results you want to view"
    )
    @is_management()
    async def quizresults(
        self,
        interaction: discord.Interaction,
        user: discord.User
    ):

        data = load_data()

        attempts = [
            record
            for record in data["attempts"].values()
            if record.get("user_id") == user.id
        ]

        attempts.sort(
            key=lambda record: record.get("created_at", ""),
            reverse=True
        )

        if not attempts:
            await interaction.response.send_message(
                f"No quiz attempts were found for {user.mention}.",
                ephemeral=True
            )
            return

        passed = sum(
            1 for record in attempts
            if record.get("result") == "passed"
        )

        failed = sum(
            1 for record in attempts
            if record.get("result") == "failed"
        )

        pending = sum(
            1 for record in attempts
            if record.get("submitted") and record.get("result") is None
        )

        embed = make_embed(
            "Staff Training Quiz Results",
            f"**Staff member:** {user.mention}\n"
            f"**Total attempts:** {len(attempts)}\n\n"
            f"**Passed:** {passed}\n"
            f"**Failed:** {failed}\n"
            f"**Awaiting review:** {pending}"
        )

        for index, record in enumerate(attempts[:20], start=1):

            result = record.get("result")

            if result == "passed":
                status = "PASSED"
            elif result == "failed":
                status = "FAILED"
            elif record.get("submitted"):
                status = "AWAITING MANAGEMENT REVIEW"
            else:
                status = "IN PROGRESS"

            reviewer_id = record.get("reviewed_by")

            if reviewer_id:
                reviewer = (
                    f"<@{reviewer_id}> "
                    f"({record.get('reviewed_by_name', 'Unknown')})"
                )
            else:
                reviewer = "Not reviewed yet"

            created = record.get("created_at", "Unknown")
            attempt_id = record.get("attempt_id", "Unknown")

            embed.add_field(
                name=f"Attempt {index} - {status}",
                value=(
                    f"**Attempt ID:** `{attempt_id[:12]}`\n"
                    f"**Started:** {created}\n"
                    f"**Reviewed by:** {reviewer}"
                ),
                inline=False
            )

        if len(attempts) > 20:
            embed.set_footer(
                text=f"Showing the 20 most recent attempts out of {len(attempts)}."
            )
        else:
            embed.set_footer(
                text="The Farmers Oak | Staff Management"
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TrainingQuiz(bot))

    # Restore persistent public quiz and review buttons.
    bot.add_view(PublicQuizPanelView())
    bot.add_view(QuizReviewView())

    # Restore individual DM quiz buttons after a restart.
    data = load_data()

    for message_id, user_id in data.get("begin_messages", {}).items():
        try:
            bot.add_view(
                BeginQuizView(int(user_id)),
                message_id=int(message_id)
            )
        except (ValueError, TypeError):
            continue
