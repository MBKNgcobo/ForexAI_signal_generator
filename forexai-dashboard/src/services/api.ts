import type {
  AnalysisWithSignalResult,
} from "../types/analysis";

import { API_BASE_URL } from "../config/api";
import { authenticatedFetch } from "../auth/authenticatedFetch";

export async function analyzeMarket(
  forexPairId: string,
  symbol: string,
  timeframe: string
): Promise<AnalysisWithSignalResult> {
  const response =
    await authenticatedFetch(
      `${API_BASE_URL}/api/Analysis`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          forex_pair_id: forexPairId,
          symbol,
          timeframe,
        }),
      }
    );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      `Analysis request failed: ${response.status} ${errorText}`
    );
  }

  return response.json();
}