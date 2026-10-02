interface FinalDecision {
  direction?: string;
  confidence?: number;
  reasoning?: string;

  [key: string]: unknown;
}

interface FinalDecisionPanelProps {
  decision: FinalDecision;
}

function FinalDecisionPanel({
  decision,
}: FinalDecisionPanelProps) {

  const direction =
    String(
      decision?.direction ??
      "NO TRADE"
    ).toUpperCase();

  const confidence =
    typeof decision?.confidence === "number"
      ? Math.max(
          0,
          Math.min(
            1,
            decision.confidence
          )
        )
      : 0;

  const percentage =
    confidence * 100;

  const reasoning =
    String(
      decision?.reasoning ??
      "No final decision reasoning available."
    );


  const decisionClass =
    direction === "BUY"
      ? "decision-direction decision-direction--buy"
      : direction === "SELL"
        ? "decision-direction decision-direction--sell"
        : "decision-direction decision-direction--neutral";


  return (
    <article className="decision-card">

      {/* ==================================================
          HEADER
          ================================================== */}

      <div className="decision-card-header">

        <div>

          <span className="panel-eyebrow">
            FOREXAI SYNTHESIS
          </span>

          <h3>
            Final decision
          </h3>

        </div>

        <span className="decision-live">
          AI
        </span>

      </div>


      {/* ==================================================
          MAIN DECISION
          ================================================== */}

      <div className="decision-main">

        <div
          className={decisionClass}
        >
          {direction}
        </div>

        <div className="decision-confidence">

          <span>
            Model confidence
          </span>

          <strong>
            {percentage.toFixed(1)}%
          </strong>

        </div>

      </div>


      {/* ==================================================
          CONFIDENCE METER
          ================================================== */}

      <div className="decision-meter">

        <div className="decision-meter-track">

          <div
            className={
              direction === "BUY"
                ? "decision-meter-fill decision-meter-fill--buy"
                : direction === "SELL"
                  ? "decision-meter-fill decision-meter-fill--sell"
                  : "decision-meter-fill decision-meter-fill--neutral"
            }
            style={{
              width: `${percentage}%`,
            }}
          />

        </div>

        <div className="decision-meter-labels">

          <span>
            0%
          </span>

          <span>
            AI confidence
          </span>

          <span>
            100%
          </span>

        </div>

      </div>


      {/* ==================================================
          REASONING
          ================================================== */}

      <div className="decision-reasoning">

        <span>
          Why ForexAI reached this result
        </span>

        <p>
          {reasoning}
        </p>

      </div>


      {/* ==================================================
          FOOTER
          ================================================== */}

      <div className="decision-footer">

        <div className="decision-footer-item">

          <span className="decision-footer-icon">
            ◉
          </span>

          <span>
            Multi-agent synthesis
          </span>

        </div>

        <span className="decision-footer-separator">
          /
        </span>

        <div className="decision-footer-item">

          <span>
            Technical
          </span>

          <span>
            Fundamental
          </span>

          <span>
            Quant
          </span>

        </div>

      </div>

    </article>
  );
}

export default FinalDecisionPanel;