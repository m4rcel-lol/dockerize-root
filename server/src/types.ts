export type ContainerStatus = 'up' | 'down' | 'suspended' | 'deleted';
export type ContainerVisibility = 'private' | 'public';
export type ContainerChannelType = 'text' | 'voice';

export interface RuntimeConfig {
  commandPrefix: string;
  maxChannelsPerContainer: number;
  defaultContainerVisibility: ContainerVisibility;
  commandChannelId?: string;
  staffRoleId?: string;
}

export interface CommandContext {
  channelId: string;
  userId: string;
  memberNickname: string;
  rawContent: string;
  args: string[];
  config: RuntimeConfig;
  isStaff: boolean;
}

export interface ContainerRecord {
  id: number;
  owner_id: string;
  owner_name: string;
  container_name: string;
  container_role_id: string | null;
  channel_group_id: string | null;
  terminal_channel_id: string | null;
  logs_channel_id: string | null;
  general_channel_id: string | null;
  voice_channel_id: string | null;
  status: ContainerStatus;
  visibility: ContainerVisibility;
  inspection_active: number;
  suspended_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContainerChannelRecord {
  id: number;
  owner_id: string;
  channel_id: string;
  channel_name: string;
  channel_type: ContainerChannelType;
  is_system: number;
  created_at: string;
}
