export interface AuthSession {
  userId: string;
  email: string;
  displayName: string;
  token: string;
}

const AUTH_STORAGE_KEY = "forexai.auth";

export function getAuthSession(): AuthSession | null {
  const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);

  if (!raw) {
    return null;
  }

  try {
    const session = JSON.parse(raw) as AuthSession;

    if (
      !session.userId ||
      !session.email ||
      !session.displayName ||
      !session.token
    ) {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
      return null;
    }

    return session;
  } catch {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

export function saveAuthSession(
  session: AuthSession
): void {
  sessionStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify(session)
  );
}

export function clearAuthSession(): void {
  sessionStorage.removeItem(AUTH_STORAGE_KEY);
}

export function getAuthToken(): string | null {
  return getAuthSession()?.token ?? null;
}

export function isAuthenticated(): boolean {
  return getAuthToken() !== null;
}