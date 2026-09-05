import asyncio

from agents import RunContextWrapper, function_tool
from vehicle_search_agent.models import AgentAction, CatalogTopic
from vehicle_search_agent.response import catalog_options_response, message_response
from vehicle_search_agent.search import get_catalog_options
from vehicle_search_agent.settings import settings
from vehicle_search_agent.tools.context import AgentContext, logger, retry_tool_error, set_response


@function_tool(
    strict_mode=False,
    timeout=settings.agent_runtime.tool_timeout_seconds,
    timeout_behavior="raise_exception",
    failure_error_function=retry_tool_error,
)
async def list_catalog_options(
    ctx: RunContextWrapper[AgentContext],
    include_cities: bool = False,
    include_categories: bool = False,
    include_body_types: bool = False,
    include_fuels: bool = False,
    include_makes: bool = False,
    include_purposes: bool = False,
) -> str:
    """List available cities, vehicle categories, body types, fuels, makes, or purposes."""
    logger.info("tool_called", extra={"tool": "list_catalog_options"})
    context = ctx.context
    context.action = AgentAction.catalog_options
    requested = {
        CatalogTopic.cities: include_cities,
        CatalogTopic.vehicle_categories: include_categories,
        CatalogTopic.body_types: include_body_types,
        CatalogTopic.fuels: include_fuels,
        CatalogTopic.makes: include_makes,
        CatalogTopic.purposes: include_purposes,
    }
    topics = [topic for topic, included in requested.items() if included]
    if not topics:
        return set_response(context, message_response("Which catalog options would you like to know about?"))

    options, context.catalog_ms = await asyncio.to_thread(get_catalog_options, topics)
    return set_response(context, catalog_options_response(options))
