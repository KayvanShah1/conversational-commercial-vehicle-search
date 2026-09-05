import re

from vehicle_search_agent.response.models import GroundedResponse


def conversational_response(candidate: object, *, first_turn: bool, user_input: str = "") -> str:
    """Allow side conversation while rejecting ungrounded numeric vehicle claims."""
    if first_turn and re.fullmatch(r"\s*(?:hi|hello|hey|yo|namaste)[!.,?\s]*", user_input, re.IGNORECASE):
        return "Hey, I'm Vivi. Tell me what you need to transport, your budget, and where you're looking."

    response = candidate.strip() if isinstance(candidate, str) else ""
    has_ungrounded_value = bool(
        re.search(
            r"(?:₹|\bINR\b)\s*\d|\d[\d,.]*\s*(?:lakh|crore|km|kg|tons?|tonnes?)\b|\b(?:19|20)\d{2}\b",
            response,
            re.IGNORECASE,
        )
    )
    if not response or has_ungrounded_value:
        response = "I can help with commercial-vehicle searches and general questions about choosing one."

    if first_turn and "vivi" not in response.casefold():
        response = "Hi, I'm Vivi. " + response
    return " ".join(response.replace("**", "").replace("’", "'").replace("‑", "-").split())


def _normalized(text: str) -> str:
    text = text.casefold().replace("₹", "").replace("inr", "").replace("rupees", "").replace("lakh", "l")
    return re.sub(r"[^a-z0-9.]", "", text)


def _contains_checks_in_order(response: str, checks: tuple[tuple[str, ...], ...]) -> bool:
    normalized = _normalized(response)
    cursor = 0
    for group in checks:
        for expected in group:
            position = normalized.find(_normalized(expected), cursor)
            if position < 0:
                return False
            cursor = position + len(_normalized(expected))
    return True


def is_grounded_response(response: str, grounded: GroundedResponse) -> bool:
    if not response or not _contains_checks_in_order(response, grounded.checks):
        return False

    allowed_numbers = set(re.findall(r"\d+(?:[.,]\d+)*", " ".join(grounded.facts)))
    allowed_numbers.update(str(index) for index in range(1, len(grounded.checks) + 1))
    response_numbers = set(re.findall(r"\d+(?:[.,]\d+)*", response))
    return response_numbers <= allowed_numbers


def natural_response(
    candidate: object,
    grounded: GroundedResponse,
    *,
    first_turn: bool,
) -> str:
    """Accept natural framing only when every catalog fact remains unchanged."""
    response = candidate.strip() if isinstance(candidate, str) else ""

    if not is_grounded_response(response, grounded):
        response = grounded.fallback

    if first_turn and "vivi" not in response.casefold():
        warm_intro = "Hi, I'm Vivi. I'll help you find the right used truck. "
        response = warm_intro + response

    return " ".join(response.replace("**", "").split())
