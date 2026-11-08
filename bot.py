import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

intents = discord.Intents.default()
intents.members = True

class StaffBot(commands.Bot):
    async def setup_hook(self):
        for filename in os.listdir("./commands"):
            if filename.endswith(".py") and not filename.startswith("_"):
                # Strip the .py extension so Python loads the module correctly
                await self.load_extension(f"commands.{filename[:-3]}")
                
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Synced commands to test server {GUILD_ID}")
        else:
            await self.tree.sync()
            print("Synced global commands (may take time to appear)")

bot = StaffBot(command_prefix="!", intents=intents, activity=discord.Game("Staff operations"))

@bot.event
async def on_ready():
    print(f"Online as {bot.user} (ID: {bot.user.id})")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Add it to your .env file.")

bot.run(TOKEN)