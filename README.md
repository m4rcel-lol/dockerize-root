# Dockerize Root Bot

Dockerize Root Bot is a Root-platform port of the original Discord Dockerize bot idea. It turns a Root community into a container-like environment where every user can create one personal **container**, represented by a Root **channel group** with mounted text/voice channels inside it.

The bot does **not** run real Docker containers. It uses Docker language as a theme for safe community organization.

## Important Root differences

Discord slash commands, categories, and DMs do not exist in the same way on Root. This port uses:

- Root text commands instead of Discord slash commands.
- Root channel groups instead of Discord categories.
- Root channels instead of Discord text/voice channels.
- Root access rules instead of Discord permission overwrites.
- Root's hosted server lifecycle and Root-provided SQLite database instead of a self-hosted Discord bot process.

Root's bot SDK is beta, so some manifest permission names may need adjusting in the Developer Portal if Root changes them.

## Project structure

```txt
root-dockerize-bot/
├── root-manifest.json
├── README.md
├── Dockerfile.optional-local-dev
└── server/
    ├── package.json
    ├── tsconfig.json
    ├── .env.example
    └── src/
        ├── main.ts
        ├── config.ts
        ├── database.ts
        ├── commands.ts
        ├── messages.ts
        ├── types.ts
        ├── api/rootCommunity.ts
        ├── services/
        │   ├── channelService.ts
        │   ├── containerService.ts
        │   ├── permissions.ts
        │   └── setupService.ts
        └── utils/sanitize.ts
```

## Commands

Default prefix is `dkz`.

```txt
dkz help

dkz setup channel=<channelId> staff=<roleId>

dkz container create <name>
dkz container up
dkz container down
dkz container delete confirm
dkz container status
dkz container public
dkz container private
dkz container invite <userId>
dkz container uninvite <userId>
dkz container invites

dkz channel create [text|voice] <name>
dkz channel delete <channelId> confirm
dkz channel list

dkz admin container check <userId> <reason>
dkz admin container suspend <userId> <reason>
dkz admin container unsuspend <userId>
dkz admin container delete <userId> <reason>
dkz admin container list
dkz admin container info <userId>
dkz admin container force-private <userId>
dkz admin container force-public <userId>
```

## Setup

1. Create a Root Bot in the Root Developer Portal.
2. Copy the app/bot ID into `root-manifest.json`.
3. From the `server` folder, install dependencies:

```bash
npm install
```

4. Create a local dev env file:

```bash
cp .env.example .env
```

5. Add your `DEV_TOKEN` from the Root Developer Portal.
6. Build and run locally with Root devhost:

```bash
npm run build
npm run bot
```

## Runtime setup in Root

After the bot is running in your Root community, run this in a channel:

```txt
dkz setup channel=<command-channel-id> staff=<staff-role-id>
```

Use Root Developer Mode to copy channel, role, and member IDs.

## Public containers

Root access rules are based on role/member IDs. The bot supports explicit owner, invited-user, and staff rules. For truly public containers, set the `EVERYONE_ROLE_ID` environment variable if your Root community exposes an everyone/public role GUID.

Without `EVERYONE_ROLE_ID`, `dkz container public` still changes the stored visibility state and keeps owner/staff/invited rules valid, but it cannot safely guess the Root GUID for everyone.

## Persistence

The bot uses SQLite through `sqlite3`. In Root, the database filename is taken from:

```ts
rootServer.dataStore.config.sqlite3.filename
```

That lets Root back up and restore the database file.

## Notes

- Root Bots are written in TypeScript and run in a Node.js environment.
- Root Bots are server-only and interact through channel messages.
- Root Bot servers are hosted/managed by Root when installed in a community.
- This code intentionally avoids Discord-specific concepts such as slash commands, embeds, gateway intents, guild categories, and DMs.

## Troubleshooting

### The bot does not respond

Check:

- Your `DEV_TOKEN` is valid.
- `npm run bot` is running.
- You are using the configured command prefix.
- The bot has the required Root permissions in `root-manifest.json`.

### Commands are rejected outside one channel

Run setup again:

```txt
dkz setup channel=<new-command-channel-id> staff=<staff-role-id>
```

### Staff commands fail

Make sure `staff=<roleId>` points to the Root role ID and that your member has that role.

### Public mode does not expose to everyone

Set `EVERYONE_ROLE_ID` if Root exposes a public/everyone role GUID for your community.

## License

MIT
