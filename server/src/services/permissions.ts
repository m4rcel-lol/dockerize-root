import { addGroupRule, allowBasic, allowManager, clearGroupRules, everyoneRoleId, publicOverlay } from '../api/rootCommunity';

export async function applyPrivate(groupId: string, containerRoleId: string, ownerId: string, staffRoleId?: string): Promise<void> {
  await clearGroupRules(groupId);
  await addGroupRule(groupId, containerRoleId, allowBasic);
  await addGroupRule(groupId, ownerId, allowManager);
  if (staffRoleId) await addGroupRule(groupId, staffRoleId, allowManager);
}

export async function applyPublic(groupId: string, containerRoleId: string, ownerId: string, staffRoleId?: string): Promise<void> {
  await clearGroupRules(groupId);
  await addGroupRule(groupId, everyoneRoleId(), publicOverlay);
  await addGroupRule(groupId, containerRoleId, allowBasic);
  await addGroupRule(groupId, ownerId, allowManager);
  if (staffRoleId) await addGroupRule(groupId, staffRoleId, allowManager);
}

export async function applyDown(groupId: string, staffRoleId?: string): Promise<void> {
  await clearGroupRules(groupId);
  if (staffRoleId) await addGroupRule(groupId, staffRoleId, allowManager);
}

export async function applySuspended(groupId: string, staffRoleId?: string): Promise<void> {
  await clearGroupRules(groupId);
  if (staffRoleId) await addGroupRule(groupId, staffRoleId, allowManager);
}
