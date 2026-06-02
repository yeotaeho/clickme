from fastmcp import FastMCP

mcp = FastMCP("persona100-simulation")


@mcp.tool()
async def run_ad_simulation(ad_base64: str, persona_config: dict) -> dict:
    """외부 MCP 클라이언트가 시뮬레이션을 호출하는 표준 진입점.

    Args:
        ad_base64: base64 인코딩된 광고 이미지
        persona_config: PersonaGenerationRequest 파라미터

    Returns:
        SimulationReport dict
    """
    from backend.domain.multiagent.hub.orchestrator.simulation_graph import simulation_graph
    from backend.domain.multiagent.models.states.simulation_state import initial_state
    import uuid

    sim_id = str(uuid.uuid4())
    state = initial_state(
        simulation_id=sim_id,
        ad_input={"base64_image": ad_base64, "filename": "mcp_upload.jpg", "persona_config": persona_config},
    )
    final_state = await simulation_graph.ainvoke(state)
    return final_state.get("report", {})


@mcp.tool()
async def get_simulation_status(simulation_id: str) -> dict:
    """시뮬레이션 진행 상태 조회."""
    from backend.domain.multiagent.hub.repositories.simulation_repository import SimulationRepository
    repo = SimulationRepository()
    return await repo.get_status(simulation_id)
