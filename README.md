# Dockerize

Dockerize is a production-ready, slash-command-only Discord bot that turns a Discord server into a container-like environment.

Each user can create one private “container,” represented by a Discord category with isolated text/voice channels:

- `terminal`
- `logs`
- `general`
- `runtime` voice channel

The bot does **not** run real Docker containers. It only uses Docker-like language, terminal-style embeds, and Discord permission layers to create a fun isolated workspace system.

## Features

- Slash commands only
- No message content intent
- One container per user per server
- Private/public containers
- User invite/uninvite system
- User channel creation/deletion inside containers
- Staff inspection, suspension, unsuspension, forced visibility, deletion
- SQLite persistence with `aiosqlite`
- Animated terminal-style embeds by editing the same interaction response
- Docker Compose deployment
- Alpine-based Docker image
- Custom emoji variables with safe raw-text fallback

## Required Bot Permissions

Invite the bot with the `bot` and `applications.commands` scopes.

Recommended permissions:

- Manage Channels
- View Channels
- Send Messages
- Embed Links
- Use External Emojis
- Read Message History
- Connect
- Speak

Permission integer for the above list:

```txt
3492880
```

Invite URL format:

```txt
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=3492880&scope=bot%20applications.commands
```

## Discord Developer Portal Setup

1. Go to the Discord Developer Portal.
2. Create a new application named `Dockerize`.
3. Open the **Bot** tab.
4. Create/reset the bot token and copy it.
5. Keep **Message Content Intent** disabled.
6. Invite the bot using the URL above.
7. Make sure the bot role is high enough to manage channels/categories it creates.

## Installation

Clone or upload this project to your Linux server.

```bash
cp .env.example .env
nano .env
```

Set your token:

```env
DISCORD_TOKEN=your-real-token-here
DATABASE_PATH=/app/data/dockerize.sqlite3
MAX_CHANNELS_PER_CONTAINER=10
DEFAULT_CONTAINER_VISIBILITY=private
ALLOW_BOT_INVITES=false
EMOJI_DOCKER=:docker:
EMOJI_SUCCESS=:success:
EMOJI_FAILURE=:failure:
EMOJI_WARNING=:warning:
```

Run it:

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f
```

Stop it:

```bash
docker compose down
```

## First Server Setup

Run this command as an administrator:

```txt
/setup command_channel:#dockerize staff_role:@Staff
```

After setup, normal users can run Dockerize commands in the configured command channel. They can also use supported commands from inside their own container.

## Command List

### Container Commands

```txt
/container create name:<name>
/container up
/container down
/container delete confirm:<true|false>
/container status
/container public
/container private
/container invite user:@user
/container uninvite user:@user
/container invites
```

### Channel Commands

```txt
/channel create name:<name> type:<text|voice>
/channel delete channel:#channel confirm:<true|false> force:<true|false>
/channel list
```

`force:true` is staff-only and is used for deleting protected system channels.

### Admin Commands

```txt
/admin container check user:@user reason:<text>
/admin container suspend user:@user reason:<text>
/admin container unsuspend user:@user
/admin container delete user:@user reason:<text>
/admin container list
/admin container info user:@user
/admin container force-private user:@user
/admin container force-public user:@user
```

## Example Usage Flow

1. Admin initializes Dockerize:

```txt
/setup command_channel:#dockerize staff_role:@Staff
```

2. User creates a container:

```txt
/container create name:marcel
```

3. User mounts another text channel:

```txt
/channel create name:projects type:text
```

4. User invites a friend:

```txt
/container invite user:@friend
```

5. Staff checks a container:

```txt
/admin container check user:@marcel reason:Routine namespace inspection
```

6. User stops the container:

```txt
/container down
```

7. User starts it again:

```txt
/container up
```

## Custom Emoji Notes

The bot reads emoji values from `.env`:

```env
EMOJI_DOCKER=:docker:
EMOJI_SUCCESS=:success:
EMOJI_FAILURE=:failure:
EMOJI_WARNING=:warning:
```

For real custom emojis, use the Discord formatted value:

```env
EMOJI_DOCKER=<:docker:123456789012345678>
```

If the emoji is not available in a server, the bot still works and displays the raw configured text.

## Data Storage

The default database path inside Docker is:

```txt
/app/data/dockerize.sqlite3
```

The compose file mounts it to:

```txt
./data:/app/data
```

Back up the `data` folder if you want to preserve containers across server moves.

## Troubleshooting

### Slash commands do not show up

- Make sure the bot was invited with `applications.commands` scope.
- Wait a minute after startup.
- Check logs with `docker compose logs -f`.

### Bot says it is missing permissions

Give the bot role these permissions:

- Manage Channels
- View Channels
- Send Messages
- Embed Links
- Read Message History
- Connect
- Speak

Also place the bot role above roles it needs to manage through channel overwrites.

### Container category was manually deleted

Run:

```txt
/container up
```

The bot will try to recreate missing category/channels and update the database.

### User cannot see their container

- Check if it is down: `/container status`
- Check if staff suspended it: `/admin container info user:@user`
- Staff can restore it with `/admin container unsuspend` if suspended.

### DMs fail

The bot will not crash if DMs are closed. It logs the failure and mentions it in the command embed where useful.

## Development Without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```
