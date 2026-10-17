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
    const out: Record<string, string> = {};
    if (this.body && typeof this.body === 'object') {
      for (const [key, value] of Object.entries(this.body)) {
        if (key === 'detail') continue;
        out[key] = Array.isArray(value) ? String(value[0]) : String(value);
      }
    }
    return out;
  }
}

function messageFrom(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>;
    if (typeof b.detail === 'string') return b.detail;
    if (Array.isArray(b.non_field_errors)) return String(b.non_field_errors[0]);
    const first = Object.values(b)[0];
    if (Array.isArray(first) && first.length) return String(first[0]);
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