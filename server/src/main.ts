import { rootServer, ChannelMessageEvent, ChannelMessageCreatedEvent, RootBotStartState } from '@rootsdk/server-bot';
import { closeDatabase, getSettings, initDatabase } from './database';
import { loadRuntimeConfig } from './config';
import { dispatch, parseArgs } from './commands';
import { CommandContext, RuntimeConfig } from './types';
import { getMember } from './api/rootCommunity';
import { ICON, safeSend, terminal } from './messages';

let runtimeConfig: RuntimeConfig = loadRuntimeConfig();

function eventUserId(evt: any): string | undefined {
  return evt.userId ?? evt.senderUserId ?? evt.createdByUserId ?? evt.memberId ?? evt.authorId;
}

async function isStaff(userId: string, config: RuntimeConfig): Promise<boolean> {
  if (!config.staffRoleId) return false;
  const member = await getMember(userId);
  const roles: string[] = member?.roleIds ?? member?.roles?.map((r: any) => r.roleId ?? r.id) ?? [];
  return roles.includes(config.staffRoleId);
}

async function onMessage(evt: ChannelMessageCreatedEvent): Promise<void> {
  const anyEvt = evt as any;
  const content = anyEvt.messageContent ?? anyEvt.content ?? '';
  const channelId = anyEvt.channelId;
  const userId = eventUserId(anyEvt);
  if (!content || !channelId || !userId) return;
  const args = parseArgs(content, runtimeConfig.commandPrefix);
  if (!args) return;

  const staff = await isStaff(userId, runtimeConfig);
  const isSetup = args[0] === 'setup';
  const isAdmin = args[0] === 'admin';
  if (runtimeConfig.commandChannelId && channelId !== runtimeConfig.commandChannelId && !staff && !isSetup && !isAdmin) {
    await safeSend(channelId, terminal(`${ICON.failure} Command rejected`, `Error: Dockerize commands must be run in the configured command channel`, `Allowed channel ID: \`${runtimeConfig.commandChannelId}\``));
    return;
  }

  const member = await getMember(userId);
  const ctx: CommandContext = {
    channelId,
    userId,
    memberNickname: member?.nickname ?? member?.displayName ?? member?.name ?? userId.slice(0, 8),
    rawContent: content,
    args,
    config: runtimeConfig,
    isStaff: staff,
  };

  try {
    await dispatch(ctx);
  } catch (error) {
    console.error('[dockerize] command failed', error);
    await safeSend(channelId, terminal(`${ICON.failure} Runtime error`, 'Error: command failed unexpectedly\nCheck the Root Developer Log for stack traces.'));
  }
}

async function onStarting(state: RootBotStartState): Promise<void> {
  runtimeConfig = loadRuntimeConfig(state);
  await initDatabase();
  const stored = await getSettings();
  runtimeConfig.commandChannelId = stored?.command_channel_id ?? runtimeConfig.commandChannelId;
  runtimeConfig.staffRoleId = stored?.staff_role_id ?? runtimeConfig.staffRoleId;
  rootServer.community.channelMessages.on(ChannelMessageEvent.ChannelMessageCreated, onMessage);
  console.log('[dockerize] Root bot started');
  console.log(`[dockerize] prefix=${runtimeConfig.commandPrefix} maxChannels=${runtimeConfig.maxChannelsPerContainer}`);
}

async function onStopping(): Promise<void> {
  console.log('[dockerize] Root bot stopping');
  await closeDatabase();
}

(async () => {
  await rootServer.lifecycle.start(onStarting, onStopping);
})();
