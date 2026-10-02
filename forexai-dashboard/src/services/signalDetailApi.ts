import type {
  SignalHistory,
} from "../types/signal";

import { API_BASE_URL } from "../config/api";
import { authenticatedFetch } from "../auth/authenticatedFetch";

export async function getSignalDetail(
  signalId: string
): Promise<SignalHistory> {
  const response =
    await authenticatedFetch(
      `${API_BASE_URL}/api/Signals/${signalId}`
    );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      `Signal detail request failed: ${response.status} ${errorText}`
    );
  }

  return response.json();
}