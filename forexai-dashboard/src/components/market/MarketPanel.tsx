import type { ForexPair } from "../../types/forexPair";
import type { Timeframe } from "../../types/timeframe";

interface MarketPanelProps {
  pairs: ForexPair[];
  symbol: string;
  timeframe: string;
  limit: number;
  loading: boolean;
  timeframes: Timeframe[];

  onLimitChange: (limit: number) => void;
  onAnalyze: () => void;
  onSymbolChange: (symbol: string) => void;
  onTimeframeChange: (timeframe: string) => void;
}

function MarketPanel({
  pairs,
  symbol,
  timeframe,
  limit,
  loading,
  timeframes,
  onLimitChange,
  onAnalyze,
  onSymbolChange,
  onTimeframeChange,
}: MarketPanelProps) {
  return (
    <section className="market-panel">

      <div className="market-panel-header">

        <div>

          <span className="panel-eyebrow">
            MARKET WORKSPACE
          </span>

          <h2>
            Configure analysis
          </h2>

          <p>
            Select your market, timeframe and data window.
          </p>

        </div>

        <div className="market-panel-status">

          <span className="status-dot" />

          <span>
            Market feed active
          </span>

        </div>

      </div>


      <div className="market-controls-row">

        {/* ==================================================
            FOREX PAIR
            ================================================== */}

        <div className="market-control">

          <label htmlFor="forex-pair">
            Forex pair
          </label>

          <div className="select-shell">

            <select
              id="forex-pair"
              value={symbol}
              onChange={(event) =>
                onSymbolChange(
                  event.target.value
                )
              }
            >
              {pairs.map((pair) => (
                <option
                  key={pair.id}
                  value={pair.symbol}
                >
                  {pair.symbol}
                </option>
              ))}
            </select>

            <span className="select-chevron">
              ▾
            </span>

          </div>

        </div>


        {/* ==================================================
            TIMEFRAME
            ================================================== */}

        <div className="market-control">

          <label htmlFor="timeframe">
            Timeframe
          </label>

          <div className="select-shell">

            <select
              id="timeframe"
              value={timeframe}
              onChange={(event) =>
                onTimeframeChange(
                  event.target.value
                )
              }
            >
              {timeframes.map((option) => (
                <option
                  key={option.value}
                  value={option.value}
                >
                  {formatTimeframe(
                    option.value
                  )}
                </option>
              ))}
            </select>

            <span className="select-chevron">
              ▾
            </span>

          </div>

        </div>


        {/* ==================================================
            CANDLE COUNT
            ================================================== */}

        <div className="market-control market-control--small">

          <label htmlFor="candle-limit">
            Candles
          </label>

          <div className="select-shell">

            <select
              id="candle-limit"
              value={limit}
              onChange={(event) =>
                onLimitChange(
                  Number(
                    event.target.value
                  )
                )
              }
            >
              <option value={50}>
                50
              </option>

              <option value={100}>
                100
              </option>

              <option value={200}>
                200
              </option>

              <option value={300}>
                300
              </option>

            </select>

            <span className="select-chevron">
              ▾
            </span>

          </div>

        </div>


        {/* ==================================================
            ANALYSE BUTTON
            ================================================== */}

        <div className="market-action">

          <label>
            &nbsp;
          </label>

          <button
            type="button"
            className="analyze-button"
            onClick={onAnalyze}
            disabled={loading || !symbol || !timeframe}
          >

            {loading ? (
              <>
                <span className="button-spinner" />
                Analysing...
              </>
            ) : (
              <>
                <span>
                  ✦
                </span>

                Run AI analysis
              </>
            )}

          </button>

        </div>

      </div>


      <div className="market-panel-footer">

        <span>
          Selected market
        </span>

        <strong>
          {symbol}
        </strong>

        <span className="footer-separator">
          /
        </span>

        <span>
          {formatTimeframe(timeframe)}
        </span>

        <span className="footer-separator">
          /
        </span>

        <span>
          {limit} candles
        </span>

      </div>

    </section>
  );
}


function formatTimeframe(
  value: string
): string {
  const labels: Record<string, string> = {
    OneMinute: "1 Minute",
    FiveMinutes: "5 Minutes",
    FifteenMinutes: "15 Minutes",
    ThirtyMinutes: "30 Minutes",
    OneHour: "1 Hour",
    FourHours: "4 Hours",
    OneDay: "1 Day",
  };

  return labels[value] ?? value;
}


export default MarketPanel;