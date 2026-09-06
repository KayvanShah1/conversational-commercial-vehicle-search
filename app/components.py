from collections.abc import Callable
from html import escape

import streamlit as st
from config import METRIC_LABELS, SLOT_LABELS, STARTER_QUESTIONS
from vehicle_search_agent.models import AgentTurnResult, RankedVehicle, SearchFilters, VehicleSearchResult
from vehicle_search_agent.runner import VehicleSearchSession


def _format_ms(value: float) -> str:
    return "<1 ms" if value < 1 else f"{value:,.0f} ms"


def display_response(result: AgentTurnResult, session: VehicleSearchSession) -> str:
    grounded = session.context.grounded_response
    if result.action.value == "details":
        return grounded.display_markdown if grounded and grounded.display_markdown else result.spoken_response

    if grounded is None or not grounded.facts:
        return result.spoken_response
    if result.action.value == "search" and not result.last_result_ids:
        return grounded.fallback

    def bullet(fact: str) -> str:
        label, separator, value = fact.partition(":")
        if separator:
            return f"- **{label}:** {value.strip()}"
        return f"- {fact}"

    if result.action.value == "search" and result.last_result_ids:
        lines = ["**Top match**", bullet(grounded.facts[0])]
        if len(grounded.facts) > 1:
            lines.extend(["", "**Other options**", *(bullet(fact) for fact in grounded.facts[1:])])
        return "\n".join(lines)
    return "\n".join(bullet(fact) for fact in grounded.facts)


def render_sidebar(reset_conversation: Callable[[], None]) -> None:
    with st.sidebar:
        with st.container(key="sidebar_header"):
            st.title("Vivi")
            st.caption("Commercial vehicle assistant")
        with st.container(horizontal=True):
            st.badge("Catalog connected", icon=":material/database:", color="green")
            st.badge("Voice & Text Available", icon=":material/mic:", color="primary")
        st.button(
            "Start new chat",
            icon=":material/add:",
            type="secondary",
            width="stretch",
            key="new_chat",
            on_click=reset_conversation,
        )

        st.subheader("Current search")
        session = st.session_state.vehicle_session
        filters = (
            session.context.state.active_filters.model_dump(mode="json", exclude_none=True)
            if session is not None
            else {}
        )
        if filters:
            with st.container(horizontal=True, wrap=True):
                for name, value in filters.items():
                    label = SLOT_LABELS.get(name, name.replace("_", " ").title())
                    st.badge(f"{label}: {_display_value(name, value)}", color="gray")
        else:
            st.caption("Budget, location and vehicle needs will stay visible here.")

        st.subheader("Conversation totals")
        totals = st.session_state.conversation_totals
        if totals["turns"]:
            total_rows = [
                f"| Completed turns | {totals['turns']:,} |  |",
                f"| Processing time | {_format_duration(totals['total_ms'])} |  |",
                f"| LLM requests | {totals['llm_requests']:,} |  |",
                (
                    f"| LLM tokens | {totals['total_tokens']:,} | "
                    f"{_format_cost(totals['estimated_llm_list_cost_inr'])} |"
                ),
            ]
            if totals["audio_input_seconds"]:
                total_rows.append(
                    f"| STT audio | {totals['audio_input_seconds']:.2f} s | "
                    f"{_format_cost(totals['estimated_stt_list_cost_inr'])} |"
                )
            if totals["tts_characters"]:
                total_rows.append(
                    f"| TTS output | {totals['tts_characters']:,} characters | "
                    f"{_format_cost(totals['estimated_tts_list_cost_inr'])} |"
                )
            total_rows.append(f"| **Conversation total** |  | **{_format_cost(totals['estimated_list_cost_inr'])}** |")
            with st.container(key="conversation_table"):
                st.markdown("| Usage | Total | Est. cost |\n|:--|--:|--:|\n" + "\n".join(total_rows))
            st.caption("Conversation cost sums completed-turn estimates; free-tier spend may be zero.")
        else:
            st.caption("Time, tokens and estimated cost will accumulate here.")

        st.subheader("Latest turn timing")
        if st.session_state.metrics:
            voice_total = st.session_state.metrics.get("recording_received_to_audio_ready_ms")
            rows = [
                f"| {_metric_label(name)} | {_format_ms(value)} |"
                for name, value in st.session_state.metrics.items()
                if name != "total_ms"
            ]
            if voice_total is None and (total := st.session_state.metrics.get("total_ms")) is not None:
                rows.append(f"| **Turn total** | **{_format_ms(total)}** |")
            with st.container(key="timing_table"):
                st.markdown("| Stage | Time |\n|:--|--:|\n" + "\n".join(rows))
        else:
            st.caption("Stage timings appear after the first turn.")

        st.subheader("Latest turn usage")
        if st.session_state.usage:
            usage = st.session_state.usage
            usage_rows = [
                f"| LLM requests | {usage['llm_requests']:,} |  |",
                f"| Context / input tokens | {usage['input_tokens']:,} |  |",
                f"| Cached context tokens | {usage.get('cached_input_tokens', 0):,} |  |",
                f"| Output tokens | {usage['output_tokens']:,} |  |",
                f"| Reasoning tokens | {usage.get('reasoning_tokens', 0):,} |  |",
                (
                    f"| **Total LLM tokens** | **{usage['total_tokens']:,}** | "
                    f"**{_format_cost(usage.get('estimated_llm_list_cost_inr'))}** |"
                ),
            ]
            if (seconds := usage.get("audio_input_seconds")) is not None:
                usage_rows.append(
                    f"| STT audio | {seconds:.2f} s | {_format_cost(usage.get('estimated_stt_list_cost_inr'))} |"
                )
            if (characters := usage.get("tts_characters")) is not None:
                usage_rows.append(
                    f"| TTS output | {characters:,} characters | "
                    f"{_format_cost(usage.get('estimated_tts_list_cost_inr'))} |"
                )
            if (cost := usage.get("estimated_list_cost_inr")) is not None:
                usage_rows.append(f"| **Turn total** |  | **{_format_cost(cost)}** |")
            with st.container(key="usage_table"):
                st.markdown("| Usage | Quantity | Est. cost |\n|:--|--:|--:|\n" + "\n".join(usage_rows))
            st.caption("List-price estimate; free-tier spend may be zero.")
        else:
            st.caption("Token usage appears after the first turn.")


