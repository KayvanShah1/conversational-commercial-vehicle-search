import pytest
from pydantic import ValidationError
from vehicle_search_agent.models import SearchField, SearchFilters, SlotPatch, merge_slot_patch


def test_fuel_is_normalized_at_the_state_boundary():
    filters = SearchFilters(fuel="diesel")

    assert filters.fuel == "Diesel"


def test_slot_patch_changes_only_the_corrected_field():
    current = SearchFilters(budget_max=500_000, city="Pune", fuel="Diesel")

    updated, changed = merge_slot_patch(current, SlotPatch(fuel="CNG"))

    assert updated == SearchFilters(budget_max=500_000, city="Pune", fuel="CNG")
    assert changed == [SearchField.fuel]


def test_slot_patch_clears_an_explicitly_removed_field():
    current = SearchFilters(city="Pune", fuel="Diesel")

    updated, changed = merge_slot_patch(current, SlotPatch(clear_fields=[SearchField.city]))

    assert updated == SearchFilters(fuel="Diesel")
    assert changed == [SearchField.city]


def test_merged_patch_revalidates_the_budget_range():
    with pytest.raises(ValueError, match="budget_min cannot exceed budget_max"):
        merge_slot_patch(SearchFilters(budget_max=500_000), SlotPatch(budget_min=600_000))


def test_unknown_filter_names_cannot_be_silently_ignored():
    with pytest.raises(ValidationError, match="price_max"):
        SlotPatch.model_validate({"price_max": 500_000})


def test_finite_catalog_fields_reject_values_outside_the_tool_schema():
    with pytest.raises(ValidationError, match="vehicle_category"):
        SlotPatch(vehicle_category="small_truck")
