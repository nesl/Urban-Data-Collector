import pytest

from extractor_modules.operations.scheduler import main, parse_cron_expr, run_command


def test_parse_cron_expr():
    assert parse_cron_expr("*/15 * * * *")["minute"] == "*/15"


def test_parse_cron_expr_rejects_wrong_field_count():
    with pytest.raises(ValueError, match="5 fields"):
        parse_cron_expr("0 * *")


def test_runner_reports_missing_command():
    try:
        main(["--cron", "0 * * * *"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("missing command should be rejected")


def test_run_command_does_not_raise_for_failed_child():
    run_command(["sh", "-c", "exit 7"])
