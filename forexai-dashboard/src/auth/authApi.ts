import { API_BASE_URL } from "../config/api";
import {
  saveAuthSession,
  clearAuthSession,
  type AuthSession,
} from "./authStorage";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthenticationResponse {
  user_id: string;
  email: string;
  display_name: string;
  token: string;
}

export async function login(
  request: LoginRequest
): Promise<AuthSession> {
  const response = await fetch(
    `${API_BASE_URL}/api/Auth/login`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      `Login failed: ${response.status} ${errorText}`
    );
  }

  const data =
    (await response.json()) as AuthenticationResponse;

  if (!data.token) {
    throw new Error(
      "Login succeeded but no authentication token was returned."
    );
  }

  const session: AuthSession = {
    userId: data.user_id,
    email: data.email,
    displayName: data.display_name,
    token: data.token,
  };

  saveAuthSession(session);

  return session;
}

export function logout(): void {
  clearAuthSession();
}