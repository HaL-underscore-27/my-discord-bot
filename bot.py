import discord
from discord.ext import commands
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
YOUR_USER_ID = int(os.getenv("OWNER_ID"))  # Your Discord user ID
intents = discord.Intents.default()
intents.bans = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# Ban tracking settings
time_frame_blabla = 10  # minutes
ban_log = defaultdict(list)
banned_users_by_banner = defaultdict(list)
BAN_THRESHOLD = 10  # Number of bans within the time frame to trigger the action
TIME_WINDOW = timedelta(minutes=time_frame_blabla)

ALLOWED_SERVER = int(os.getenv("ALLOWED_SERVER"))

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    await bot.process_commands(message)  # Ensure other commands still work

    # Only respond to the owner in DMs
    if message.guild is None and message.author.id == YOUR_USER_ID:
        if message.content.strip().lower() == "delete all":
            try:
                dm_channel = message.channel
                deleted_count = 0

                async for msg in dm_channel.history(limit=None):
                    if msg.author == bot.user:
                        await msg.delete()
                        deleted_count += 1

                await dm_channel.send(f"✅ Deleted {deleted_count} of my messages.")
            except discord.Forbidden:
                await message.channel.send("❌ I don't have permission to delete messages here.")
            except Exception as e:
                await message.channel.send(f"⚠️ An error occurred: {e}")


@bot.event
async def on_member_ban(guild, user):
    if guild.id != ALLOWED_SERVER:
        print(f"{guild.name} tried to use your bot. ID = {guild.id}")
        return  # Ignore servers not in the approved list
    else:
        async for entry in guild.audit_logs(limit=1,
                                            action=discord.AuditLogAction.ban):
            if (datetime.now(timezone.utc) -
                    entry.created_at).total_seconds() < 10:
                banner = entry.user
                now = datetime.now(timezone.utc)

                # Track time and banned users
                ban_log[banner.id].append(now)
                banned_users_by_banner[banner.id].append((user.name, user.id))

                # Remove entries older than TIME_WINDOW
                ban_log[banner.id] = [
                    t for t in ban_log[banner.id] if now - t <= TIME_WINDOW
                ]
                banned_users_by_banner[banner.id] = banned_users_by_banner[
                    banner.id][-len(ban_log[banner.id]):]

                if len(ban_log[banner.id]) >= BAN_THRESHOLD:
                    member = guild.get_member(banner.id)
                    owner = await bot.fetch_user(YOUR_USER_ID)

                    # Format banned user list
                    banned_list = "\n".join([
                        f"- {uname} ({uid})"
                        for uname, uid in banned_users_by_banner[banner.id]
                    ])

                    if member and owner:
                        try:
                            await member.edit(roles=[])
                            await owner.send(
                                f"⚠️ **{banner}** has banned {BAN_THRESHOLD} or more users within {time_frame_blabla} minutes in **{guild.name}**.\n"
                                f"🛑 All roles have been removed from them.\n\n"
                                f"**The username and ID's for the banned users:**\n{banned_list}"
                            )
                            print(
                                f"⚠️ {banner} hit the threshold and all roles were removed."
                            )

                            # ✅ Clear banned list after sending
                            banned_users_by_banner[banner.id].clear()
                            ban_log[banner.id].clear()

                        except discord.Forbidden:
                            await owner.send(
                                f"❌ I don't have permission to remove roles from {banner}."
                            )
                            print(
                                f"❌ Failed to remove roles from {banner} — missing permissions."
                            )
bot.run(TOKEN)
