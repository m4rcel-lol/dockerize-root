import { addGroupRule, allowBasic, allowManager, clearGroupRules, denyBasic, publicOverlay } from '../api/rootCommunity';

export async function applyPrivate(groupId: string, ownerId: string, invitedUserIds: string[], staffRoleId?: string): Promise<void> {
  await clearGroupRules(groupId);
  await addGroupRule(groupId, ownerId, allowManager);
  for (const invited of invitedUserIds) await addGroupRule(groupId, invited, allowBasic);
  if (staffRoleId) await addGroupRule(groupId, staffRoleId, allowManager);
}

export async function applyPublic(groupId: string, ownerId: string, invitedUserIds: string[], staffRoleId?: string): Promise<void> {
  await clearGroupRules(groupId);
  // Root's exact @everyone GUID is instance-defined, so public mode grants a permissive group rule only when configured by staff.
  // The owner's/staff permissions remain explicit. If your community exposes an Everyone role GUID, use dkz setup staff=<roleId> and set EVERYONE_ROLE_ID in code/env.
  const everyone = process.env.EVERYONE_ROLE_ID;
  if (everyone) await addGroupRule(groupId, everyone, publicOverlay);
  await addGroupRule(groupId, ownerId, allowManager);
  for (const invited of invitedUserIds) await addGroupRule(groupId, invited, allowBasic);
  if (staffRoleId) await addGroupRule(groupId, staffRoleId, allowManager);
}

export async function applyDown(groupId: string, ownerId: string, invitedUserIds: string[], staffRoleId?: string): Promise<void> {
  await clearGroupRules(groupId);
  await addGroupRule(groupId, ownerId, { ...denyBasic, channelView: true, channelCreateMessage: false, channelConnect: false });
  for (const invited of invitedUserIds) await addGroupRule(groupId, invited, denyBasic);
  if (staffRoleId) await addGroupRule(groupId, staffRoleId, allowManager);
}

export async function applySuspended(groupId: string, ownerId: string, invitedUserIds: string[], staffRoleId?: string): Promise<void> {
  await clearGroupRules(groupId);
  await addGroupRule(groupId, ownerId, denyBasic);
  for (const invited of invitedUserIds) await addGroupRule(groupId, invited, denyBasic);
  if (staffRoleId) await addGroupRule(groupId, staffRoleId, allowManager);
}
