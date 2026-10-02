import {
  useEffect,
  useRef,
} from "react";

import {
  createChart,
  CandlestickSeries,
  CrosshairMode,
  ColorType,
  type Time,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
} from "lightweight-charts";

import type {
  MarketCandle,
} from "../../types/market";


interface MarketChartProps {
  symbol: string;
  timeframe: string;
  candles: MarketCandle[];
  entryPrice?: number | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
}


function MarketChart({
  symbol,
  timeframe,
  candles,
  entryPrice,
  stopLoss,
  takeProfit,
}: MarketChartProps) {

  const chartContainerRef =
    useRef<HTMLDivElement | null>(null);

  const chartRef =
    useRef<IChartApi | null>(null);

  const seriesRef =
    useRef<ISeriesApi<"Candlestick"> | null>(null);

  const entryLineRef =
    useRef<IPriceLine | null>(null);

  const stopLossLineRef =
    useRef<IPriceLine | null>(null);

  const takeProfitLineRef =
    useRef<IPriceLine | null>(null);


  /* ==========================================================
     CREATE CHART
     ========================================================== */

  useEffect(() => {

    if (!chartContainerRef.current) {
      return;
    }

    const container =
      chartContainerRef.current;

    const chart = createChart(
      container,
      {
        width: container.clientWidth,
        height: 480,

        layout: {
          background: {
            type: ColorType.Solid,
            color: "#090c10",
          },

          textColor: "#7f8997",
        },

        grid: {
          vertLines: {
            color: "#171c23",
          },

          horzLines: {
            color: "#171c23",
          },
        },

        crosshair: {
          mode: CrosshairMode.Normal,

          vertLine: {
            color: "#4a5360",
            width: 1,
            style: 2,
            labelBackgroundColor: "#202630",
          },

          horzLine: {
            color: "#4a5360",
            width: 1,
            style: 2,
            labelBackgroundColor: "#202630",
          },
        },

        rightPriceScale: {
          borderColor: "#20262f",

          scaleMargins: {
            top: 0.08,
            bottom: 0.08,
          },
        },

        timeScale: {
          borderColor: "#20262f",

          timeVisible: true,
          secondsVisible: false,

          rightOffset: 5,

          barSpacing: 8,
          minBarSpacing: 3,
        },

        handleScroll: {
          mouseWheel: true,
          pressedMouseMove: true,
          horzTouchDrag: true,
          vertTouchDrag: true,
        },

        handleScale: {
          mouseWheel: true,
          pinch: true,
          axisPressedMouseMove: true,
        },
      }
    );


    const candlestickSeries =
      chart.addSeries(
        CandlestickSeries,
        {
          upColor: "#45d483",
          downColor: "#f16b73",

          borderUpColor: "#45d483",
          borderDownColor: "#f16b73",

          wickUpColor: "#45d483",
          wickDownColor: "#f16b73",
        }
      );


    chartRef.current = chart;

    seriesRef.current =
      candlestickSeries;


    /* ========================================================
       RESPONSIVE CHART
       ======================================================== */

    const resizeObserver =
      new ResizeObserver(
        (entries) => {

          const entry =
            entries[0];

          if (!entry) {
            return;
          }

          const width =
            Math.floor(
              entry.contentRect.width
            );

          if (width > 0) {

            chart.applyOptions({
              width,
            });

          }

        }
      );


    resizeObserver.observe(
      container
    );


    return () => {

      resizeObserver.disconnect();

      chart.remove();

      chartRef.current = null;
      seriesRef.current = null;

      entryLineRef.current = null;
      stopLossLineRef.current = null;
      takeProfitLineRef.current = null;

    };

  }, []);


  /* ==========================================================
     UPDATE CANDLES
     ========================================================== */

  useEffect(() => {

    if (
      !seriesRef.current ||
      candles.length === 0
    ) {
      return;
    }

    const chartData =
      candles.map(
        (candle) => ({
          time: Math.floor(
            new Date(
              candle.timestamp
            ).getTime() / 1000
          ) as Time,

          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
        })
      );


    seriesRef.current.setData(
      chartData
    );


    chartRef.current
      ?.timeScale()
      .fitContent();

  }, [candles]);


  /* ==========================================================
     UPDATE TRADE LEVELS
     ========================================================== */

  useEffect(() => {

    if (!seriesRef.current) {
      return;
    }


    if (entryLineRef.current) {

      seriesRef.current.removePriceLine(
        entryLineRef.current
      );

      entryLineRef.current = null;
    }


    if (stopLossLineRef.current) {

      seriesRef.current.removePriceLine(
        stopLossLineRef.current
      );

      stopLossLineRef.current = null;
    }


    if (takeProfitLineRef.current) {

      seriesRef.current.removePriceLine(
        takeProfitLineRef.current
      );

      takeProfitLineRef.current = null;
    }


    if (
      entryPrice !== null &&
      entryPrice !== undefined
    ) {

      entryLineRef.current =
        seriesRef.current.createPriceLine({
          price: entryPrice,

          title: "ENTRY",

          color: "#8f99a7",

          lineWidth: 1,

          axisLabelVisible: true,

          lineStyle: 2,
        });

    }


    if (
      stopLoss !== null &&
      stopLoss !== undefined
    ) {

      stopLossLineRef.current =
        seriesRef.current.createPriceLine({
          price: stopLoss,

          title: "SL",

          color: "#f16b73",

          lineWidth: 1,

          axisLabelVisible: true,

          lineStyle: 2,
        });

    }


    if (
      takeProfit !== null &&
      takeProfit !== undefined
    ) {

      takeProfitLineRef.current =
        seriesRef.current.createPriceLine({
          price: takeProfit,

          title: "TP",

          color: "#45d483",

          lineWidth: 1,

          axisLabelVisible: true,

          lineStyle: 2,
        });

    }

  }, [
    entryPrice,
    stopLoss,
    takeProfit,
  ]);


  return (
    <section className="market-chart-card">

      <div className="market-chart-header">

        <div>

          <span className="panel-eyebrow">
            PRICE ACTION
          </span>

          <h2>
            {symbol}
          </h2>

        </div>

        <div className="chart-header-meta">

          <span>
            {formatTimeframe(
              timeframe
            )}
          </span>

          <span>
            {candles.length} candles
          </span>

        </div>

      </div>


      <div
        ref={chartContainerRef}
        className="market-chart"
      />

    </section>
  );
}


function formatTimeframe(
  value: string
): string {

  const labels: Record<
    string,
    string
  > = {
    OneMinute: "1m",
    FiveMinutes: "5m",
    FifteenMinutes: "15m",
    ThirtyMinutes: "30m",
    OneHour: "1h",
    FourHours: "4h",
    OneDay: "1D",
  };

  return labels[value] ?? value;
}


export default MarketChart;