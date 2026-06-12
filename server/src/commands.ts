import { CommandContext } from './types';
import { handleSetup } from './services/setupService';
import { adminCheck, adminDelete, adminForceVisibility, adminInfo, adminList, adminSuspend, adminUnsuspend, containerDown, containerStatus, containerUp, createUserContainer, deleteOwnContainer, inviteUser, makePrivate, makePublic, showInvites, uninviteUser } from './services/containerService';
import { createContainerChannel, deleteContainerChannel, listContainerChannels } from './services/channelService';
import { ICON, safeSend, terminal } from './messages';

export function parseArgs(content: string, prefix: string): string[] | null {
  const trimmed = content.trim();
  if (!trimmed.toLowerCase().startsWith(prefix.toLowerCase())) return null;
  return trimmed.slice(prefix.length).trim().split(/\s+/).filter(Boolean);
}

export async function dispatch(ctx: CommandContext): Promise<void> {
  const [group, sub, action] = ctx.args;
  if (!group || group === 'help') return help(ctx);
  if (group === 'setup') return handleSetup(ctx);
  if (group === 'container') {
    switch (sub) {
      case 'create': return createUserContainer(ctx);
      case 'up': return containerUp(ctx);
      case 'down': return containerDown(ctx);
      case 'delete': return deleteOwnContainer(ctx);
      case 'status': return containerStatus(ctx);
      case 'public': return makePublic(ctx);
      case 'private': return makePrivate(ctx);
      case 'invite': return inviteUser(ctx);
      case 'uninvite': return uninviteUser(ctx);
      case 'invites': return showInvites(ctx);
      default: return help(ctx);
    }
  }
  if (group === 'channel') {
    switch (sub) {
      case 'create': return createContainerChannel(ctx);
      case 'delete': return deleteContainerChannel(ctx);
      case 'list': return listContainerChannels(ctx);
      default: return help(ctx);
    }
  }
  if (group === 'admin' && sub === 'container') {
    switch (action) {
      case 'check': return adminCheck(ctx);
      case 'suspend': return adminSuspend(ctx);
      case 'unsuspend': return adminUnsuspend(ctx);
      case 'delete': return adminDelete(ctx);
      case 'list': return adminList(ctx);
      case 'info': return adminInfo(ctx);
      case 'force-private': return adminForceVisibility(ctx, 'private');
      case 'force-public': return adminForceVisibility(ctx, 'public');
      default: return help(ctx);
    }
  }
  await help(ctx);
}

async function help(ctx: CommandContext): Promise<void> {
  const p = ctx.config.commandPrefix;
  await safeSend(ctx.channelId, terminal(`${ICON.docker} Dockerize Root Bot`, `${p} setup channel=<channelId> staff=<roleId>\n${p} container create <name>\n${p} container up | down | status | public | private\n${p} container invite <userId> | uninvite <userId> | invites\n${p} container delete confirm\n${p} channel create [text|voice] <name>\n${p} channel delete <channelId> confirm\n${p} channel list\n${p} admin container check <userId> <reason>\n${p} admin container suspend <userId> <reason>\n${p} admin container unsuspend <userId>\n${p} admin container delete <userId> <reason>\n${p} admin container list | info <userId>\n${p} admin container force-private <userId> | force-public <userId>`, 'Root version uses text commands because Root Bots interact through channel messages.'));
}
