import discord
from discord.ext import commands
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
YOUR_USER_ID = int(os.getenv("OWNER_ID"))
BUMP_CHANNEL_ID = int(os.getenv("BUMP_CHANNEL_ID"))
ALLOWED_SERVER = int(os.getenv("ALLOWED_SERVER"))

intents = discord.Intents.default()
intents.bans = True
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Ban tracking settings
time_frame_blabla = 10  # minutes
BAN_THRESHOLD = 5
TIME_WINDOW = timedelta(minutes=time_frame_blabla)
ban_log = defaultdict(list)
banned_users_by_banner = defaultdict(list)

# Bump timer tracking
last_bump_time = None
BUMP_COOLDOWN = timedelta(minutes=120)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    # Send startup message
    channel = bot.get_channel(BUMP_CHANNEL_ID)
    if channel:
        try:
            await channel.send("I got updated by HaL. Beware...")
            print(f"✅ Sent initial test message in #{channel.name}")
        except Exception as e:
            print(f"⚠️ Failed to send initial test message: {e}")

@bot.event
async def on_message(message):
    global last_bump_time
    await bot.process_commands(message)

    if message.guild and message.channel.id == BUMP_CHANNEL_ID and message.content.strip().lower() == "/bump":
        print(f"✅ Bump command received in #{message.channel.name} from {message.author.name}")
        now = datetime.now(timezone.utc)
        if not last_bump_time or (now - last_bump_time) >= BUMP_COOLDOWN:
            last_bump_time = now
            try:
                await message.channel.send("✅ Bump registered. Next reminder in 120 minutes.")
                await asyncio.sleep(BUMP_COOLDOWN.total_seconds())
                await message.channel.send("⏰ It's time to **/bump** the server again!")
            except Exception as e:
                print(f"⚠️ Failed during bump timer: {e}")
        else:
            print("⏳ Bump ignored. Timer is still active.")

    # DM commands for message deletion
    if message.guild is None and message.author.id == YOUR_USER_ID:
        content = message.content.strip()

        if content.lower() == "delete all":
            try:
                dm_channel = message.channel
                deleted_count = 0
                async for msg in dm_channel.history(limit=None):
                    if msg.author == bot.user:
                        await msg.delete()
                        deleted_count += 1
                await dm_channel.send(f"✅ Deleted {deleted_count} of my DM messages.")
            except discord.Forbidden:
                await message.channel.send("❌ I don't have permission to delete messages here.")
            except Exception as e:
                await message.channel.send(f"⚠️ An error occurred: {e}")

        elif content.lower().startswith("delete user "):
            try:
                target_id = content[12:].strip()
                if not target_id.isdigit():
                    await message.channel.send("⚠️ Please provide a valid user ID.")
                    return
                target_id = int(target_id)

                deleted_count = 0
                for guild in bot.guilds:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).read_message_history and channel.permissions_for(guild.me).manage_messages:
                            try:
                                async for msg in channel.history(limit=None):
                                    if msg.author.id == target_id:
                                        await msg.delete()
                                        deleted_count += 1
                            except (discord.Forbidden, discord.HTTPException):
                                continue

                await message.channel.send(f"✅ Deleted `{deleted_count}` messages from user ID `{target_id}`.")
            except Exception as e:
                await message.channel.send(f"⚠️ An error occurred: {e}")

@bot.event
async def on_member_ban(guild, user):
    if guild.id != ALLOWED_SERVER:
        print(f"{guild.name} tried to use your bot. ID = {guild.id}")
        return

    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        if (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 10:
            banner = entry.user
            now = datetime.now(timezone.utc)

            ban_log[banner.id].append(now)
            banned_users_by_banner[banner.id].append((user.name, user.id))

            # Clean old entries
            ban_log[banner.id] = [t for t in ban_log[banner.id] if now - t <= TIME_WINDOW]
            banned_users_by_banner[banner.id] = banned_users_by_banner[banner.id][-len(ban_log[banner.id]):]

            if len(ban_log[banner.id]) >= BAN_THRESHOLD:
                member = guild.get_member(banner.id)
                owner = await bot.fetch_user(YOUR_USER_ID)

                banned_list = "\n".join([f"- {uname} ({uid})" for uname, uid in banned_users_by_banner[banner.id]])

                if member and owner:
                    try:
                        await member.edit(roles=[])
                        await owner.send(
                            f"⚠️ **{banner}** has banned {BAN_THRESHOLD} or more users within {time_frame_blabla} minutes in **{guild.name}**.\n"
                            f"🛑 All roles have been removed from them.\n\n"
                            f"**The username and ID's for the banned users:**\n{banned_list}"
                        )
                        print(f"⚠️ {banner} hit the threshold and all roles were removed.")

                        banned_users_by_banner[banner.id].clear()
                        ban_log[banner.id].clear()
                    except discord.Forbidden:
                        await owner.send(f"❌ I don't have permission to remove roles from {banner}.")
                        print(f"❌ Failed to remove roles from {banner} — missing permissions.")

bot.run(TOKEN)