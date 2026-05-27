interface TokenPayload {
  sub: string;
  user_id: number;
  company_id: number;
  role: string | null;
  exp: number;
}

export function decodeToken(token: string): TokenPayload | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
    return payload as TokenPayload;
  } catch {
    return null;
  }
}

export function getStoredToken(): string | null {
  return localStorage.getItem('token');
}

export function getStoredUser(): TokenPayload | null {
  const token = getStoredToken();
  if (!token) return null;
  return decodeToken(token);
}

export function clearToken(): void {
  localStorage.removeItem('token');
}
