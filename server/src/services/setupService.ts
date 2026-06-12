import { saveSettings } from '../database';
import { CommandContext } from '../types';
import { ICON, safeSend, terminal } from '../messages';
import { extractId } from '../utils/sanitize';

export async function handleSetup(ctx: CommandContext): Promise<void> {
  if (!ctx.isStaff) {
    await safeSend(ctx.channelId, terminal(`${ICON.failure} Setup denied`, 'Error: staff permissions required'));
    return;
  }
  const commandChannelArg = ctx.args.find(a => a.startsWith('channel=') || a.startsWith('commandChannel='));
  const staffArg = ctx.args.find(a => a.startsWith('staff=') || a.startsWith('staffRole='));
  const commandChannelId = extractId(commandChannelArg?.split('=')[1]) ?? ctx.channelId;
  const staffRoleId = extractId(staffArg?.split('=')[1]) ?? ctx.config.staffRoleId;
  await saveSettings(commandChannelId, staffRoleId);
  ctx.config.commandChannelId = commandChannelId;
  ctx.config.staffRoleId = staffRoleId;
  await safeSend(ctx.channelId, terminal(`${ICON.success} Dockerize daemon initialized`, `$ dockerize setup --root\n[+] Command channel attached\n[+] Staff role linked\n[+] Container mode: user-isolated\n[+] Status: online`, `Command Channel: \`${commandChannelId}\`\nStaff Role: \`${staffRoleId ?? 'not set'}\``));
}
