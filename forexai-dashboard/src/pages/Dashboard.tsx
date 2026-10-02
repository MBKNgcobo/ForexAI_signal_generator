import {
  useEffect,
  useState,
} from "react";

import { analyzeMarket } from "../services/api";
import { getMarketData } from "../services/marketDataApi";

import type {
  AnalysisWithSignalResult,
} from "../types/analysis";

import type {
  MarketDataResponse,
} from "../types/market";

import MarketPanel from "../components/market/MarketPanel";
import MarketChart from "../components/market/MarketChart";

import AgentAnalysisPanel from "../components/analysis/AgentAnalysisPanel";
import RiskAssessmentPanel from "../components/analysis/RiskAssessmentPanel";
import FinalDecisionPanel from "../components/analysis/FinalDecisionPanel";

import SignalReview from "../components/signals/SignalReview";

import { getForexPairs } from "../services/forexPairApi";
import type { ForexPair } from "../types/forexPair";

import { getTimeframes } from "../services/timeframeApi";
import type { Timeframe } from "../types/timeframe";


function Dashboard() {

  // ============================================================
  // ANALYSIS STATE
  // ============================================================

  const [result, setResult] =
    useState<AnalysisWithSignalResult | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);


  // ============================================================
  // MARKET SELECTION STATE
  // ============================================================

  const [symbol, setSymbol] =
    useState("EURUSD");

  const [timeframe, setTimeframe] =
    useState("FifteenMinutes");

  const [limit, setLimit] =
    useState(100);

  const [forexPairs, setForexPairs] =
    useState<ForexPair[]>([]);

  const [selectedPairId, setSelectedPairId] =
    useState<string>("");

  const [timeframes, setTimeframes] =
    useState<Timeframe[]>([]);


  // ============================================================
  // MARKET DATA STATE
  // ============================================================

  const [marketData, setMarketData] =
    useState<MarketDataResponse | null>(null);

  const [marketDataLoading, setMarketDataLoading] =
    useState(false);

  const [marketDataError, setMarketDataError] =
    useState<string | null>(null);


  // ============================================================
  // LOAD MARKET DATA
  // ============================================================

  async function loadMarketData() {

    if (!symbol || !timeframe) {
      return;
    }

    setMarketDataLoading(true);
    setMarketDataError(null);

    try {

      const data = await getMarketData(
        symbol,
        timeframe,
        limit
      );

      console.log(
        "Market data response:",
        data
      );

      setMarketData(data);

    } catch (err) {

      console.error(
        "Market data error:",
        err
      );

      setMarketData(null);

      setMarketDataError(
        err instanceof Error
          ? err.message
          : "Unable to load market data."
      );

    } finally {

      setMarketDataLoading(false);

    }
  }


  // ============================================================
  // LOAD FOREX PAIRS
  // ============================================================

  async function loadForexPairs() {

    try {

      const pairs =
        await getForexPairs();

      setForexPairs(pairs);

      if (pairs.length > 0) {

        const defaultPair =
          pairs.find(
            (pair) =>
              pair.symbol === symbol
          ) ?? pairs[0];

        setSelectedPairId(
          defaultPair.id
        );

        setSymbol(
          defaultPair.symbol
        );
      }

    } catch (err) {

      console.error(
        "Forex pair loading error:",
        err
      );

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load forex pairs."
      );
    }
  }


  // ============================================================
  // LOAD TIMEFRAMES
  // ============================================================

  async function loadTimeframes() {

    try {

      const data =
        await getTimeframes();

      setTimeframes(data);

      if (data.length > 0) {

        const defaultTimeframe =
          data.find(
            (option) =>
              option.value === timeframe
          ) ?? data[0];

        setTimeframe(
          defaultTimeframe.value
        );
      }

    } catch (err) {

      console.error(
        "Timeframe loading error:",
        err
      );

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load timeframes."
      );
    }
  }


  // ============================================================
  // LOAD MARKET OPTIONS
  // ============================================================

  useEffect(() => {

    async function loadMarketOptions() {

      await Promise.all([
        loadForexPairs(),
        loadTimeframes(),
      ]);

    }

    loadMarketOptions();

  }, []);


  // ============================================================
  // LOAD MARKET DATA WHEN SELECTION CHANGES
  // ============================================================

  useEffect(() => {

    if (!symbol || !timeframe) {
      return;
    }

    loadMarketData();

    const intervalId =
      window.setInterval(() => {
        loadMarketData();
      }, 30000);

    return () => {
      window.clearInterval(
        intervalId
      );
    };

  }, [
    symbol,
    timeframe,
    limit,
  ]);


  // ============================================================
  // ANALYSE MARKET
  // ============================================================

  async function handleAnalyze() {

    if (!selectedPairId) {

      setError(
        "Please select a forex pair."
      );

      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {

      const data =
        await analyzeMarket(
          selectedPairId,
          symbol,
          timeframe
        );

      console.log(
        "ForexAI analysis response:",
        data
      );

      setResult(data);

    } catch (err) {

      console.error(
        "ForexAI analysis error:",
        err
      );

      setError(
        err instanceof Error
          ? err.message
          : "An unexpected error occurred."
      );

    } finally {

      setLoading(false);

    }
  }


  // ============================================================
  // MARKET SELECTION CHANGE
  // ============================================================

  function handleMarketChange(
    newSymbol: string,
    newTimeframe: string
  ) {

    setSymbol(newSymbol);
    setTimeframe(newTimeframe);

    setResult(null);
    setError(null);

  }


  // ============================================================
  // EXTRACT ANALYSIS
  // ============================================================

  const analysis =
    result?.analysis;


  // ============================================================
  // RENDER
  // ============================================================

  return (
    <div className="dashboard-page">

      {/* ======================================================
          MARKET HEADER
          ====================================================== */}

      <section className="dashboard-header">

        <div>

          <div className="market-kicker">
            AI MARKET WORKSPACE
          </div>

          <div className="market-title-row">

            <h2>
              {symbol}
            </h2>

            <span className="timeframe-pill">
              {timeframe}
            </span>

          </div>

          <p className="market-subtitle">
            Multi-agent analysis across technical,
            fundamental and quantitative models.
          </p>

        </div>


        <div className="market-live-status">

          <span className="status-dot" />

          {marketDataLoading
            ? "Updating market"
            : "Market data connected"}

        </div>

      </section>


      {/* ======================================================
          MARKET CONTROLS
          ====================================================== */}

     <section className="market-controls-panel">

                <MarketPanel
                  pairs={forexPairs}
                  symbol={symbol}
                  timeframe={timeframe}
                  limit={limit}
                  loading={loading}
                  timeframes={timeframes}

                  onLimitChange={(newLimit) => {
                    setLimit(newLimit);
                  }}

                  onAnalyze={handleAnalyze}

                  onSymbolChange={(newSymbol) => {

                    const selectedPair =
                      forexPairs.find(
                        (pair) =>
                          pair.symbol === newSymbol
                      );

                    if (selectedPair) {
                      setSelectedPairId(
                        selectedPair.id
                      );
                    }

                    handleMarketChange(
                      newSymbol,
                      timeframe
                    );

                  }}

                  onTimeframeChange={(newTimeframe) => {

                    handleMarketChange(
                      symbol,
                      newTimeframe
                    );

                  }}
                />
        </section>


      {/* ======================================================
          MARKET DATA ERROR
          ====================================================== */}

      {marketDataError && (

        <section className="error-card">

          <div>
            <span className="panel-eyebrow">
              MARKET DATA
            </span>

            <h3>
              Unable to load market data
            </h3>

            <p>
              {marketDataError}
            </p>
          </div>

          <button
            type="button"
            onClick={loadMarketData}
            disabled={marketDataLoading}
          >
            {marketDataLoading
              ? "Retrying..."
              : "Retry"}
          </button>

        </section>

      )}


      {/* ======================================================
          PRICE CHART
          ====================================================== */}

      {marketData && (

       <section className="workspace-panel chart-panel">

  <div className="chart-wrapper">

    <MarketChart
      symbol={symbol}
      timeframe={timeframe}
      candles={marketData.candles}

      entryPrice={
        analysis?.riskAssessment
          ?.entry_price
      }

      stopLoss={
        analysis?.riskAssessment
          ?.stop_loss
      }

      takeProfit={
        analysis?.riskAssessment
          ?.take_profit
      }
    />

  </div>

</section>

      )}


      {/* ======================================================
          ANALYSIS ERROR
          ====================================================== */}

      {error && (

        <section className="error-card">

          <div>

            <span className="panel-eyebrow">
              ANALYSIS
            </span>

            <h3>
              Analysis failed
            </h3>

            <p>
              {error}
            </p>

          </div>

        </section>

      )}


      {/* ======================================================
          LONG-RUNNING ANALYSIS STATE
          ====================================================== */}

      {loading && (

        <section className="analysis-progress">

          <div className="progress-spinner" />

          <div>

            <span className="panel-eyebrow">
              AI ANALYSIS RUNNING
            </span>

            <h3>
              ForexAI is analysing {symbol}
            </h3>

            <p>
              Technical, fundamental and quantitative
              agents are evaluating the current market.
            </p>

          </div>

          <div className="agent-progress">

            <span>
              Technical
            </span>

            <span>
              Fundamental
            </span>

            <span>
              Quant
            </span>

            <span>
              Risk
            </span>

            <span>
              Decision
            </span>

          </div>

        </section>

      )}


      {/* ======================================================
          EMPTY ANALYSIS STATE
          ====================================================== */}

      {!analysis &&
        !loading &&
        !error && (

          <section className="analysis-empty">

            <div className="empty-icon">
              ✦
            </div>

            <span className="panel-eyebrow">
              AI ANALYSIS
            </span>

            <h3>
              No active analysis
            </h3>

            <p>
              Select a forex pair and timeframe,
              then run an analysis to generate a
              multi-agent market assessment.
            </p>

          </section>

        )}


      {/* ======================================================
          ANALYSIS RESULTS
          ====================================================== */}

      {analysis && (

        <>

          {/* ==================================================
              ANALYSIS SUMMARY
              ================================================== */}

          <section className="analysis-summary">

            <div>

              <span className="panel-eyebrow">
                ANALYSIS COMPLETE
              </span>

              <h2>
                {analysis.symbol}
              </h2>

              <p>
                {analysis.timeframe} multi-agent assessment
              </p>

            </div>

            <span className="analysis-complete-pill">
              ● Complete
            </span>

          </section>


          {/* ==================================================
              DECISION + RISK
              ================================================== */}

          <section className="decision-layout">

            <div className="decision-panel">

              <div className="panel-heading">

                <div>

                  <span className="panel-eyebrow">
                    AI DECISION
                  </span>

                  <h3>
                    Final market assessment
                  </h3>

                </div>

                <span className="panel-hint">
                  Multi-agent synthesis
                </span>

              </div>

              <FinalDecisionPanel
                decision={
                  { ...analysis.finalDecision }
                }
              />

            </div>


            {analysis.riskAssessment && (

              <div className="risk-panel">

                <div className="panel-heading">

                  <div>

                    <span className="panel-eyebrow">
                      RISK
                    </span>

                    <h3>
                      Risk profile
                    </h3>

                  </div>

                </div>

                <RiskAssessmentPanel
                  riskAssessment={
                    {
                      ...analysis.riskAssessment,
                      entry_price:
                        analysis.riskAssessment.entry_price ?? undefined,
                      stop_loss:
                        analysis.riskAssessment.stop_loss ?? undefined,
                      take_profit:
                        analysis.riskAssessment.take_profit ?? undefined,
                      risk_reward:
                        analysis.riskAssessment.risk_reward ?? undefined,
                    }
                  }
                />

              </div>

            )}

          </section>


          {/* ==================================================
              AGENT ANALYSIS
              ================================================== */}

          <section className="workspace-section">

            <div className="panel-heading">

              <div>

                <span className="panel-eyebrow">
                  SPECIALIST AGENTS
                </span>

                <h3>
                  Agent analysis
                </h3>

              </div>

              <span className="panel-hint">
                Independent model perspectives
              </span>

            </div>


            <div className="analysis-grid">

              <AgentAnalysisPanel
                title="Technical"
                analysis={
                  { ...analysis.technicalAnalysis }
                }
              />

              <AgentAnalysisPanel
                title="Fundamental"
                analysis={
                  { ...analysis.fundamentalAnalysis }
                }
              />

              <AgentAnalysisPanel
                title="Quant"
                analysis={
                  { ...analysis.quantPrediction }
                }
              />

            </div>

          </section>


          {/* ==================================================
              HUMAN REVIEW
              ================================================== */}

          <section className="workspace-section">

            <div className="panel-heading">

              <div>

                <span className="panel-eyebrow">
                  HUMAN-IN-THE-LOOP
                </span>

                <h3>
                  Signal review
                </h3>

              </div>

              <span className="panel-hint">
                Your decision remains in control
              </span>

            </div>


            {result.signal ? (

              <SignalReview
                signal={result.signal}

                onStatusChange={(status) => {

                  setResult(
                    (current) => {

                      if (
                        !current ||
                        !current.signal
                      ) {
                        return current;
                      }

                      return {
                        ...current,
                        signal: {
                          ...current.signal,
                          status,
                        },
                      };

                    }
                  );

                }}

              />

            ) : (

              <section className="signal-empty">

                <span className="empty-icon">
                  —
                </span>

                <h3>
                  No trading signal
                </h3>

                <p>
                  This analysis did not generate a
                  reviewable trading signal.
                </p>

              </section>

            )}

          </section>

        </>

      )}

    </div>
  );
}


export default Dashboard;