import 'dotenv/config';
import { RootBotStartState } from '@rootsdk/server-bot';
import { RuntimeConfig } from './types';

function asString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function asNumber(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function asVisibility(value: unknown): 'private' | 'public' {
  return value === 'public' ? 'public' : 'private';
}

export function loadRuntimeConfig(state?: RootBotStartState): RuntimeConfig {
  const settings: Record<string, unknown> = (state as any)?.settings ?? (state as any)?.globalSettings ?? {};
  return {
    commandPrefix: asString(settings.commandPrefix) ?? process.env.COMMAND_PREFIX ?? 'dkz',
    maxChannelsPerContainer: Math.max(4, asNumber(settings.maxChannelsPerContainer ?? process.env.MAX_CHANNELS_PER_CONTAINER, 10)),
    defaultContainerVisibility: asVisibility(settings.defaultContainerVisibility ?? process.env.DEFAULT_CONTAINER_VISIBILITY),
    commandChannelId: asString(settings.commandChannelId) ?? asString(process.env.COMMAND_CHANNEL_ID),
    staffRoleId: asString(settings.staffRoleId) ?? asString(process.env.STAFF_ROLE_ID),
  };
}
