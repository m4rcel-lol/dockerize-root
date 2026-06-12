import { CommandContext } from '../types';
import { addChannel, countChannels, getChannel, getContainer, listChannels, removeChannel } from '../database';
import { createChannel, deleteChannel } from '../api/rootCommunity';
import { ICON, safeSend, terminal } from '../messages';
import { sanitizeName } from '../utils/sanitize';

export async function createContainerChannel(ctx: CommandContext): Promise<void> {
  const row = await getContainer(ctx.userId);
  if (!row?.channel_group_id) return safeSend(ctx.channelId, terminal(`${ICON.failure} Channel allocation failed`, 'Error: no container exists'));
  if (row.status === 'suspended') return safeSend(ctx.channelId, terminal(`${ICON.failure} Channel allocation failed`, 'Error: container is suspended'));
  const type = (ctx.args[2] === 'voice' ? 'voice' : 'text') as 'text' | 'voice';
  const rawName = type === ctx.args[2] ? ctx.args.slice(3).join(' ') : ctx.args.slice(2).join(' ');
  const name = sanitizeName(rawName, 'mounted-channel');
  const total = await countChannels(ctx.userId);
  if (total >= ctx.config.maxChannelsPerContainer) {
    await safeSend(ctx.channelId, terminal(`${ICON.failure} Channel allocation failed`, 'Error: maximum channel limit reached', `Limit: ${ctx.config.maxChannelsPerContainer}`));
    return;
  }
  const created = await createChannel(row.channel_group_id, name, type);
  const channelId = created.channelId ?? created.id;
  await addChannel(ctx.userId, channelId, name, type, false);
  await safeSend(ctx.channelId, terminal(`${ICON.success} Channel mounted`, `$ docker volume create ${name}\n[+] Channel volume mounted inside ${row.container_name}`, `Channel ID: \`${channelId}\`\nType: \`${type}\``));
}

export async function deleteContainerChannel(ctx: CommandContext): Promise<void> {
  const channelId = ctx.args[2];
  const confirm = ctx.args.includes('confirm') || ctx.args.includes('confirm=true');
  const force = ctx.args.includes('force') || ctx.args.includes('force=true');
  if (!channelId || !confirm) return safeSend(ctx.channelId, terminal(`${ICON.warning} Channel delete requires confirmation`, 'Usage: dkz channel delete <channelId> confirm'));
  const ch = await getChannel(channelId);
  if (!ch) return safeSend(ctx.channelId, terminal(`${ICON.failure} Channel delete failed`, 'Error: channel is not tracked by Dockerize'));
  if (ch.owner_id !== ctx.userId && !ctx.isStaff) return safeSend(ctx.channelId, terminal(`${ICON.failure} Channel delete failed`, 'Error: you can only delete channels in your own container'));
  if (ch.is_system && !force) return safeSend(ctx.channelId, terminal(`${ICON.failure} Channel delete failed`, 'Error: system channels require staff force=true'));
  if (ch.is_system && !ctx.isStaff) return safeSend(ctx.channelId, terminal(`${ICON.failure} Channel delete failed`, 'Error: only staff can force-delete system channels'));
  try { await deleteChannel(channelId); } catch (error) { console.warn('[channel] delete failed', error); }
  await removeChannel(channelId);
  await safeSend(ctx.channelId, terminal(`${ICON.failure} Channel unmounted`, `$ docker volume rm ${ch.channel_name}\n[+] Channel removed from container metadata`));
}

export async function listContainerChannels(ctx: CommandContext): Promise<void> {
  const row = await getContainer(ctx.userId);
  if (!row) return safeSend(ctx.channelId, terminal(`${ICON.failure} Channel list failed`, 'Error: no container exists'));
  const channels = await listChannels(ctx.userId);
  const body = channels.length
    ? channels.map(c => `${c.channel_id.padEnd(26)} ${c.channel_type.padEnd(6)} ${c.is_system ? 'system' : 'user'}   ${c.channel_name}`).join('\n')
    : 'No mounted channels.';
  await safeSend(ctx.channelId, terminal(`${ICON.docker} Mounted channel volumes`, `CHANNEL ID                 TYPE   CLASS    NAME\n${body}`));
}
