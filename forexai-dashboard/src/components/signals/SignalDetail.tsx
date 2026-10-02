import { useEffect, useState } from "react";

import {
  getSignalDetail,
} from "../../services/signalDetailApi";

import type {
  SignalHistory,
} from "../../types/signal";

import {
  getSignalAudit,
  type SignalAuditEvent,
} from "../../services/signalAuditApi";

interface SignalDetailProps {
  signalId: string;
  onBack: () => void;
}

function SignalDetail({
  signalId,
  onBack,
}: SignalDetailProps) {
  const [signal, setSignal] =
    useState<SignalHistory | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

 const [auditEvents, setAuditEvents] =
  useState<SignalAuditEvent[]>([]);

const [auditLoading, setAuditLoading] =
  useState(true);

const [auditError, setAuditError] =
  useState<string | null>(null);

  useEffect(() => {
  async function loadSignal() {
    setLoading(true);
    setError(null);

    try {
      const data =
        await getSignalDetail(signalId);

      setSignal(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load signal."
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadAudit() {
    setAuditLoading(true);
    setAuditError(null);

    try {
      const events =
        await getSignalAudit(signalId);

      setAuditEvents(events);
    } catch (err) {
      setAuditError(
        err instanceof Error
          ? err.message
          : "Unable to load audit trail."
      );
    } finally {
      setAuditLoading(false);
    }
  }

  loadSignal();
  loadAudit();
}, [signalId]);

  if (loading) {
    return (
      <section className="signal-card">
        <p>Loading signal...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="error-card">
        <h2>Signal Error</h2>
        <p>{error}</p>

        <button
          type="button"
          onClick={onBack}
        >
          Back
        </button>
      </section>
    );
  }

  if (!signal) {
    return null;
  }

  return (
    <section className="signal-detail-card">
      <button
        type="button"
        onClick={onBack}
      >
        ← Back to History
      </button>

      <div className="signal-detail-header">
        <div>
          <h2>
            {signal.direction}
          </h2>

          <p>
            {signal.timeframe}
          </p>
        </div>

        <span className="signal-status">
          {signal.status}
        </span>
      </div>

      <div className="signal-detail-grid">
        <div>
          <span>Confidence</span>
          <strong>
            {(signal.confidence * 100).toFixed(0)}%
          </strong>
        </div>

        <div>
          <span>Entry</span>
          <strong>
            {signal.entry_price.toFixed(5)}
          </strong>
        </div>

        <div>
          <span>Stop Loss</span>
          <strong>
            {signal.stop_loss.toFixed(5)}
          </strong>
        </div>

        <div>
          <span>Take Profit</span>
          <strong>
            {signal.take_profit.toFixed(5)}
          </strong>
        </div>

        <div>
          <span>Risk / Reward</span>
          <strong>
            {signal.risk_reward}
          </strong>
        </div>

        <div>
          <span>Created</span>
          <strong>
            {new Date(
              signal.created_at
            ).toLocaleString()}
          </strong>
        </div>
      </div>

      <div className="signal-reasoning">
        <h3>Reasoning</h3>
        <p>
          {signal.reasoning}
        </p>
      </div>

      <div className="audit-card">
  <h3>Audit Trail</h3>

  {auditLoading && (
    <p>Loading audit trail...</p>
  )}

  {auditError && (
    <p>{auditError}</p>
  )}

  {!auditLoading &&
    !auditError &&
    auditEvents.length === 0 && (
      <p>No audit events recorded.</p>
    )}

  {!auditLoading &&
    !auditError &&
    auditEvents.length > 0 &&
    auditEvents.map((event) => (
      <div
        key={event.id}
        className="audit-item"
      >
        <strong>
          {event.event_type}
        </strong>

        <span>
          {new Date(
            event.created_at
          ).toLocaleString()}
        </span>

        {event.reason && (
          <p>{event.reason}</p>
        )}
      </div>
    ))}

      <div className="audit-item">
          <strong>
            {signal.status === "UnderReview"
              ? "Under Review"
              : "Reviewed"}
          </strong>

          <span>
            Current signal lifecycle state
          </span>
        </div>
      </div>
    </section>
  );
}

export default SignalDetail;