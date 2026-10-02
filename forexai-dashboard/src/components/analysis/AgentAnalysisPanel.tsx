interface AgentAnalysis {
  direction?: string;
  confidence?: number;
  summary?: string;

  [key: string]: unknown;
}

interface AgentAnalysisPanelProps {
  title: string;
  analysis: AgentAnalysis;
}

function AgentAnalysisPanel({
  title,
  analysis,
}: AgentAnalysisPanelProps) {

  const direction =
    String(
      analysis?.direction ?? "NO TRADE"
    ).toUpperCase();

  const confidence =
    typeof analysis?.confidence === "number"
      ? analysis.confidence
      : 0;

  const percentage =
    Math.max(
      0,
      Math.min(
        100,
        confidence * 100
      )
    );

  const summary =
    String(
      analysis?.summary ??
      "No analysis summary available."
    );

  const directionClass =
    direction === "BUY"
      ? "agent-direction agent-direction--buy"
      : direction === "SELL"
        ? "agent-direction agent-direction--sell"
        : "agent-direction agent-direction--neutral";


  return (
    <article className="agent-card">

      {/* ==================================================
          HEADER
          ================================================== */}

      <div className="agent-card-header">

        <div>

          <span className="agent-card-label">
            SPECIALIST AGENT
          </span>

          <h3>
            {title}
          </h3>

        </div>

        <span className="agent-status-dot" />

      </div>


      {/* ==================================================
          SIGNAL
          ================================================== */}

      <div className="agent-signal-row">

        <span className={directionClass}>
          {direction}
        </span>

        <div className="agent-confidence">

          <span>
            Confidence
          </span>

          <strong>
            {percentage.toFixed(0)}%
          </strong>

        </div>

      </div>


      {/* ==================================================
          CONFIDENCE BAR
          ================================================== */}

      <div className="confidence-track">

        <div
          className={
            direction === "BUY"
              ? "confidence-fill confidence-fill--buy"
              : direction === "SELL"
                ? "confidence-fill confidence-fill--sell"
                : "confidence-fill confidence-fill--neutral"
          }
          style={{
            width: `${percentage}%`,
          }}
        />

      </div>


      {/* ==================================================
          SUMMARY
          ================================================== */}

      <div className="agent-summary">

        <span>
          Assessment
        </span>

        <p>
          {summary}
        </p>

      </div>


      {/* ==================================================
          FOOTER
          ================================================== */}

      <div className="agent-card-footer">

        <span>
          {title} model
        </span>

        <span className="agent-footer-arrow">
          →
        </span>

      </div>

    </article>
  );
}

export default AgentAnalysisPanel;