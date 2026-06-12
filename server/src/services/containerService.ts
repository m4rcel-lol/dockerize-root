import { CommandContext, ContainerRecord } from '../types';
import { addChannel, addInvite, countChannels, createContainer, deleteContainerRecord, getContainer, listChannels, listContainers, listInvites, removeInvite, setVisibility, updateContainer } from '../database';
import { createChannel, createChannelGroup, deleteChannelGroup, editChannelGroup } from '../api/rootCommunity';
import { applyDown, applyPrivate, applyPublic, applySuspended } from './permissions';
import { containerDisplayName, extractId, nowIso, sanitizeName } from '../utils/sanitize';
import { animate, ICON, safeSend, terminal } from '../messages';

function statusTable(row: ContainerRecord, channelCount: number, invites: string[]): string {
  const id = `dkz-${String(row.id).padStart(4, '0')}`;
  return `CONTAINER ID   OWNER         STATUS       VISIBILITY   CHANNELS   INVITES\n${id.padEnd(15)} ${('@' + row.owner_name).padEnd(13)} ${row.status.padEnd(12)} ${row.visibility.padEnd(12)} ${String(channelCount).padEnd(9)} ${invites.length}`;
}

async function createDefaultChannels(ownerId: string, groupId: string): Promise<{ terminal: any; logs: any; general: any; voice: any }> {
  const terminalCh = await createChannel(groupId, 'terminal', 'text');
  const logsCh = await createChannel(groupId, 'logs', 'text');
  const generalCh = await createChannel(groupId, 'general', 'text');
  const voiceCh = await createChannel(groupId, 'runtime', 'voice');
  await addChannel(ownerId, terminalCh.channelId ?? terminalCh.id, 'terminal', 'text', true);
  await addChannel(ownerId, logsCh.channelId ?? logsCh.id, 'logs', 'text', true);
  await addChannel(ownerId, generalCh.channelId ?? generalCh.id, 'general', 'text', true);
  await addChannel(ownerId, voiceCh.channelId ?? voiceCh.id, 'runtime', 'voice', true);
  return { terminal: terminalCh, logs: logsCh, general: generalCh, voice: voiceCh };
}

export async function createUserContainer(ctx: CommandContext): Promise<void> {
  const requested = ctx.args.slice(2).join(' ') || ctx.memberNickname;
  const existing = await getContainer(ctx.userId);
  if (existing) {
    await safeSend(ctx.channelId, terminal(`${ICON.failure} Container failed to start`, 'Error: container already exists for this user', 'You already have a Dockerize container in this Root community.'));
    return;
  }
  const name = containerDisplayName(ctx.memberNickname, requested);
  const frames = [
    '$ docker compose up -d\n[+] Building Dockerize namespace...',
    '$ docker compose up -d\n[+] Creating private channel group...\n[+] Mounting Root channels...',
    '$ docker compose up -d\n[+] Creating private channel group...\n[+] Mounting Root channels...\n[+] Applying permission overlays...',
    '$ docker compose up -d\n[+] Creating private channel group...\n[+] Mounting Root channels...\n[+] Applying permission overlays...\n[+] Container started successfully.'
  ];
  const group = await createChannelGroup(`🐳 ${name}`);
  const groupId = group.channelGroupId ?? group.id;
  const channels = await createDefaultChannels(ctx.userId, groupId);
  const visibility = ctx.config.defaultContainerVisibility;
  const now = nowIso();
  await createContainer({
    owner_id: ctx.userId,
    owner_name: ctx.memberNickname,
    container_name: name,
    channel_group_id: groupId,
    terminal_channel_id: channels.terminal.channelId ?? channels.terminal.id,
    logs_channel_id: channels.logs.channelId ?? channels.logs.id,
    general_channel_id: channels.general.channelId ?? channels.general.id,
    voice_channel_id: channels.voice.channelId ?? channels.voice.id,
    status: 'up',
    visibility,
    inspection_active: 0,
    suspended_reason: null,
    created_at: now,
    updated_at: now,
  });
  if (visibility === 'public') await applyPublic(groupId, ctx.userId, [], ctx.config.staffRoleId);
  else await applyPrivate(groupId, ctx.userId, [], ctx.config.staffRoleId);
  const final = terminal(`${ICON.success} Container started`, '$ docker compose up -d\n[+] Namespace mounted\n[+] Channel volumes mounted\n[+] Permission layer applied\n[+] Container is online', `Container: \`${name}\`\nStatus: \`up\`\nVisibility: \`${visibility}\`\nChannels: \`terminal\`, \`logs\`, \`general\`, 🔊 \`runtime\``);
  await animate(ctx.channelId, frames, final);
  await safeSend(channels.terminal.channelId ?? channels.terminal.id, terminal(`${ICON.docker} Your Dockerize container is online`, '$ docker ps\nCONTAINER       STATUS\n' + `${name}       up`, 'Your private Root container has been created and started.'));
}

