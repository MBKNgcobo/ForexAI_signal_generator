import { API_BASE_URL } from "../config/api";
import { authenticatedFetch } from "../auth/authenticatedFetch";

export async function acceptSignal(
  signalId: string
): Promise<void> {
  const response =
    await authenticatedFetch(
      `${API_BASE_URL}/api/Signals/${signalId}/accept`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      `Failed to accept signal: ${response.status} ${errorText}`
    );
  }
}

export async function rejectSignal(
  signalId: string
): Promise<void> {
  const response =
    await authenticatedFetch(
      `${API_BASE_URL}/api/Signals/${signalId}/reject`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      `Failed to reject signal: ${response.status} ${errorText}`
    );
  }
}