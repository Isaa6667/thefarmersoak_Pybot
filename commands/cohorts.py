
import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = Path("cohort_data.json")


def get_ids():
    return {
        "guild": int(os.getenv("GUILD_ID", "0")),
        "category": int(os.getenv("STAFF_CATEGORY_ID", "0")),
        "management": int(os.getenv("MANAGEMENT_ROLE_ID", "0")),
        "cohort_role": int(os.getenv("COHORT_ROLE_ID", "0")),
    }


def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "number": 0,
        "channel_id": None,
        "channel_name": None
    }


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))


def management_only():
    async def predicate(interaction: discord.Interaction):
        ids = get_ids()
        role = interaction.guild.get_role(ids["management"]) if interaction.guild else None

        if role is None or role not in interaction.user.roles:
            raise app_commands.CheckFailure(
                "You need the Management role to use this command."
            )

        return True

    return app_commands.check(predicate)


async def get_configured_objects(guild):
    ids = get_ids()

    missing = [
        key for key in ("category", "management", "cohort_role")
        if not ids[key]
    ]

    if missing:
        raise RuntimeError("Missing IDs in .env: " + ", ".join(missing))

    category = guild.get_channel(ids["category"])
    management = guild.get_role(ids["management"])
    cohort_role = guild.get_role(ids["cohort_role"])

    if category is None or not isinstance(category, discord.CategoryChannel):
        raise RuntimeError("STAFF_CATEGORY_ID must be the ID of a server category.")

    if management is None:
        raise RuntimeError("MANAGEMENT_ROLE_ID does not match a role in this server.")

    if cohort_role is None:
        raise RuntimeError("COHORT_ROLE_ID does not match a role in this server.")

    return category, management, cohort_role


class CohortConfirmView(discord.ui.View):

    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.confirmed = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the person who started this command can confirm it.",
                ephemeral=True
            )
            return False

        return True

    @discord.ui.button(
        label="Confirm: replace current cohort",
        style=discord.ButtonStyle.danger
    )
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer(ephemeral=True)

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()

        await interaction.response.edit_message(
            content="Cancelled. The current cohort has not been changed.",
            view=None
        )