export async function containerStatus(ctx: CommandContext, targetUserId?: string): Promise<void> {
  const ownerId = targetUserId ?? ctx.userId;
  const row = await getContainer(ownerId);
  if (!row) {
    await safeSend(ctx.channelId, terminal(`${ICON.failure} Container not found`, 'Error: no container exists for this user'));
    return;
  }
  if (ownerId !== ctx.userId && !ctx.isStaff) {
    await safeSend(ctx.channelId, terminal(`${ICON.failure} Access denied`, 'Error: staff permissions required'));
    return;
  }
  const channelCount = await countChannels(ownerId);
  const invites = await listInvites(ownerId);
  await safeSend(ctx.channelId, terminal(`${ICON.docker} docker ps`, statusTable(row, channelCount, invites), `Created: ${row.created_at}\nInspection active: ${row.inspection_active ? 'yes' : 'no'}\nSuspended: ${row.status === 'suspended' ? 'yes' : 'no'}`));
}

export async function containerUp(ctx: CommandContext): Promise<void> {
  const row = await getContainer(ctx.userId);
  if (!row?.channel_group_id) {
    await safeSend(ctx.channelId, terminal(`${ICON.failure} Container failed to start`, 'Error: no container record or channel group exists'));
    return;
  }
  if (row.status === 'suspended') {
    await safeSend(ctx.channelId, terminal(`${ICON.failure} Runtime suspended`, 'Error: staff must unsuspend this container before it can start'));
    return;
  }
  const invites = await listInvites(ctx.userId);
  if (row.visibility === 'public') await applyPublic(row.channel_group_id, ctx.userId, invites, ctx.config.staffRoleId);
  else await applyPrivate(row.channel_group_id, ctx.userId, invites, ctx.config.staffRoleId);
  await updateContainer(ctx.userId, { status: 'up' });
  await safeSend(ctx.channelId, terminal(`${ICON.success} Container started`, '$ docker start user-container\n[+] Permission layer restored\n[+] Container is online'));
  await safeSend(row.terminal_channel_id, terminal(`${ICON.docker} Container online`, '$ docker start\n[+] Runtime attached'));
}

export async function containerDown(ctx: CommandContext): Promise<void> {
  const row = await getContainer(ctx.userId);
  if (!row?.channel_group_id) {
    await safeSend(ctx.channelId, terminal(`${ICON.failure} Container stop failed`, 'Error: no container exists'));
    return;
  }
  const invites = await listInvites(ctx.userId);
  await applyDown(row.channel_group_id, ctx.userId, invites, ctx.config.staffRoleId);
  await updateContainer(ctx.userId, { status: 'down' });
  await safeSend(ctx.channelId, terminal(`${ICON.docker} Container stopped`, '$ docker stop user-container\n[+] Owner write access detached\n[+] Staff inspection layer kept\n[+] Runtime is down'));
}

