from unittest.mock import Mock

import pytest
from vehicle_search_utils import timing
from vehicle_search_utils.operation import format_duration


def test_format_duration():
    assert format_duration(0.125) == "125.0 ms"
    assert format_duration(1.25) == "1.250 s"
    assert format_duration(3661) == "1 h 01 m 01 s"


def test_timed_run_logs_success():
    logger = Mock()

    @timing.timed_run(
        logger=logger,
        name="data_generation",
    )
    def generate() -> int:
        return 42

    assert generate() == 42
    started_extra = logger.info.call_args_list[0].kwargs["extra"]
    assert logger.info.call_args_list[0].args == ("timed_run_started",)
    assert started_extra["operation"] == "data_generation"
    assert started_extra["status"] == "started"
    assert started_extra["started_at_utc"]

    completed_extra = logger.info.call_args_list[1].kwargs["extra"]
    assert logger.info.call_args_list[1].args == ("timed_run_completed",)
    assert completed_extra["operation"] == "data_generation"
    assert completed_extra["operation_id"] == started_extra["operation_id"]
    assert completed_extra["status"] == "succeeded"
    assert completed_extra["duration"].endswith("ms")


def test_timed_run_logs_failure():
    logger = Mock()

    @timing.timed_run(
        logger=logger,
    )
    def generate() -> None:
        raise ValueError("generation failed")

    with pytest.raises(ValueError, match="generation failed"):
        generate()

    failed_extra = logger.exception.call_args.kwargs["extra"]
    assert logger.exception.call_args.args == ("timed_run_failed",)
    assert failed_extra["operation"] == "generate"
    assert failed_extra["status"] == "failed"
    assert failed_extra["error_type"] == "ValueError"
