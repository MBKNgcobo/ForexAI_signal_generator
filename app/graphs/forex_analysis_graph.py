import inspect
import logging
from functools import wraps
from time import perf_counter
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.decision_agent import run_decision_agent
from app.agents.fundamental_agent import FundamentalAgent
from app.agents.market_data_agent import run_market_data_agent
from app.agents.quant_agent import run_quant_agent
from app.agents.risk_agent import run_risk_agent
from app.agents.technical_agent import TechnicalAgent

from app.fundamentals.service import FundamentalRAGService
from app.llm.llm_provider import LLMProvider


logger = logging.getLogger(__name__)


def timed_node(name: str, node: Callable):
    @wraps(node)
    async def wrapper(state):
        started_at = perf_counter()

        try:
            result = node(state)

            if inspect.isawaitable(result):
                result = await result

            return result

        finally:
            elapsed = perf_counter() - started_at
            # Node timings fire for every request; INFO/WARNING would flood
            # production logs. Use DEBUG and let LOG_LEVEL decide.
            logger.debug(
                "TIMING | Graph node %s | %.3f seconds",
                name,
                elapsed,
    )

    return wrapper


class ForexAnalysisState(TypedDict, total=False):

    symbol: str
    timeframe: str

    market_data: Any

    technical_analysis: dict
    fundamental_analysis: dict
    quant_prediction: dict

    risk_assessment: dict
    final_decision: dict


def build_forex_analysis_graph(
    llm_provider: LLMProvider,
    rag_service: FundamentalRAGService | None = None,
):
    if rag_service is None:
        rag_service = FundamentalRAGService()

    technical_agent = TechnicalAgent(
        llm_provider
    )

    fundamental_agent = FundamentalAgent(
        llm_provider=llm_provider,
        rag_service=rag_service,
    )

    graph = StateGraph(
        ForexAnalysisState
    )

    graph.add_node(
        "market_data",
        timed_node("market_data", run_market_data_agent),
    )

    graph.add_node(
        "technical_analysis",
        timed_node("technical_analysis", technical_agent.run),
    )

    graph.add_node(
        "fundamental_analysis",
        timed_node("fundamental_analysis", fundamental_agent.run),
    )

    graph.add_node(
        "quant_prediction",
        timed_node("quant_prediction", run_quant_agent),
    )

    graph.add_node(
        "risk_assessment",
        timed_node("risk_assessment", run_risk_agent),
    )

    graph.add_node(
        "final_decision",
        timed_node("final_decision", run_decision_agent),
    )

    graph.add_edge(
        START,
        "market_data",
    )

    graph.add_edge(
        "market_data",
        "technical_analysis",
    )

    graph.add_edge(
        "market_data",
        "fundamental_analysis",
    )

    graph.add_edge(
        "market_data",
        "quant_prediction",
    )

    graph.add_edge(
        "technical_analysis",
        "risk_assessment",
    )

    graph.add_edge(
        "fundamental_analysis",
        "risk_assessment",
    )

    graph.add_edge(
        "quant_prediction",
        "risk_assessment",
    )

    graph.add_edge(
        "risk_assessment",
        "final_decision",
    )

    graph.add_edge(
        "final_decision",
        END,
    )

    return graph.compile()