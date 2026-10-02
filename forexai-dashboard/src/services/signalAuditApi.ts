export interface SignalAuditEvent {
  id: string;
  signal_id: string;
  event_type: string;
  reason: string | null;
  created_at: string;
}

import { API_BASE_URL } from "../config/api";
import { authenticatedFetch } from "../auth/authenticatedFetch";

export async function getSignalAudit(
  signalId: string
): Promise<SignalAuditEvent[]> {
  if (!signalId) {
    throw new Error(
      "Signal ID is required."
    );
  }

  const response =
    await authenticatedFetch(
      `${API_BASE_URL}/api/Signals/${signalId}/audit`
    );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      `Signal audit request failed: ${response.status} ${errorText}`
    );
  }

  return response.json();
}