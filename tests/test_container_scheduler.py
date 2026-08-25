from extractor_modules.container_scheduler import main, run_command


def test_runner_reports_missing_command():
    try:
        main(["--cron", "0 * * * *"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("missing command should be rejected")


def test_run_command_does_not_raise_for_failed_child():
    run_command(["sh", "-c", "exit 7"])
