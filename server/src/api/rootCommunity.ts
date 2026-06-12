import { rootServer, ChannelType, WellKnownRootGuids } from '@rootsdk/server-bot';

export type Overlay = Record<string, boolean | undefined>;

export const allowBasic: Overlay = {
  channelView: true,
  channelCreateMessage: true,
  channelCreateMessageReaction: true,
  channelViewMessageHistory: true,
  channelVoiceTalk: true,
};

export const allowManager: Overlay = {
  ...allowBasic,
  channelCreateMessageAttachment: true,
  channelCreateFile: true,
  channelManageFiles: true,
  channelViewFile: true,
};

export const denyBasic: Overlay = {
  channelView: false,
  channelCreateMessage: false,
  channelVoiceTalk: false,
};

export const publicOverlay: Overlay = {
  channelView: true,
  channelCreateMessage: true,
  channelViewMessageHistory: true,
  channelVoiceTalk: true,
};

export function everyoneRoleId(): string {
  return (WellKnownRootGuids as any).CommunityRoles.EveryoneRole;
}

function containerRoleRequest(name: string): any {
  return {
    name,
    colorHex: '#0EA5E9',
    isMentionable: false,
    communityPermission: {
      communityManageCommunity: false,
      communityManageRoles: false,
      communityManageEmojis: false,
      communityManageAuditLog: false,
      communityCreateInvite: false,
      communityManageInvites: false,
      communityCreateBan: false,
      communityManageBans: false,
      communityFullControl: false,
      communityKick: false,
      communityChangeMyNickname: false,
      communityChangeOtherNickname: false,
      communityCreateChannelGroup: false,
      communityManageApps: false,
    },
    channelPermission: {
      channelFullControl: false,
      channelView: true,
      channelUseExternalEmoji: false,
      channelCreateMessage: true,
      channelDeleteMessageOther: false,
      channelManagePinnedMessages: false,
      channelViewMessageHistory: true,
      channelCreateMessageAttachment: false,
      channelCreateMessageMention: false,
      channelCreateMessageReaction: true,
      channelMakeMessagePublic: false,
      channelMoveUserOther: false,
      channelVoiceTalk: true,
      channelVoiceMuteOther: false,
      channelVoiceDeafenOther: false,
      channelVoiceKick: false,
      channelVideoStreamMedia: false,
      channelCreateFile: false,
      channelManageFiles: false,
      channelViewFile: false,
      channelAppKick: false,
    },
  };
}

export async function createContainerRole(name: string): Promise<any> {
  return await rootServer.community.communityRoles.create(containerRoleRequest(name) as any);
}

export async function deleteContainerRole(roleId: string): Promise<void> {
  await rootServer.community.communityRoles.delete({ id: roleId } as any);
}

export async function addRoleToMember(userId: string, roleId: string): Promise<void> {
  await rootServer.community.communityMemberRoles.add({ communityRoleId: roleId, userIds: [userId] } as any);
}

export async function removeRoleFromMember(userId: string, roleId: string): Promise<void> {
  await rootServer.community.communityMemberRoles.remove({ communityRoleId: roleId, userIds: [userId] } as any);
}

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
  await rootServer.community.accessRules.create({ channelOrChannelGroupId: channelGroupId, roleOrMemberId, overlay } as any);
}

export async function clearGroupRules(channelGroupId: string): Promise<void> {
  try {
    const res = await rootServer.community.accessRules.listByChannelOrChannelGroup({ channelOrChannelGroupId: channelGroupId } as any) as any;
    const rules = Array.isArray(res) ? res : (res?.accessRules ?? res?.items ?? []);
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