def render_matches(result: VehicleSearchResult | None, *, key_prefix: str = "matches") -> None:
    vehicles = _vehicle_rows(result)
    if not vehicles:
        return

    st.subheader("Top matches")
    columns = st.columns(len(vehicles), gap="medium")
    for index, (column, vehicle, ranked) in enumerate(zip(columns, vehicles, result.vehicles, strict=True)):
        with column, st.container(border=True, key=f"vehicle_card_{key_prefix}_{index}", height="stretch", gap="small"):
            with st.container(key=f"vehicle_identity_{key_prefix}_{index}", gap=None):
                with st.container(key=f"vehicle_title_{key_prefix}_{index}", gap=None):
                    st.markdown(
                        (
                            f'<span class="vehicle-make">{escape(ranked.vehicle.make)}</span>'
                            f'<span class="vehicle-model">{escape(ranked.vehicle.model)}</span>'
                        ),
                        unsafe_allow_html=True,
                    )
                if vehicle["Papers"] == "Verified":
                    with st.container(key=f"vehicle_verified_{key_prefix}_{index}"):
                        st.markdown(":green[:material/check_circle:]")
                st.caption(f"{vehicle['Year']} · {vehicle['City']} · {vehicle['Body'].title()} body")

            with st.container(key=f"vehicle_metrics_{key_prefix}_{index}", gap="small"):
                price, kilometres = st.columns([3, 2], gap="medium", vertical_alignment="top")
                with price:
                    st.metric("Price", _format_price(vehicle["Price (INR)"]), border=False)
                with kilometres:
                    st.metric("KM driven", f"{vehicle['KM']:,}", border=False)

            with st.container(key=f"vehicle_specs_{key_prefix}_{index}", gap="small"):
                specs = st.columns([0.8, 1.2, 1.2], gap="small", vertical_alignment="top")
                payload_label = "Est. payload" if vehicle["Payload basis"] == "Estimated" else "Payload"
                payload_value = _format_weight(vehicle["Payload (kg)"])
                values = (
                    ("Fuel", vehicle["Fuel"]),
                    (payload_label, payload_value),
                    ("GVW", _format_weight(vehicle["GVW (kg)"])),
                )
                for spec, (label, value) in zip(specs, values, strict=True):
                    with spec:
                        st.metric(label, value, border=False, width="stretch")

            with st.container(key=f"vehicle_reason_{key_prefix}_{index}", gap="small"):
                st.metric("Why it fits", vehicle["Why this match"], border=False, width="stretch")
            st.link_button(
                "View specifications",
                vehicle["Specification source"],
                icon=":material/open_in_new:",
                width="content",
            )

    with st.expander("Compare every catalog field"):
        st.dataframe(
            vehicles,
            hide_index=True,
            width="stretch",
            column_config={
                "Price (INR)": st.column_config.NumberColumn(format="₹%d", width="small"),
                "KM driven": st.column_config.NumberColumn(format="%d km", width="small"),
                "Payload (kg)": st.column_config.NumberColumn(format="%d kg"),
                "GVW (kg)": st.column_config.NumberColumn(format="%d kg"),
                "Specification source": st.column_config.LinkColumn(display_text="Open source"),
            },
        )

    if result is not None and result.vehicles:
        ranking_rows = [
            {
                "Vehicle": f"{item.vehicle.make} {item.vehicle.model}",
                "Total": item.score.total,
                "Purpose": item.score.purpose,
                "Papers": item.score.papers_verified,
                "Budget": item.score.budget,
                "KM driven": item.score.km_driven,
                "Condition": item.score.condition,
                "Year": item.score.year,
            }
            for item in result.vehicles
        ]
        with st.expander("Why these ranked first"):
            st.caption(
                "All shown vehicles meet your filters. Their total combines the weighted signals below; "
                "higher is better."
            )
            st.dataframe(
                [
                    {
                        "Purpose fit": "30%",
                        "Verified papers": "15%",
                        "Within budget": "15%",
                        "Lower KM driven": "15%",
                        "Condition": "15%",
                        "Newer year": "10%",
                    }
                ],
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "If purpose or budget is not provided, its share is redistributed. Vivi may infer purpose and "
                "vehicle size from the use case; everything else must be stated."
            )
            st.caption("Score by vehicle")
            st.dataframe(
                ranking_rows,
                hide_index=True,
                width="stretch",
                column_config={
                    name: st.column_config.NumberColumn(format="%.3f") for name in ranking_rows[0] if name != "Vehicle"
                },
            )


