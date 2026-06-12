import { rootServer } from '@rootsdk/server-bot';
import sqlite3 from 'sqlite3';
import { ContainerChannelRecord, ContainerRecord, ContainerVisibility } from './types';
import { nowIso } from './utils/sanitize';

sqlite3.verbose();
let db: sqlite3.Database;

function run(sql: string, params: unknown[] = []): Promise<void> {
  return new Promise((resolve, reject) => {
    db.run(sql, params, (err) => err ? reject(err) : resolve());
  });
}

function get<T>(sql: string, params: unknown[] = []): Promise<T | undefined> {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => err ? reject(err) : resolve(row as T | undefined));
  });
}

function all<T>(sql: string, params: unknown[] = []): Promise<T[]> {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => err ? reject(err) : resolve(rows as T[]));
  });
}

export async function initDatabase(): Promise<void> {
  const filename = rootServer.dataStore.config.sqlite3?.filename ?? './dockerize-root.sqlite3';
  db = new sqlite3.Database(filename);
  await run('PRAGMA journal_mode=WAL');
  await run('PRAGMA foreign_keys=ON');
  await run(`CREATE TABLE IF NOT EXISTS guild_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    command_channel_id TEXT,
    staff_role_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  )`);
  await run(`CREATE TABLE IF NOT EXISTS containers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL UNIQUE,
    owner_name TEXT NOT NULL,
    container_name TEXT NOT NULL,
    channel_group_id TEXT,
    terminal_channel_id TEXT,
    logs_channel_id TEXT,
    general_channel_id TEXT,
    voice_channel_id TEXT,
    status TEXT NOT NULL,
    visibility TEXT NOT NULL,
    inspection_active INTEGER DEFAULT 0,
    suspended_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  )`);
  await run(`CREATE TABLE IF NOT EXISTS container_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    channel_id TEXT NOT NULL UNIQUE,
    channel_name TEXT NOT NULL,
    channel_type TEXT NOT NULL,
    is_system INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
  )`);
  await run(`CREATE TABLE IF NOT EXISTS container_invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    invited_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(owner_id, invited_user_id)
  )`);
}

export async function closeDatabase(): Promise<void> {
  await new Promise<void>((resolve) => db?.close(() => resolve()));
}

export async function saveSettings(commandChannelId?: string, staffRoleId?: string): Promise<void> {
  const now = nowIso();
  await run(`INSERT INTO guild_settings (id, command_channel_id, staff_role_id, created_at, updated_at)
    VALUES (1, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET command_channel_id=excluded.command_channel_id, staff_role_id=excluded.staff_role_id, updated_at=excluded.updated_at`,
    [commandChannelId ?? null, staffRoleId ?? null, now, now]);
}

export async function getSettings(): Promise<{ command_channel_id?: string; staff_role_id?: string } | undefined> {
  return await get('SELECT command_channel_id, staff_role_id FROM guild_settings WHERE id=1');
}

export async function createContainer(rec: Omit<ContainerRecord, 'id'>): Promise<void> {
  await run(`INSERT INTO containers (owner_id, owner_name, container_name, channel_group_id, terminal_channel_id, logs_channel_id, general_channel_id, voice_channel_id, status, visibility, inspection_active, suspended_reason, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [rec.owner_id, rec.owner_name, rec.container_name, rec.channel_group_id, rec.terminal_channel_id, rec.logs_channel_id, rec.general_channel_id, rec.voice_channel_id, rec.status, rec.visibility, rec.inspection_active, rec.suspended_reason, rec.created_at, rec.updated_at]);
}

export async function getContainer(ownerId: string): Promise<ContainerRecord | undefined> {
  return await get<ContainerRecord>('SELECT * FROM containers WHERE owner_id=?', [ownerId]);
}

export async function listContainers(): Promise<ContainerRecord[]> {
  return await all<ContainerRecord>('SELECT * FROM containers WHERE status != ? ORDER BY created_at DESC', ['deleted']);
}

export async function updateContainer(ownerId: string, patch: Partial<ContainerRecord>): Promise<void> {
  const entries = Object.entries(patch).filter(([k]) => k !== 'id' && k !== 'owner_id');
  if (entries.length === 0) return;
  entries.push(['updated_at', nowIso()]);
  const setSql = entries.map(([k]) => `${k}=?`).join(', ');
  await run(`UPDATE containers SET ${setSql} WHERE owner_id=?`, [...entries.map(([, v]) => v), ownerId]);
}

export async function deleteContainerRecord(ownerId: string): Promise<void> {
  await run('DELETE FROM container_invites WHERE owner_id=?', [ownerId]);
  await run('DELETE FROM container_channels WHERE owner_id=?', [ownerId]);
  await run('DELETE FROM containers WHERE owner_id=?', [ownerId]);
}

export async function addChannel(ownerId: string, channelId: string, name: string, type: string, isSystem = false): Promise<void> {
  await run(`INSERT OR REPLACE INTO container_channels (owner_id, channel_id, channel_name, channel_type, is_system, created_at)
    VALUES (?, ?, ?, ?, ?, ?)`, [ownerId, channelId, name, type, isSystem ? 1 : 0, nowIso()]);
}

export async function getChannel(channelId: string): Promise<ContainerChannelRecord | undefined> {
  return await get<ContainerChannelRecord>('SELECT * FROM container_channels WHERE channel_id=?', [channelId]);
}

export async function listChannels(ownerId: string): Promise<ContainerChannelRecord[]> {
  return await all<ContainerChannelRecord>('SELECT * FROM container_channels WHERE owner_id=? ORDER BY is_system DESC, created_at ASC', [ownerId]);
}

export async function removeChannel(channelId: string): Promise<void> {
  await run('DELETE FROM container_channels WHERE channel_id=?', [channelId]);
}

export async function addInvite(ownerId: string, invitedUserId: string): Promise<void> {
  await run('INSERT OR IGNORE INTO container_invites (owner_id, invited_user_id, created_at) VALUES (?, ?, ?)', [ownerId, invitedUserId, nowIso()]);
}

export async function removeInvite(ownerId: string, invitedUserId: string): Promise<void> {
  await run('DELETE FROM container_invites WHERE owner_id=? AND invited_user_id=?', [ownerId, invitedUserId]);
}

export async function listInvites(ownerId: string): Promise<string[]> {
  const rows = await all<{ invited_user_id: string }>('SELECT invited_user_id FROM container_invites WHERE owner_id=? ORDER BY created_at ASC', [ownerId]);
  return rows.map((r) => r.invited_user_id);
}

export async function countChannels(ownerId: string): Promise<number> {
  const row = await get<{ total: number }>('SELECT COUNT(*) as total FROM container_channels WHERE owner_id=?', [ownerId]);
  return row?.total ?? 0;
}

export async function setVisibility(ownerId: string, visibility: ContainerVisibility): Promise<void> {
  await updateContainer(ownerId, { visibility });
}
