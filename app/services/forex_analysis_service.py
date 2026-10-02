from app.graphs.forex_analysis_graph import (
    build_forex_analysis_graph,
)

from app.llm.llm_provider import (
    LLMProvider,
)


class ForexAnalysisService:

    def __init__(
        self,
        llm_provider: LLMProvider,
    ):
        self.graph = (
            build_forex_analysis_graph(
                llm_provider
            )
        )

    async def analyze(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict:

        return await self.graph.ainvoke(
            {
                "symbol": symbol,
                "timeframe": timeframe,
            }
        )