export async function deleteOwnContainer(ctx: CommandContext): Promise<void> {
  if (!ctx.args.includes('confirm') && !ctx.args.includes('confirm=true')) {
    await safeSend(ctx.channelId, terminal(`${ICON.warning} Delete requires confirmation`, 'Usage: dkz container delete confirm'));
    return;
  }
  const row = await getContainer(ctx.userId);
  if (!row) {
    await safeSend(ctx.channelId, terminal(`${ICON.failure} Container delete failed`, 'Error: no container exists'));
    return;
  }
  if (row.channel_group_id) {
    try { await deleteChannelGroup(row.channel_group_id); } catch (error) { console.warn('[container] group delete failed', error); }
  }
  await deleteContainerRecord(ctx.userId);
  await safeSend(ctx.channelId, terminal(`${ICON.failure} Container deleted`, '$ docker compose down --volumes\n[+] Stopping container\n[+] Unmounting channels\n[+] Removing channel group\n[+] Cleaning database record'));
}

export async function makePublic(ctx: CommandContext): Promise<void> {
  const row = await getContainer(ctx.userId);
  if (!row?.channel_group_id) return safeSend(ctx.channelId, terminal(`${ICON.failure} Public mode failed`, 'Error: no container exists'));
  const invites = await listInvites(ctx.userId);
  await applyPublic(row.channel_group_id, ctx.userId, invites, ctx.config.staffRoleId);
  await setVisibility(ctx.userId, 'public');
  await safeSend(ctx.channelId, terminal(`${ICON.success} Container exposed`, '$ docker network connect public user-container\n[+] Visibility state: public', 'Note: set EVERYONE_ROLE_ID if your Root community requires an explicit Everyone access rule.'));
}

export async function makePrivate(ctx: CommandContext): Promise<void> {
  const row = await getContainer(ctx.userId);
  if (!row?.channel_group_id) return safeSend(ctx.channelId, terminal(`${ICON.failure} Private mode failed`, 'Error: no container exists'));
  const invites = await listInvites(ctx.userId);
  await applyPrivate(row.channel_group_id, ctx.userId, invites, ctx.config.staffRoleId);
  await setVisibility(ctx.userId, 'private');
  await safeSend(ctx.channelId, terminal(`${ICON.success} Container sealed`, '$ docker network disconnect public user-container\n[+] Visibility state: private\n[+] Invite rules preserved'));
}

export async function inviteUser(ctx: CommandContext): Promise<void> {
  const userId = extractId(ctx.args[2]);
  const row = await getContainer(ctx.userId);
  if (!userId || !row?.channel_group_id) return safeSend(ctx.channelId, terminal(`${ICON.failure} Invite failed`, 'Usage: dkz container invite <userId>'));
  if (userId === ctx.userId) return safeSend(ctx.channelId, terminal(`${ICON.failure} Invite failed`, 'Error: cannot invite yourself'));
  await addInvite(ctx.userId, userId);
  const invites = await listInvites(ctx.userId);
  if (row.visibility === 'public') await applyPublic(row.channel_group_id, ctx.userId, invites, ctx.config.staffRoleId);
  else await applyPrivate(row.channel_group_id, ctx.userId, invites, ctx.config.staffRoleId);
  await safeSend(ctx.channelId, terminal(`${ICON.success} User invited`, `$ dockerize invite ${userId}\n[+] Access rule created\n[+] User can view/send/connect inside the container`, `Container: \`${row.container_name}\``));
  await safeSend(row.logs_channel_id, terminal(`${ICON.docker} Invite event`, `[+] User ${userId} was invited by ${ctx.memberNickname}`));
}

export async function uninviteUser(ctx: CommandContext): Promise<void> {
  const userId = extractId(ctx.args[2]);
  const row = await getContainer(ctx.userId);
  if (!userId || !row?.channel_group_id) return safeSend(ctx.channelId, terminal(`${ICON.failure} Uninvite failed`, 'Usage: dkz container uninvite <userId>'));
  await removeInvite(ctx.userId, userId);
  const invites = await listInvites(ctx.userId);
  if (row.visibility === 'public') await applyPublic(row.channel_group_id, ctx.userId, invites, ctx.config.staffRoleId);
  else await applyPrivate(row.channel_group_id, ctx.userId, invites, ctx.config.staffRoleId);
  await safeSend(ctx.channelId, terminal(`${ICON.warning} Container access removed`, `$ dockerize uninvite ${userId}\n[+] Access rule removed`));
}

