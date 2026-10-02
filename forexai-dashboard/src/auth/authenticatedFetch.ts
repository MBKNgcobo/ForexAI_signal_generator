import {
  clearAuthSession,
  getAuthToken,
} from "./authStorage";

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {}
): Promise<Response> {
  const token = getAuthToken();

  if (!token) {
    throw new Error(
      "Authentication is required. Please log in."
    );
  }

  const headers = new Headers(
    init.headers
  );

  headers.set(
    "Authorization",
    `Bearer ${token}`
  );

  if (
    init.body &&
    !headers.has("Content-Type")
  ) {
    headers.set(
      "Content-Type",
      "application/json"
    );
  }

  const response = await fetch(
    input,
    {
      ...init,
      headers,
    }
  );

  if (response.status === 401) {
    clearAuthSession();

    throw new Error(
      "Your session has expired. Please log in again."
    );
  }

  return response;
}