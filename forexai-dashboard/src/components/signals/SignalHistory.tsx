import { useEffect, useState } from "react";

import { getSignalHistory } from "../../services/signalHistoryApi";

import type {
  SignalHistory as SignalHistoryItem,
  PagedSignalHistory,
} from "../../types/signal";

import SignalDetail from "./SignalDetail";

const PAGE_SIZE = 10;

function SignalHistory() {
  const [history, setHistory] =
    useState<PagedSignalHistory | null>(null);

  const [page, setPage] =
    useState(1);

  const [status, setStatus] =
    useState("");

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [selectedSignalId, setSelectedSignalId] =
    useState<string | null>(null);

  // Manual retry counter (F-02): setPage(page) with the same value is a
  // React no-op, so the error state's "Try Again" button needs its own
  // dependency to re-trigger the effect.
  const [reloadTick, setReloadTick] =
    useState(0);

  useEffect(() => {
    let stale = false;

    async function loadHistory() {
      setLoading(true);
      setError(null);

      try {
        const data = await getSignalHistory(
          page,
          PAGE_SIZE,
          status || undefined
        );

        if (stale) return;

        setHistory(data);
      } catch (err) {
        console.error(
          "Signal history error:",
          err
        );

        if (stale) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load signal history."
        );
      } finally {
        if (!stale) {
          setLoading(false);
        }
      }
    }

    loadHistory();

    // A newer request (page/status/reload changed) supersedes this one;
    // its late result must not overwrite fresh data.
    return () => {
      stale = true;
    };
  }, [page, status, reloadTick]);

  function handleStatusChange(
    newStatus: string
  ) {
    setPage(1);
    setStatus(newStatus);
  }

  // Show the selected signal instead of the history list
  if (selectedSignalId) {
    return (
      <SignalDetail
        signalId={selectedSignalId}
        onBack={() =>
          setSelectedSignalId(null)
        }
      />
    );
  }

  return (
    <section className="signal-history-card">
      <div className="history-header">
        <div>
          <h2>Signal History</h2>

          {history && (
            <span>
              {history.totalItems} signals
            </span>
          )}
        </div>

        <select
          value={status}
          onChange={(event) =>
            handleStatusChange(
              event.target.value
            )
          }
        >
          <option value="">
            All
          </option>

          <option value="UnderReview">
            Under Review
          </option>

          <option value="Accepted">
            Accepted
          </option>

          <option value="Rejected">
            Rejected
          </option>
        </select>
      </div>

      {loading && (
        <p>
          Loading signal history...
        </p>
      )}

      {error && (
        <section className="error-card">
          <h3>
            Signal History Error
          </h3>

          <p>{error}</p>

          <button
            type="button"
            onClick={() =>
              setReloadTick((tick) => tick + 1)
            }
          >
            Try Again
          </button>
        </section>
      )}

      {!loading &&
        !error &&
        history &&
        history.items.length === 0 && (
          <p>
            No signals found.
          </p>
        )}

      {!loading &&
        !error &&
        history &&
        history.items.length > 0 && (
          <>
            <div className="signal-history-list">
              {history.items.map(
                (signal) => (
                  <HistoryItem
                    key={signal.signal_id}
                    signal={signal}
                    onClick={() =>
                      setSelectedSignalId(
                        signal.signal_id
                      )
                    }
                  />
                )
              )}
            </div>

            <div className="pagination">
              <button
                type="button"
                disabled={
                  page <= 1 ||
                  loading
                }
                onClick={() =>
                  setPage(
                    (current) =>
                      current - 1
                  )
                }
              >
                Previous
              </button>

              <span>
                Page {history.page} of{" "}
                {history.totalPages}
              </span>

              <button
                type="button"
                disabled={
                  page >=
                    history.totalPages ||
                  loading
                }
                onClick={() =>
                  setPage(
                    (current) =>
                      current + 1
                  )
                }
              >
                Next
              </button>
            </div>
          </>
        )}
    </section>
  );
}

function HistoryItem({
  signal,
  onClick,
}: {
  signal: SignalHistoryItem;
  onClick: () => void;
}) {
  return (
    <article
      className="history-item"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (
          event.key === "Enter" ||
          event.key === " "
        ) {
          onClick();
        }
      }}
    >
      <div>
        <strong>
          {signal.direction}
        </strong>

        <span>
          {signal.status}
        </span>
      </div>

      <div>
        <span>
          {signal.timeframe}
        </span>

        <span>
          Confidence:{" "}
          {(
            signal.confidence * 100
          ).toFixed(0)}
          %
        </span>
      </div>

      <div>
        <span>
          Entry:{" "}
          {signal.entry_price.toFixed(
            5
          )}
        </span>

        <span>
          R:R:{" "}
          {signal.risk_reward}
        </span>
      </div>

      <small>
        {new Date(
          signal.created_at
        ).toLocaleString()}
      </small>
    </article>
  );
}

export default SignalHistory;