export async function showInvites(ctx: CommandContext): Promise<void> {
  const row = await getContainer(ctx.userId);
  if (!row) return safeSend(ctx.channelId, terminal(`${ICON.failure} Invites unavailable`, 'Error: no container exists'));
  const invites = await listInvites(ctx.userId);
  const body = invites.length ? invites.map((id, i) => `${String(i + 1).padStart(2, '0')}   ${id}`).join('\n') : 'No invited users.';
  await safeSend(ctx.channelId, terminal(`${ICON.docker} Container invites`, body));
}

export async function adminList(ctx: CommandContext): Promise<void> {
  if (!ctx.isStaff) return safeSend(ctx.channelId, terminal(`${ICON.failure} Access denied`, 'Error: staff permissions required'));
  const rows = await listContainers();
  const body = rows.length ? rows.map(r => `dkz-${String(r.id).padStart(4, '0')}   ${r.owner_name.padEnd(14)} ${r.status.padEnd(11)} ${r.visibility}`).join('\n') : 'No containers found.';
  await safeSend(ctx.channelId, terminal(`${ICON.docker} docker ps --all`, `CONTAINER ID   OWNER          STATUS      VISIBILITY\n${body}`));
}

export async function adminCheck(ctx: CommandContext): Promise<void> {
  if (!ctx.isStaff) return safeSend(ctx.channelId, terminal(`${ICON.failure} Access denied`, 'Error: staff permissions required'));
  const userId = extractId(ctx.args[3]);
  const reason = ctx.args.slice(4).join(' ') || 'No reason provided.';
  if (!userId) return safeSend(ctx.channelId, terminal(`${ICON.failure} Check failed`, 'Usage: dkz admin container check <userId> <reason>'));
  const row = await getContainer(userId);
  if (!row) return safeSend(ctx.channelId, terminal(`${ICON.failure} Check failed`, 'Error: target has no container'));
  await updateContainer(userId, { inspection_active: 1 });
  await safeSend(ctx.channelId, terminal(`${ICON.warning} Container inspection started`, `$ docker inspect ${row.container_name}\n[!] Staff inspection mode enabled\n[!] Owner notification posted`, `Reason: ${reason}`));
  await safeSend(row.logs_channel_id, terminal(`${ICON.warning} Your Dockerize container is being checked`, `[!] Staff inspection mode enabled`, `Reason: ${reason}\nThis does not mean you are suspended. It means staff is reviewing the container.`));
}

export async function adminSuspend(ctx: CommandContext): Promise<void> {
  if (!ctx.isStaff) return safeSend(ctx.channelId, terminal(`${ICON.failure} Access denied`, 'Error: staff permissions required'));
  const userId = extractId(ctx.args[3]);
  const reason = ctx.args.slice(4).join(' ') || 'No reason provided.';
  const row = userId ? await getContainer(userId) : undefined;
  if (!userId || !row?.channel_group_id) return safeSend(ctx.channelId, terminal(`${ICON.failure} Suspend failed`, 'Usage: dkz admin container suspend <userId> <reason>'));
  const invites = await listInvites(userId);
  await applySuspended(row.channel_group_id, userId, invites, ctx.config.staffRoleId);
  try { await editChannelGroup(row.channel_group_id, `suspended-${sanitizeName(row.owner_name, 'user')}`); } catch {}
  await updateContainer(userId, { status: 'suspended', suspended_reason: reason });
  await safeSend(ctx.channelId, terminal(`${ICON.failure} Runtime suspended`, `$ docker container pause ${row.container_name}\n[!] Freezing permissions\n[!] Locking owner access\n[!] Staff inspection mode enabled`, `Reason: ${reason}`));
  await safeSend(row.logs_channel_id, terminal(`${ICON.failure} Your Dockerize container was suspended`, `[!] Runtime access locked`, `Reason: ${reason}`));
}

