import json

from extractor_modules.scheduling import (
    apply_scheduling,
    parse_cron_expr,
    parse_source_data,
)


class Job:
    def __init__(self, job_id):
        self.id = job_id


class Scheduler:
    def __init__(self, job_ids=()):
        self.jobs = {job_id: Job(job_id) for job_id in job_ids}
        self.added = []

    def get_jobs(self):
        return list(self.jobs.values())

    def remove_job(self, job_id):
        del self.jobs[job_id]

    def add_job(self, function, trigger, **kwargs):
        self.added.append((function, trigger, kwargs))
        self.jobs[kwargs["id"]] = Job(kwargs["id"])


def test_all_checked_in_schedules_parse():
    for filename in ("default.json",):
        with open(f"extractor_modules/config/{filename}", encoding="utf-8") as stream:
            config = json.load(stream)
        for source, source_data in config.items():
            parsed = parse_source_data(source_data, source)
            assert parsed


def test_cron_parser_rejects_nonstandard_field_count():
    assert parse_cron_expr("*/15 * * * *")["minute"] == "*/15"


def test_source_refresh_does_not_remove_other_sources_jobs():
    scheduler = Scheduler(("cctv_old", "weather_default", "schedule_all"))
    config = {"cctv_default": [[], [], parse_cron_expr("*/15 * * * *")]}

    apply_scheduling(lambda *_: None, config, scheduler, "cctv")

    assert "cctv_old" not in scheduler.jobs
    assert "cctv_default" in scheduler.jobs
    assert "weather_default" in scheduler.jobs
    assert "schedule_all" in scheduler.jobs
