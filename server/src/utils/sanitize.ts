export function sanitizeName(input: string, fallback = 'container'): string {
  const normalized = input
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9-_ ]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 38);
  return normalized || fallback;
}

export function containerDisplayName(ownerName: string, requested?: string): string {
  const base = sanitizeName(requested || ownerName, 'user');
  return `container-${base}`;
}

export function extractId(token?: string): string | undefined {
  if (!token) return undefined;
  const match = token.match(/[a-zA-Z0-9_-]{6,}/g);
  return match ? match[match.length - 1] : undefined;
}

export function nowIso(): string {
  return new Date().toISOString();
}
