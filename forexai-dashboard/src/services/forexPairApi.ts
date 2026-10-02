import type { ForexPair } from "../types/forexPair";

import { API_BASE_URL } from "../config/api";

export async function getForexPairs(): Promise<ForexPair[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/ForexPairs`
  );

  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(
      `Forex pair request failed: ${response.status} ${errorText}`
    );
  }

  return response.json();
}