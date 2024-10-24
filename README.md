# Discord Staff Activity Tracker

This Discord bot tracks staff activity across specified channels in a Discord server. It counts messages sent by staff members and generates an activity leaderboard.

![image](https://github.com/user-attachments/assets/83964121-1ac8-4ef0-9aae-36bc8e791fa9)


## Features

- Tracks activity based on specified roles (Staff for example)
- Checks activity in specified channels, including text channels, threads, and forum channels
- Generates an activity leaderboard for a configurable number of days
- Handles rate limiting to avoid Discord API restrictions
- Authorizes command usage based on specified roles

## Requirements

- Python 3.8 or higher
- discord library
- configparser library

## Setup

1. Clone this repository
2. Install the required packages:
```pip install discord configparser```

3. Create a `db_config.ini` file with the following structure:

```ini
[activity]
DISCORD_BOT_TOKEN = your_bot_token_here
DAYS_TO_CHECK = 30
RATE_LIMIT_DELAY = 5
ROLES_TO_TRACK = role_id1,role_id2,role_id3
AUTHORIZED_ROLES = auth_role_id1,auth_role_id2
CHANNELS_TO_CHECK = channel_id1,channel_id2,channel_id3
