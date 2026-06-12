import { rootServer, ChannelType } from '@rootsdk/server-bot';

export type Overlay = Record<string, boolean | undefined>;

export const allowBasic: Overlay = {
  channelView: true,
  channelCreateMessage: true,
  channelCreateReaction: true,
  channelConnect: true,
  channelReadMessageHistory: true,
};

export const allowManager: Overlay = {
  ...allowBasic,
  channelManage: true,
  channelEdit: true,
  channelDelete: true,
  channelCreateFile: true,
};

export const denyBasic: Overlay = {
  channelView: false,
  channelCreateMessage: false,
  channelConnect: false,
};

export const publicOverlay: Overlay = {
  channelView: true,
  channelCreateMessage: true,
  channelConnect: true,
  channelReadMessageHistory: true,
};

export async function createChannelGroup(name: string, accessRuleCreates: Array<{ roleOrMemberId: string; overlay: Overlay }> = []): Promise<any> {
  return await rootServer.community.channelGroups.create({ name, accessRuleCreates } as any);
}

export async function editChannelGroup(channelGroupId: string, name: string): Promise<void> {
  await rootServer.community.channelGroups.edit({ channelGroupId, name } as any);
}

export async function deleteChannelGroup(channelGroupId: string): Promise<void> {
  await rootServer.community.channelGroups.delete({ channelGroupId } as any);
}

export async function createChannel(channelGroupId: string, name: string, type: 'text' | 'voice'): Promise<any> {
  return await rootServer.community.channels.create({
    channelGroupId,
    name,
    channelType: type === 'voice' ? ChannelType.Voice : ChannelType.Text,
    useChannelGroupPermission: true,
  } as any);
}

export async function deleteChannel(channelId: string): Promise<void> {
  await rootServer.community.channels.delete({ channelId } as any);
}

export async function addGroupRule(channelGroupId: string, roleOrMemberId: string, overlay: Overlay): Promise<void> {
  await rootServer.community.accessRules.create({ channelGroupId, roleOrMemberId, overlay } as any);
}

export async function clearGroupRules(channelGroupId: string): Promise<void> {
  try {
    const rules = await rootServer.community.accessRules.listByChannelOrChannelGroup({ channelGroupId } as any) as any[];
    for (const rule of rules ?? []) {
      const accessRuleId = rule.accessRuleId ?? rule.id;
      if (accessRuleId) await rootServer.community.accessRules.delete({ accessRuleId } as any);
    }
  } catch (error) {
    console.warn('[root-api] could not clear access rules; continuing', error);
  }
}

export async function getMember(userId: string): Promise<any | undefined> {
  try {
    return await rootServer.community.communityMembers.get({ userId } as any);
  } catch {
    return undefined;
  }
}

export async function getCurrentCommunity(): Promise<any | undefined> {
  try {
    return await rootServer.community.communities.get();
  } catch {
    return undefined;
  }
}
