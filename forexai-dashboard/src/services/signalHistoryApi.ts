import type {
  PagedSignalHistory,
} from "../types/signal";

import { API_BASE_URL } from "../config/api";
import { authenticatedFetch } from "../auth/authenticatedFetch";

export async function getSignalHistory(
  page: number = 1,
  pageSize: number = 10,
  status?: string
): Promise<PagedSignalHistory> {
  const params =
    new URLSearchParams({
      page: page.toString(),
      pageSize: pageSize.toString(),
    });

  if (status) {
    params.set("status", status);
  }

  const response =
    await authenticatedFetch(
      `${API_BASE_URL}/api/Signals?${params.toString()}`
    );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      `Signal history request failed: ${response.status} ${errorText}`
    );
  }

  return response.json();
}