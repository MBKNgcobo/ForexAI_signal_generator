export interface SignalHistory {
  signal_id: string;
  direction: string;
  confidence: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  risk_reward: number;
  timeframe: string;
  status: string;
  reasoning: string;
  created_at: string;
}
export interface PagedSignalHistory {
  items: SignalHistory[];
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}