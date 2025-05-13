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
    await bot.process_commands(message)  # Ensures other commands still work

    # Only act on DMs from the owner
    if message.guild is None and message.author.id == YOUR_USER_ID:
        print(f"Received DM from {message.author}: {message.content} 'delete'")
        content = message.content.strip()

        # DELETE all messages in DMs with the owner
        if content.lower() == "delete":
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

        # DELETE messages with a specific word
        elif content.lower().startswith("delete words "):
            print(f"Received DM from {message.author}: {message.content} 'delete words'")
            try:
                target_word = content[13:].strip().lower()
                if not target_word:
                    await message.channel.send("⚠️ Please specify a word.")
                    return

                deleted_dm = 0
                dm_channel = message.channel

                # First, delete in DM history
                async for msg in dm_channel.history(limit=None):
                    if msg.author == bot.user and target_word in msg.content.lower():
                        await msg.delete()
                        deleted_dm += 1

                # Then delete in server messages
                deleted_server = 0
                for guild in bot.guilds:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).read_message_history and channel.permissions_for(guild.me).manage_messages:
                            try:
                                async for msg in channel.history(limit=None):
                                    if msg.author == bot.user and target_word in msg.content.lower():
                                        await msg.delete()
                                        deleted_server += 1
                            except discord.Forbidden:
                                continue  # skip channels bot can't access

                await dm_channel.send(
                    f"✅ Deleted `{deleted_dm}` messages in DMs and `{deleted_server}` messages in servers containing the word: `{target_word}`."
                )
            except Exception as e:
                await message.channel.send(f"⚠️ An error occurred: {e}")

        # DELETE all messages from a specific user ID
        elif content.lower().startswith("delete user "):
            print(f"Received DM from {message.author}: {message.content}' delete user'")
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
                            except discord.Forbidden:
                                continue
                            except discord.HTTPException:
                                continue

                await message.channel.send(
                    f"✅ Deleted `{deleted_count}` messages from user ID `{target_id}`."
                )
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
