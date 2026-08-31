"""Run one extractor command on a cron schedule in a long-lived container."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

LOG = logging.getLogger(__name__)


def parse_cron_expr(expr: str) -> dict[str, str]:
    """Parse the five cron fields accepted by APScheduler."""
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(
            "Cron expression must have 5 fields: minute hour day month day_of_week"
        )
    return dict(zip(("minute", "hour", "day", "month", "day_of_week"), fields))


def run_command(command: list[str]) -> None:
    """Run a collector once without terminating its scheduler on failure."""
    LOG.info("Starting scheduled command: %s", " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode:
        LOG.error("Scheduled command exited with status %d", result.returncode)
    else:
        LOG.info("Scheduled command completed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a command repeatedly using a five-field cron expression"
    )
    parser.add_argument("--cron", required=True, help='for example: "*/15 * * * *"')
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="command to run; place it after --",
    )
    args = parser.parse_args(argv)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")

    from apscheduler.schedulers.blocking import BlockingScheduler

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cron = parse_cron_expr(args.cron)
    scheduler = BlockingScheduler(timezone=os.environ.get("TZ", "UTC"))
    scheduler.add_job(
        run_command,
        "cron",
        args=[command],
        id="collector",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        **cron,
    )
    LOG.info("Scheduled %s with cron %s", " ".join(command), args.cron)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
