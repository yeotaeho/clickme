from typing import TypedDict


class SimulationState(TypedDict):
    simulation_id: str
    ad_input: dict           # {"base64_image": str, "filename": str, "campaign_context": str}
    ad_analysis: dict        # AdAnalysis.model_dump()
    persona_pool: list       # list[Persona.model_dump()]
    raw_responses: list      # list[PersonaResponse.model_dump()]
    aggregated_stats: dict
    performance_predictions: dict
    recommendations: list    # list[ActionItem dict]
    report: dict             # SimulationReport dict
    errors: list             # list[{"type": str, "detail": str, "persona_id": str | None}]
    progress: int            # 0~100
    retry_count: int         # Supervisor 재시도 횟수


def initial_state(simulation_id: str, ad_input: dict) -> SimulationState:
    return SimulationState(
        simulation_id=simulation_id,
        ad_input=ad_input,
        ad_analysis={},
        persona_pool=[],
        raw_responses=[],
        aggregated_stats={},
        performance_predictions={},
        recommendations=[],
        report={},
        errors=[],
        progress=0,
        retry_count=0,
    )
