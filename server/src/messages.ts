import { rootServer, ChannelMessageCreateRequest } from '@rootsdk/server-bot';

export const ICON = {
  docker: '🐳',
  success: '✅',
  failure: '❌',
  warning: '⚠️',
};

export function terminal(title: string, body: string, details?: string): string {
  return [
    `**${title}**`,
    '```console',
    body.trim(),
    '```',
    details?.trim() || '',
    '_Dockerize Runtime • container-isolated Root community environment_',
  ].filter(Boolean).join('\n');
}

export async function send(channelId: string, content: string): Promise<void> {
  const request: ChannelMessageCreateRequest = { channelId, content } as any;
  await rootServer.community.channelMessages.create(request);
}

export async function safeSend(channelId: string | null | undefined, content: string): Promise<void> {
  if (!channelId) return;
  try {
    await send(channelId, content);
  } catch (error) {
    console.error('[messages] send failed', error);
  }
}

export async function animate(channelId: string, frames: string[], finalMessage: string, delayMs = 450): Promise<void> {
  // Root Bots currently expose message creation clearly in the public docs. Message editing may change while the SDK is beta,
  // so the Root port keeps animations compact by sending one terminal block containing all frames, then the final result.
  const folded = frames.map((frame, i) => `# frame ${i + 1}\n${frame}`).join('\n\n');
  await safeSend(channelId, terminal(`${ICON.docker} Dockerize terminal animation`, folded));
  await new Promise((resolve) => setTimeout(resolve, delayMs));
  await safeSend(channelId, finalMessage);
}
