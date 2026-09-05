from time import sleep

from vehicle_search_utils.operation import OperationLogContext


def test_completed_extra_contains_numeric_duration():
    operation = OperationLogContext(operation="vehicle_search")

    sleep(0.001)
    extra = operation.completed_extra(status="succeeded")

    assert extra["duration_ms"] > 0
    assert isinstance(extra["duration_ms"], float)
    assert extra["status"] == "succeeded"
    assert extra["started_at_utc"] == operation.started_at_utc
    assert extra["ended_at_utc"]
