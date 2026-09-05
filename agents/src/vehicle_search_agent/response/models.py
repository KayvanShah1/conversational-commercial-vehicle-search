from dataclasses import dataclass


@dataclass(frozen=True)
class GroundedResponse:
    fallback: str
    facts: tuple[str, ...]
    checks: tuple[tuple[str, ...], ...]
    display_markdown: str | None = None


@dataclass(frozen=True)
class DetailValue:
    fact: str
    spoken_clause: str | None
    display_label: str
    display_value: str
    checks: tuple[str, ...]