def render_starter_questions(run_text: Callable[[str], None]) -> None:
    if st.session_state.messages:
        return

    with st.container(key="starter_questions"):
        st.caption("Not sure where to begin? Try one of these:")
        for index, question in enumerate(STARTER_QUESTIONS):
            if st.button(question, key=f"starter_question_{index}", width="content"):
                run_text(question)
                st.rerun()


def _reason(ranked: RankedVehicle, filters: SearchFilters) -> str:
    if filters.purpose and ranked.score.purpose > 0:
        return f"Listed for {filters.purpose.replace('_', ' ')}"
    if (
        filters.payload_min_kg
        and ranked.vehicle.payload_kg is not None
        and ranked.vehicle.payload_kg >= filters.payload_min_kg
    ):
        return f"Meets your {_format_weight(filters.payload_min_kg)} payload minimum"
    if filters.budget_max and ranked.vehicle.price_inr <= filters.budget_max:
        return f"Within your {_format_price(filters.budget_max)} budget"
    if filters.fuel and ranked.vehicle.fuel == filters.fuel:
        return f"Matches your {filters.fuel} preference"
    if ranked.vehicle.papers_verified:
        return "Verified papers"
    return f"{ranked.vehicle.condition.title()} condition"


def _vehicle_rows(result: VehicleSearchResult | None) -> list[dict]:
    if result is None:
        return []
    return [
        {
            "Make / Model": f"{ranked.vehicle.make} {ranked.vehicle.model}",
            "Year": ranked.vehicle.year,
            "Price (INR)": ranked.vehicle.price_inr,
            "KM": ranked.vehicle.km_driven,
            "Fuel": ranked.vehicle.fuel,
            "Payload (kg)": ranked.vehicle.payload_kg,
            "Payload basis": "Estimated" if ranked.vehicle.payload_is_estimated else "Manufacturer-listed",
            "GVW (kg)": ranked.vehicle.gvw_kg,
            "Body": ranked.vehicle.body_type,
            "City": ranked.vehicle.city,
            "Papers": "Verified" if ranked.vehicle.papers_verified else "Not verified",
            "Why this match": _reason(ranked, result.executed_filters),
            "Specification source": ranked.vehicle.spec_source_url,
        }
        for ranked in result.vehicles
    ]


def _display_value(name: str, value) -> str:
    if name in {"budget_min", "budget_max"}:
        return _format_price(int(value))
    if name in {"payload_min_kg", "gvw_min_kg"}:
        return f"{value:,.0f} kg"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value).replace("_", " ").title()


def _metric_label(name: str) -> str:
    return METRIC_LABELS.get(name, name.removesuffix("_ms").replace("_", " ").title())


def _format_duration(milliseconds: float) -> str:
    if milliseconds < 1_000:
        return f"{milliseconds:,.0f} ms"
    if milliseconds < 60_000:
        return f"{milliseconds / 1_000:,.1f} s"
    minutes, seconds = divmod(milliseconds / 1_000, 60)
    return f"{minutes:,.0f}m {seconds:02.0f}s"


def _format_cost(cost_inr: float | None) -> str:
    return f"₹{cost_inr:.4f}" if cost_inr is not None else "—"


def _format_price(price_inr: int) -> str:
    digits = str(abs(price_inr))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        pairs = []
        while head:
            pairs.append(head[-2:])
            head = head[:-2]
        digits = f"{','.join(reversed(pairs))},{tail}"
    sign = "-" if price_inr < 0 else ""
    return f"₹{sign}{digits}"


def _format_weight(weight_kg: int | None) -> str:
    return f"{weight_kg:,} kg" if weight_kg else "not listed"
