import type { MarketDataResponse } from "../types/market";

import { API_BASE_URL } from "../config/api";

export async function getMarketData(
  symbol: string,
  timeframe: string,
  limit: number = 100
): Promise<MarketDataResponse> {
  const params = new URLSearchParams({
    timeframe,
    limit: limit.toString(),
  });

  const response = await fetch(
    `${API_BASE_URL}/api/MarketData/${symbol}?${params.toString()}`
  );

  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(
      `Market data request failed: ${response.status} ${errorText}`
    );
  }

  return response.json();
}