export async function adminUnsuspend(ctx: CommandContext): Promise<void> {
  if (!ctx.isStaff) return safeSend(ctx.channelId, terminal(`${ICON.failure} Access denied`, 'Error: staff permissions required'));
  const userId = extractId(ctx.args[3]);
  const row = userId ? await getContainer(userId) : undefined;
  if (!userId || !row?.channel_group_id) return safeSend(ctx.channelId, terminal(`${ICON.failure} Unsuspend failed`, 'Usage: dkz admin container unsuspend <userId>'));
  const invites = await listInvites(userId);
  if (row.visibility === 'public') await applyPublic(row.channel_group_id, userId, invites, ctx.config.staffRoleId);
  else await applyPrivate(row.channel_group_id, userId, invites, ctx.config.staffRoleId);
  try { await editChannelGroup(row.channel_group_id, `🐳 ${row.container_name}`); } catch {}
  await updateContainer(userId, { status: 'up', suspended_reason: null });
  await safeSend(ctx.channelId, terminal(`${ICON.success} Runtime unsuspended`, `$ docker container unpause ${row.container_name}\n[+] Access restored\n[+] Container is online`));
  await safeSend(row.terminal_channel_id, terminal(`${ICON.success} Your Dockerize container was unsuspended`, `[+] Runtime access restored`));
}

export async function adminDelete(ctx: CommandContext): Promise<void> {
  if (!ctx.isStaff) return safeSend(ctx.channelId, terminal(`${ICON.failure} Access denied`, 'Error: staff permissions required'));
  const userId = extractId(ctx.args[3]);
  const reason = ctx.args.slice(4).join(' ') || 'No reason provided.';
  const row = userId ? await getContainer(userId) : undefined;
  if (!userId || !row) return safeSend(ctx.channelId, terminal(`${ICON.failure} Admin delete failed`, 'Usage: dkz admin container delete <userId> <reason>'));
  if (row.channel_group_id) { try { await deleteChannelGroup(row.channel_group_id); } catch {} }
  await deleteContainerRecord(userId);
  await safeSend(ctx.channelId, terminal(`${ICON.failure} Container deleted by staff`, `$ docker compose down --volumes ${row.container_name}\n[+] Channel group removed\n[+] Database record deleted`, `Reason: ${reason}`));
}

export async function adminInfo(ctx: CommandContext): Promise<void> {
  if (!ctx.isStaff) return safeSend(ctx.channelId, terminal(`${ICON.failure} Access denied`, 'Error: staff permissions required'));
  const userId = extractId(ctx.args[3]);
  return containerStatus(ctx, userId);
}

export async function adminForceVisibility(ctx: CommandContext, visibility: 'private' | 'public'): Promise<void> {
  if (!ctx.isStaff) return safeSend(ctx.channelId, terminal(`${ICON.failure} Access denied`, 'Error: staff permissions required'));
  const userId = extractId(ctx.args[3]);
  const row = userId ? await getContainer(userId) : undefined;
  if (!userId || !row?.channel_group_id) return safeSend(ctx.channelId, terminal(`${ICON.failure} Force visibility failed`, 'Usage: dkz admin container force-private|force-public <userId>'));
  const invites = await listInvites(userId);
  if (visibility === 'public') await applyPublic(row.channel_group_id, userId, invites, ctx.config.staffRoleId);
  else await applyPrivate(row.channel_group_id, userId, invites, ctx.config.staffRoleId);
  await setVisibility(userId, visibility);
  await safeSend(ctx.channelId, terminal(`${ICON.success} Visibility forced`, `$ dockerize visibility --set ${visibility}\n[+] Permission overlays rebuilt`, `Container: ${row.container_name}`));
}
