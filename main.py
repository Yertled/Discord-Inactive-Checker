import configparser
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import asyncio
import logging
from collections import defaultdict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Load configuration
config = configparser.ConfigParser()
config.read('db_config.ini')

# Configuration
DAYS_TO_CHECK = config.getint('activity', 'DAYS_TO_CHECK')
RATE_LIMIT_DELAY = config.getint('activity', 'RATE_LIMIT_DELAY')
ROLES_TO_TRACK = [int(role_id) for role_id in config.get('activity', 'ROLES_TO_TRACK').split(',')]
AUTHORIZED_ROLES = [int(role_id) for role_id in config.get('activity', 'AUTHORIZED_ROLES').split(',')]
CHANNELS_TO_CHECK = [int(channel_id) for channel_id in config.get('activity', 'CHANNELS_TO_CHECK').split(',')]

# Discord bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


async def handle_rate_limit(exception):
    if isinstance(exception, discord.errors.HTTPException) and exception.status == 429:
        retry_after = getattr(exception, 'retry_after', RATE_LIMIT_DELAY)
        logging.info(f"Rate limited. Waiting for {retry_after} seconds.")
        await asyncio.sleep(retry_after)
        return True
    return False


def is_authorized():
    async def predicate(ctx):
        return any(role.id in AUTHORIZED_ROLES for role in ctx.author.roles)

    return commands.check(predicate)


async def check_channel_activity(channel, member, start_date):
    count = 0
    try:
        if isinstance(channel, discord.ForumChannel):
            async for thread in channel.archived_threads(limit=None, before=datetime.now(timezone.utc)):
                if thread.created_at < start_date:
                    break
                async for message in thread.history(limit=None, after=start_date):
                    if message.author.id == member.id:
                        count += 1
            for thread in channel.threads:
                async for message in thread.history(limit=None, after=start_date):
                    if message.author.id == member.id:
                        count += 1
        elif isinstance(channel, (discord.TextChannel, discord.Thread)):
            async for message in channel.history(limit=None, after=start_date):
                if message.author.id == member.id:
                    count += 1
        else:
            logging.warning(f"Unsupported channel type for {channel.name}: {type(channel)}")
    except discord.errors.Forbidden:
        logging.warning(f"No permission to read history in channel {channel.name}")
    except discord.errors.HTTPException as e:
        if await handle_rate_limit(e):
            return await check_channel_activity(channel, member, start_date)
        else:
            logging.error(f"Error checking channel {channel.name}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error checking channel {channel.name}: {e}")

    logging.info(f"Total messages found for {member.name} (ID: {member.id}) in {channel.name}: {count}")
    return count


@bot.command()
@is_authorized()
async def activity(ctx):
    logging.info(f"'activity' command invoked by {ctx.author} in {ctx.guild.name}")
    guild = ctx.guild

    members_to_track = [member for member in guild.members if any(role.id in ROLES_TO_TRACK for role in member.roles)]
    logging.info(f"Found {len(members_to_track)} members to track")

    activity_counts = defaultdict(int)
    channel_activity = defaultdict(lambda: defaultdict(int))
    total_members = len(members_to_track)

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=DAYS_TO_CHECK)
    logging.info(f"Checking activity from {start_date} to {now}")

    status_message = await ctx.send("Preparing to check activity...")

    if not CHANNELS_TO_CHECK:
        await ctx.send("No channels configured to check. Please update the configuration.")
        return

    for i, member in enumerate(members_to_track):
        await status_message.edit(content=f"Checking activity: {i + 1}/{total_members}\nCurrent member: {member.name}")
        logging.info(f"Checking activity for member: {member.name}")

        for channel_id in CHANNELS_TO_CHECK:
            channel = guild.get_channel(channel_id)
            if not channel:
                channel = discord.utils.get(guild.forums, id=channel_id) or discord.utils.get(guild.threads, id=channel_id)

            if not channel:
                logging.warning(f"Channel with ID {channel_id} not found.")
                continue

            logging.info(f"Checking channel: {channel.name}")
            count = await check_channel_activity(channel, member, start_date)
            logging.info(f"Found {count} messages for {member.name} in {channel.name}")
            activity_counts[member] += count
            if count > 0:
                channel_activity[member][channel.name] += count

            await asyncio.sleep(RATE_LIMIT_DELAY)

    logging.info("Finished checking all members and channels")
    logging.info(f"Activity counts: {dict(activity_counts)}")

    sorted_activity = sorted(activity_counts.items(), key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title=f"Staff Activity in the Last {DAYS_TO_CHECK} Days", color=0x00ff00)
    embed.description = ""

    for member, count in sorted_activity:
        most_active_channel = max(channel_activity[member], key=channel_activity[member].get, default="N/A")
        nickname = member.nick if member.nick else member.name
        embed.description += f"<@{member.id}> ({nickname}) - {count} messages [Most active in: {most_active_channel}]\n"

    if len(embed.description) > 4096:
        chunks = [embed.description[i:i + 4096] for i in range(0, len(embed.description), 4096)]
        for i, chunk in enumerate(chunks):
            if i == 0:
                embed.description = chunk
                await ctx.send(embed=embed)
            else:
                new_embed = discord.Embed(description=chunk, color=0x00ff00)
                await ctx.send(embed=new_embed)
    else:
        await ctx.send(embed=embed)

    logging.info(f"Activity leaderboard generated for {ctx.guild.name}")


@activity.error
async def activity_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to use this command.")
    else:
        logging.error(f"An error occurred: {error}")
        await ctx.send("An error occurred while processing the command. Please try again later.")


# Run the bot
bot.run(config.get('activity', 'DISCORD_BOT_TOKEN'))
