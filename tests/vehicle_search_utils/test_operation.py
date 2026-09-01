from time import sleep

from vehicle_search_utils.operation import OperationLogContext


def test_operation_context_has_stable_identity():
    operation = OperationLogContext(operation="vehicle_search")

    first = operation.extra()
    second = operation.extra()

    assert first["operation"] == "vehicle_search"
    assert first["operation_id"]
    assert first["operation_id"] == second["operation_id"]


def test_completed_extra_contains_numeric_duration():
    operation = OperationLogContext(operation="vehicle_search")

    sleep(0.001)
    extra = operation.completed_extra(status="succeeded")

    assert extra["duration_ms"] > 0
    assert isinstance(extra["duration_ms"], float)
    assert extra["status"] == "succeeded"
    assert extra["started_at_utc"] == operation.started_at_utc
    assert extra["ended_at_utc"]


def test_started_extra_does_not_contain_duration():
    operation = OperationLogContext(operation="vehicle_search")

    extra = operation.started_extra(status="started")

    assert "duration_ms" not in extra
    assert "ended_at_utc" not in extra
    assert extra["started_at_utc"] == operation.started_at_utc
