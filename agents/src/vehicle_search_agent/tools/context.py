from dataclasses import dataclass

from vehicle_search_utils import OperationLogContext, get_logger

from agents import RunContextWrapper
from vehicle_search_agent.models import AgentAction, ConversationState, VehicleSearchResult
from vehicle_search_agent.response import GroundedResponse

logger = get_logger("VehicleSearchTools")


@dataclass
class AgentContext:
    state: ConversationState
    current_input: str = ""
    action: AgentAction = AgentAction.conversation
    last_search_result: VehicleSearchResult | None = None
    catalog_ms: float | None = None
    grounded_response: GroundedResponse | None = None
    response_ms: float | None = None
    understanding_ms: float | None = None
    llm_operation: OperationLogContext | None = None
    llm_list_cost_usd: float = 0.0
    pricing_complete: bool = True
    tool_failures: int = 0
    model_name: str = "unknown"
    model_route: str = "unknown"

    def reset_turn(self) -> None:
        self.current_input = ""
        self.action = AgentAction.conversation
        self.last_search_result = None
        self.catalog_ms = None
        self.grounded_response = None
        self.response_ms = None
        self.understanding_ms = None
        self.llm_operation = None
        self.llm_list_cost_usd = 0.0
        self.pricing_complete = True
        self.tool_failures = 0
        self.model_name = "unknown"
        self.model_route = "unknown"


def retry_tool_error(ctx: RunContextWrapper[AgentContext], error: Exception) -> str:
    """Return invalid arguments to the model for at most three self-correction attempts."""
    ctx.context.tool_failures += 1
    logger.warning(
        "tool_input_rejected",
        extra={
            "tool": getattr(ctx, "tool_name", "unknown"),
            "attempt": ctx.context.tool_failures,
            "error_type": type(error).__name__,
            "error": str(error),
        },
    )
    return f"Tool arguments were invalid. Correct them using the declared schema and retry. Validation: {error}"


def log_tool_call(context: AgentContext, tool: str) -> None:
    logger.info(
        "tool_called",
        extra={"tool": tool, "model": context.model_name, "model_route": context.model_route},
    )


def rephrase_request(response: GroundedResponse, *, first_turn: bool) -> str:
    facts = "\n".join(f"- {fact}" for fact in response.facts)
    introduction = " Begin with a short, warm introduction as Vivi." if first_turn else ""
    return (
        "Write one concise, natural reply. Preserve every catalog value and key label below, "
        "but connect and rephrase them naturally. Mention each vehicle once. Do not add facts or numbers. "
        "Never describe kilometres driven or an odometer reading as mileage or fuel economy."
        f"{introduction}\n\n"
        f"Grounded facts:\n{facts}"
    )


def set_response(context: AgentContext, response: GroundedResponse) -> str:
    context.grounded_response = response
    return rephrase_request(response, first_turn=context.state.turn_number == 1)
