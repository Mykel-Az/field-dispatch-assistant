// One place that knows how to talk to the Django API with a session cookie.
//
// - Same-origin base URL (/api): the browser sends the session cookie itself.
//   In dev Vite proxies /api; in prod the static site rewrites /api to Django.
// - Unsafe methods carry X-CSRFToken. The cookie is read fresh on every call
//   because login/register rotate it.
// - 401 means "session expired": tell the app (once) so it can send the
//   user to /login while keeping the page they were on. Login failures are
//   400, so they never trigger this.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

function flatten(
  value: unknown,
  out: Record<string, string> = {},
  key = '',
): Record<string, string> {
  if (Array.isArray(value)) {
    const first = value[0];
    if (first !== null && typeof first === 'object') flatten(first, out, key);
    else if (key && first !== undefined && !(key in out)) out[key] = String(first);
  } else if (value !== null && typeof value === 'object') {
    for (const [k, v] of Object.entries(value)) flatten(v, out, k);
  } else if (value !== null && value !== undefined && key && !(key in out)) {
    out[key] = String(value);
  }
  return out;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(messageFrom(body, status));
    this.status = status;
    this.body = body;
  }

  /** Field errors as { field: "first message" }, for forms. */
  get fieldErrors(): Record<string, string> {
    const out = flatten(this.body);
    delete out.detail;
    return out;
  }
}

function messageFrom(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>;
    if (typeof b.detail === 'string') return b.detail;
    const first = Object.values(flatten(body))[0];
    if (first) return first;
  }
  return `Request failed (${status})`;
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

function readCookie(name: string): string | null {
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split('=')[1]) : null;
}

async function ensureCsrfCookie(): Promise<string> {
  let token = readCookie('csrftoken');
  if (!token) {
    await fetch(`${BASE_URL}/auth/csrf/`, { credentials: 'same-origin' });
    token = readCookie('csrftoken');
  }
  if (!token) throw new Error('Could not obtain a CSRF token.');
  return token;
}

export async function request<T>(
  method: 'GET' | 'POST' | 'PATCH',
  path: string,
  body?: unknown,
  opts: { skipUnauthorizedHandler?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (method !== 'GET') {
    headers['X-CSRFToken'] = await ensureCsrfCookie();
  }
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = null; // e.g. an HTML page from a misconfigured proxy
  }

  if (!response.ok) {
    if (response.status === 401 && !opts.skipUnauthorizedHandler) {
      onUnauthorized?.();
    }
    throw new ApiError(response.status, parsed);
  }
  if (parsed === null) {
    throw new Error(
      'The API returned a non-JSON response. Check the /api rewrite/proxy.',
    );
  }
  return parsed as T;
}

export const get = <T>(path: string, opts?: { skipUnauthorizedHandler?: boolean }) =>
  request<T>('GET', path, undefined, opts);
export const post = <T>(path: string, body?: unknown) =>
  request<T>('POST', path, body ?? {});
export const patch = <T>(path: string, body: unknown) =>
  request<T>('PATCH', path, body);