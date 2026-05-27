import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { decodeToken, getStoredUser, getStoredToken, clearToken } from '../lib/auth';

function makeJwt(payload: object): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fakesig`;
}

describe('decodeToken', () => {
  it('returns payload for a valid JWT', () => {
    const token = makeJwt({ sub: 'manager', role: 'Manager', company_id: 1, user_id: 2, exp: 9999999999 });
    const result = decodeToken(token);
    expect(result?.sub).toBe('manager');
    expect(result?.role).toBe('Manager');
    expect(result?.company_id).toBe(1);
  });

  it('returns null for a non-JWT string', () => {
    expect(decodeToken('notavalidtoken')).toBeNull();
  });

  it('returns null for an empty string', () => {
    expect(decodeToken('')).toBeNull();
  });

  it('returns null when payload is not valid JSON', () => {
    expect(decodeToken('header.!!!.sig')).toBeNull();
  });
});

describe('getStoredToken / clearToken / getStoredUser', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('returns null when no token is stored', () => {
    expect(getStoredToken()).toBeNull();
    expect(getStoredUser()).toBeNull();
  });

  it('returns token after storing it', () => {
    const token = makeJwt({ sub: 'manager', role: 'Manager', company_id: 1, user_id: 2, exp: 9999999999 });
    localStorage.setItem('token', token);
    expect(getStoredToken()).toBe(token);
    expect(getStoredUser()?.sub).toBe('manager');
  });

  it('returns null after clearToken', () => {
    const token = makeJwt({ sub: 'manager', role: 'Manager', company_id: 1, user_id: 2, exp: 9999999999 });
    localStorage.setItem('token', token);
    clearToken();
    expect(getStoredToken()).toBeNull();
  });
});
