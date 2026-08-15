"""Dependency-light schedule parsing and reconciliation helpers."""


def parse_cron_expr(expr: str):
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(
            "Cron expression must have 5 fields: minute hour day month day_of_week"
        )
    return dict(zip(("minute", "hour", "day", "month", "day_of_week"), fields))


def apply_scheduling(extract_function, config_params, scheduler, source_name):
    source_prefix = source_name + "_"
    for job in scheduler.get_jobs():
        if job.id.startswith(source_prefix) and job.id not in config_params:
            scheduler.remove_job(job.id)
            print(f"Removed job {job.id} as it is no longer in the config")

    for case_name, params in config_params.items():
        include_ids, exclude_ids, cron_expr = params
        scheduler.add_job(
            extract_function,
            "cron",
            id=case_name,
            replace_existing=True,
            args=[include_ids, exclude_ids],
            **cron_expr,
        )
        print(case_name, include_ids, exclude_ids)


def parse_source_data(source_data, source):
    config_params = {}
    default_exclude = []
    for case_name, values in source_data.items():
        if case_name != "default":
            case_ids = values["ids"]
            config_params[f"{source}_{case_name}"] = [
                case_ids,
                [],
                parse_cron_expr(values["frequency"]),
            ]
            default_exclude.extend(case_ids)

    config_params[f"{source}_default"] = [
        [],
        default_exclude,
        parse_cron_expr(source_data["default"]["frequency"]),
    ]
    return config_params
