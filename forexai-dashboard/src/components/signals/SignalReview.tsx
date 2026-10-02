import { useState } from "react";
import {
  acceptSignal,
  rejectSignal,
} from "../../services/signalApi";

interface Signal {
  signalId: string;
  direction: string;
  confidence: number;
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  riskReward: number;
  timeframe: string;
  status: string;
  reasoning: string;
}

interface SignalReviewProps {
  signal: Signal;
  onStatusChange: (status: string) => void;
}

function SignalReview({
  signal,
  onStatusChange,
}: SignalReviewProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAccept() {
    setLoading(true);
    setError(null);

    try {
      await acceptSignal(signal.signalId);

      onStatusChange("Accepted");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to accept signal."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleReject() {
    setLoading(true);
    setError(null);

    try {
      await rejectSignal(signal.signalId);

      onStatusChange("Rejected");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to reject signal."
      );
    } finally {
      setLoading(false);
    }
  }

  const isUnderReview =
    signal?.status === "UnderReview";

  return (
    <section className="signal-card">
      <h2>Human Review</h2>

      <div className="signal-grid">

        <div>
          <span>Signal ID</span>
          <strong>{signal.signalId}</strong>
        </div>

        <div>
          <span>Direction</span>
          <strong>{signal.direction}</strong>
        </div>

        <div>
          <span>Confidence</span>
          <strong>
            {(signal.confidence * 100).toFixed(0)}%
          </strong>
        </div>

        <div>
          <span>Status</span>
          <strong>{signal.status}</strong>
        </div>

        <div>
          <span>Entry</span>
          <strong>
            {signal.entryPrice.toFixed(5)}
          </strong>
        </div>

        <div>
          <span>Stop Loss</span>
          <strong>
            {signal.stopLoss.toFixed(5)}
          </strong>
        </div>

        <div>
          <span>Take Profit</span>
          <strong>
            {signal.takeProfit.toFixed(5)}
          </strong>
        </div>

        <div>
          <span>Risk / Reward</span>
          <strong>
            {signal.riskReward}
          </strong>
        </div>

      </div>

      <div className="signal-reasoning">
        <h3>Reasoning</h3>
        <p>{signal.reasoning}</p>
      </div>

      {error && (
        <div className="error-card">
          <h3>Action failed</h3>
          <p>{error}</p>
        </div>
      )}

      {isUnderReview && (
        <div className="signal-actions">

          <button
    disabled={!isUnderReview || loading}
    onClick={handleAccept}
>
    {loading ? "Accepting..." : "Accept Signal"}
</button>

<button
    disabled={!isUnderReview || loading}
    onClick={handleReject}
>
    {loading ? "Rejecting..." : "Reject Signal"}
</button>

        </div>
      )}

      {!isUnderReview && (
        <p>
          This signal has already been reviewed.
        </p>
      )}
    </section>
  );
}

export default SignalReview;