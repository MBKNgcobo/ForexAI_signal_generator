interface RiskAssessment {
  risk_level?: string;
  approved?: boolean;
  agreement?: number;

  reason?: string;

  entry_price?: number;
  stop_loss?: number;
  take_profit?: number;

  risk_reward?: number;

  [key: string]: unknown;
}

interface RiskAssessmentPanelProps {
  riskAssessment: RiskAssessment;
}

function RiskAssessmentPanel({
  riskAssessment,
}: RiskAssessmentPanelProps) {

  const riskLevel =
    String(
      riskAssessment?.risk_level ??
      "UNKNOWN"
    ).toUpperCase();

  const approved =
    Boolean(
      riskAssessment?.approved
    );

  const agreement =
    typeof riskAssessment?.agreement === "number"
      ? riskAssessment.agreement * 100
      : 0;

  const entry =
    formatPrice(
      riskAssessment?.entry_price
    );

  const stopLoss =
    formatPrice(
      riskAssessment?.stop_loss
    );

  const takeProfit =
    formatPrice(
      riskAssessment?.take_profit
    );

  const riskReward =
    typeof riskAssessment?.risk_reward === "number"
      ? riskAssessment.risk_reward
      : null;

  const reason =
    String(
      riskAssessment?.reason ??
      "No risk assessment explanation available."
    );


  return (
    <article className="risk-card">

      {/* ==================================================
          HEADER
          ================================================== */}

      <div className="risk-card-header">

        <div>

          <span className="panel-eyebrow">
            RISK ENGINE
          </span>

          <h3>
            Risk profile
          </h3>

        </div>

        <span
          className={
            approved
              ? "risk-approved"
              : "risk-not-approved"
          }
        >
          {approved
            ? "Approved"
            : "Not approved"}
        </span>

      </div>


      {/* ==================================================
          RISK LEVEL
          ================================================== */}

      <div className="risk-level-section">

        <span className="risk-level-label">
          Current exposure
        </span>

        <div className="risk-level-row">

          <span
            className={
              `risk-level-badge risk-level-badge--${riskLevel.toLowerCase()}`
            }
          >
            <span className="risk-level-dot" />

            {riskLevel}
          </span>

          <span className="risk-agreement">
            {agreement.toFixed(0)}% agreement
          </span>

        </div>

      </div>


      {/* ==================================================
          PRICE LEVELS
          ================================================== */}

      <div className="risk-price-grid">

        <PriceBlock
          label="Entry"
          value={entry}
          className="price-entry"
        />

        <PriceBlock
          label="Stop Loss"
          value={stopLoss}
          className="price-stop"
        />

        <PriceBlock
          label="Take Profit"
          value={takeProfit}
          className="price-target"
        />

        <PriceBlock
          label="Risk / Reward"
          value={
            riskReward !== null
              ? `1 : ${riskReward}`
              : "—"
          }
          className="price-rr"
        />

      </div>


      {/* ==================================================
          REASON
          ================================================== */}

      <div className="risk-reason">

        <span>
          Risk assessment
        </span>

        <p>
          {reason}
        </p>

      </div>

    </article>
  );
}


function PriceBlock({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className: string;
}) {

  return (
    <div className="price-block">

      <span>
        {label}
      </span>

      <strong
        className={className}
      >
        {value}
      </strong>

    </div>
  );
}


function formatPrice(
  value: unknown
): string {

  if (
    typeof value !== "number" ||
    Number.isNaN(value)
  ) {
    return "—";
  }

  return value.toFixed(5);
}


export default RiskAssessmentPanel;