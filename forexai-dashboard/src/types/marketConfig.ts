export interface ForexPairOption {
  symbol: string;
  label: string;
}

export const FOREX_PAIRS: ForexPairOption[] = [
  {
    symbol: "EURUSD",
    label: "EUR/USD",
  },
  {
    symbol: "GBPUSD",
    label: "GBP/USD",
  },
  {
    symbol: "USDJPY",
    label: "USD/JPY",
  },
  {
    symbol: "AUDUSD",
    label: "AUD/USD",
  },
];

export const TIMEFRAMES = [
  {
    value: "OneMinute",
    label: "1 Minute",
  },
  {
    value: "FiveMinutes",
    label: "5 Minutes",
  },
  {
    value: "FifteenMinutes",
    label: "15 Minutes",
  },
  {
    value: "OneHour",
    label: "1 Hour",
  },
  {
    value: "FourHours",
    label: "4 Hours",
  },
  {
    value: "OneDay",
    label: "1 Day",
  },
] as const;

export const CANDLE_LIMITS = [
  50,
  100,
  200,
  500,
];