class Cohorts(commands.GroupCog, group_name="cohort", group_description="Manage staff training cohorts"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="newtrainingcohort",
        description="Create the next training cohort channel"
    )
    @management_only()
    async def new_training_cohort(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        try:
            category, management, cohort_role = await get_configured_objects(
                interaction.guild
            )
        except RuntimeError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        data = load_data()

        old_channel = (
            interaction.guild.get_channel(data.get("channel_id"))
            if data.get("channel_id")
            else None
        )

        old_name = (
            old_channel.name
            if old_channel
            else data.get("channel_name") or "no current cohort"
        )

        view = CohortConfirmView(interaction.user.id)

        await interaction.followup.send(
            f"**Replace the current training cohort?**\n"
            f"Current: **{old_name}**\n"
            "This will delete that cohort channel and create the next one. "
            "Members will need to be added to the new cohort again.",
            view=view,
            ephemeral=True
        )

        await view.wait()

        if view.confirmed is not True:
            if view.confirmed is None:
                await interaction.followup.send(
                    "Confirmation timed out. Nothing was changed.",
                    ephemeral=True
                )
            return

        if old_channel:
            try:
                await old_channel.delete(
                    reason=f"Replaced by a new training cohort by {interaction.user}"
                )

            except discord.Forbidden:
                await interaction.followup.send(
                    "I couldn't delete the previous cohort. Check my Manage Channels "
                    "permission and role position. No new channel was created.",
                    ephemeral=True
                )
                return

            except discord.HTTPException as exc:
                await interaction.followup.send(
                    f"Discord couldn't delete the previous channel: {exc}",
                    ephemeral=True
                )
                return

        number = int(data.get("number", 0)) + 1
        channel_name = f"cohort-{number:03d}"

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),

            management: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            ),

            cohort_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
        }

        try:
            channel = await interaction.guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Staff training cohort {number:03d}",
                reason=f"New training cohort created by {interaction.user}"
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "I couldn't create the channel. Give the bot Manage Channels "
                "permission and move its role above the relevant roles.",
                ephemeral=True
            )
            return

        data = {
            "number": number,
            "channel_id": channel.id,
            "channel_name": channel.name
        }

        save_data(data)

        await channel.send(
            f"**Training Cohort {number:03d}**\n"
            "Welcome. Management can add members using `/cohort add`."
        )

        await interaction.followup.send(
            f"Created {channel.mention}.",
            ephemeral=True
        )

    @app_commands.command(
        name="add",
        description="Add a member to the current training cohort"
    )
    @app_commands.describe(user="The member to add")
    @management_only()
    async def add_member(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):

        await interaction.response.defer(ephemeral=True)

        data = load_data()

        channel = (
            interaction.guild.get_channel(data.get("channel_id"))
            if data.get("channel_id")
            else None
        )

        if channel is None:
            await interaction.followup.send(
                "There isn't an active cohort. Use `/cohort newtrainingcohort` first.",
                ephemeral=True
            )
            return

        try:
            _, _, cohort_role = await get_configured_objects(interaction.guild)

            await user.add_roles(
                cohort_role,
                reason=f"Added to {channel.name} by {interaction.user}"
            )

            await channel.set_permissions(
                user,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                reason=f"Added to cohort by {interaction.user}"
            )

        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.followup.send(
                f"Couldn't add that member: {exc}",
                ephemeral=True
            )
            return

        # Acceptance DM
        try:
            embed = discord.Embed(
                title="Congratulations! You've Been Accepted!",
                description=(
                    "Congratulations! Your application has been successful.\n\n"
                    "Welcome to **The Farmers Oak Training Programme**!\n\n"
                    "You've officially been accepted into our staff training cohort. "
                    "We're looking forward to having you as part of the team.\n\n"
                    f"**Your Training Cohort:** {channel.name}\n\n"
                    "Please head over to your assigned cohort channel for further "
                    "information and instructions from Management.\n\n"
                    "Welcome to The Farmers Oak!"
                ),
                colour=discord.Colour(0x355E3B)
            )

            embed.set_footer(
                text="The Farmers Oak | Staff Management"
            )

            await user.send(embed=embed)

            dm_status = "An acceptance DM has been sent."

        except discord.Forbidden:
            dm_status = (
                "I couldn't send them a DM because their direct messages "
                "are disabled or unavailable."
            )

        except discord.HTTPException:
            dm_status = "The member was added, but Discord couldn't deliver the DM."

        await interaction.followup.send(
            f"Added {user.mention} to **{channel.name}**.\n{dm_status}",
            ephemeral=True
        )

    @app_commands.command(
        name="remove",
        description="Remove a member from the current training cohort"
    )
    @app_commands.describe(user="The member to remove")
    @management_only()
    async def remove_member(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):

        await interaction.response.defer(ephemeral=True)

        data = load_data()

        channel = (
            interaction.guild.get_channel(data.get("channel_id"))
            if data.get("channel_id")
            else None
        )

        if channel is None:
            await interaction.followup.send(
                "There isn't an active cohort.",
                ephemeral=True
            )
            return

        try:
            _, _, cohort_role = await get_configured_objects(interaction.guild)

            if cohort_role in user.roles:
                await user.remove_roles(
                    cohort_role,
                    reason=f"Removed from cohort by {interaction.user}"
                )

            await channel.set_permissions(
                user,
                overwrite=None,
                reason=f"Removed from cohort by {interaction.user}"
            )

        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.followup.send(
                f"Couldn't remove that member: {exc}",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            f"Removed {user.mention} from **{channel.name}**.",
            ephemeral=True
        )

    @app_commands.command(
        name="info",
        description="Show the active training cohort"
    )
    @management_only()
    async def cohort_info(self, interaction: discord.Interaction):

        data = load_data()

        channel = (
            interaction.guild.get_channel(data.get("channel_id"))
            if data.get("channel_id")
            else None
        )

        if channel:
            await interaction.response.send_message(
                f"Active cohort: {channel.mention} "
                f"(Cohort {data['number']:03d})",
                ephemeral=True
            )

        else:
            await interaction.response.send_message(
                "There is no active training cohort.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Cohorts(bot))
