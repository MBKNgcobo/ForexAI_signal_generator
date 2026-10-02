import type { Timeframe } from "../types/timeframe";

import { API_BASE_URL } from "../config/api";

export async function getTimeframes(): Promise<Timeframe[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/Timeframes`
  );

  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(
      `Timeframe request failed: ${response.status} ${errorText}`
    );
  }

  return response.json();
}