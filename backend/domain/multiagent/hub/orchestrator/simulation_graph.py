from langgraph.graph import END, StateGraph

from backend.domain.multiagent.hub.orchestrator.supervisor import supervisor_route
from backend.domain.multiagent.hub.services.aggregation_service import AggregationService
from backend.domain.multiagent.hub.services.report_service import ReportService
from backend.domain.multiagent.models.states.simulation_state import SimulationState
from backend.domain.multiagent.spokes.agents.ad_understanding import AdUnderstandingAgent
from backend.domain.multiagent.spokes.agents.persona_generation import PersonaGenerationAgent
from backend.domain.multiagent.spokes.agents.prediction import PredictionAgent
from backend.domain.multiagent.spokes.agents.reaction_simulation import ReactionSimulationAgent
from backend.domain.multiagent.spokes.agents.recommendation import RecommendationAgent
from backend.domain.multiagent.spokes.agents.validation import ValidationAgent

# 에이전트 인스턴스
_ad_agent = AdUnderstandingAgent()
_persona_agent = PersonaGenerationAgent()
_reaction_agent = ReactionSimulationAgent()
_validation_agent = ValidationAgent()
_prediction_agent = PredictionAgent()
_recommendation_agent = RecommendationAgent()
_aggregation_svc = AggregationService()
_report_svc = ReportService()


# ─── 노드 함수 ────────────────────────────────────────────────


async def analyze_ad_node(state: SimulationState) -> SimulationState:
    return await _ad_agent.run(state)


async def generate_personas_node(state: SimulationState) -> SimulationState:
    return await _persona_agent.run(state)


async def run_reactions_node(state: SimulationState) -> SimulationState:
    # 재시도 횟수 증가
    state["retry_count"] = state.get("retry_count", 0) + 1
    return await _reaction_agent.run(state)


def validate_responses_node(state: SimulationState) -> SimulationState:
    return _validation_agent.run(state)


def aggregate_stats_node(state: SimulationState) -> SimulationState:
    return _aggregation_svc.run(state)


async def predict_performance_node(state: SimulationState) -> SimulationState:
    return await _prediction_agent.run(state)


async def generate_recommendations_node(state: SimulationState) -> SimulationState:
    return await _recommendation_agent.run(state)


def generate_report_node(state: SimulationState) -> SimulationState:
    return _report_svc.run(state)


# ─── 그래프 조립 ──────────────────────────────────────────────


def build_simulation_graph():
    graph = StateGraph(SimulationState)

    graph.add_node("analyze_ad", analyze_ad_node)
    graph.add_node("generate_personas", generate_personas_node)
    graph.add_node("run_reactions", run_reactions_node)
    graph.add_node("validate_responses", validate_responses_node)
    graph.add_node("aggregate_stats", aggregate_stats_node)
    graph.add_node("predict_performance", predict_performance_node)
    graph.add_node("generate_recommendations", generate_recommendations_node)
    graph.add_node("generate_report", generate_report_node)

    graph.set_entry_point("analyze_ad")
    graph.add_edge("analyze_ad", "generate_personas")
    graph.add_edge("generate_personas", "run_reactions")
    graph.add_edge("run_reactions", "validate_responses")

    # Supervisor LLM conditional edge
    graph.add_conditional_edges(
        "validate_responses",
        supervisor_route,
        {
            "aggregate_stats": "aggregate_stats",
            "retry_reactions": "run_reactions",
            "end": END,
        },
    )

    graph.add_edge("aggregate_stats", "predict_performance")
    graph.add_edge("predict_performance", "generate_recommendations")
    graph.add_edge("generate_recommendations", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


simulation_graph = build_simulation_graph()
