"""Acquire Citizen/IFTTT emails without LLM interpretation."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from extractor_modules.email.email_filters import is_citizen_notification
from extractor_modules.email.get_emails import connect_to_gmail_imap, fetch_emails_by_uid
from extractor_modules.email.imap_checkpoint import acquire_collector_lock, begin_incremental_run, save_checkpoint
from extractor_modules.email.raw_email import normalize_email, write_raw_batch
from extractor_modules.common.config import get_config

def process_emails_to_csv(username: str, password: str, output_dir: str = ".", state_root: str = ".", max_results: int = 500, subject_filter: str | None = None):
    """Persist raw messages; retained name keeps scheduler compatibility."""
    collector_lock = acquire_collector_lock(state_root, "citizen")
    if collector_lock is None:
        logging.info("Another Citizen email extraction is running; skipping")
        return []

    with connect_to_gmail_imap(username, password) as mail:
        uids, state_path, uidvalidity, highest_uid, bootstrapped = begin_incremental_run(
            mail, state_root, "citizen"
        )
        if bootstrapped:
            logging.info("Initialized Citizen checkpoint at UID %s", highest_uid)
            return []
        selected_uids = uids[:max_results]
        emails = fetch_emails_by_uid(mail, selected_uids)
        if len(emails) != len(selected_uids):
            raise RuntimeError("Not every selected Citizen email could be fetched; checkpoint unchanged")
        emails = [item for item in emails if is_citizen_notification(item)]
        if subject_filter:
            needle = subject_filter.lower()
            emails = [item for item in emails if needle in item.get("subject", "").lower()]
        records = [normalize_email(item, "citizen") for item in emails]
        path = write_raw_batch(records, output_dir)
        if path:
            logging.info("Saved %d raw Citizen emails to %s", len(records), path)
        if selected_uids:
            save_checkpoint(state_path, uidvalidity, selected_uids[-1])
        return records


def pull_data(chosen_sensors=None, exclude_sensors=None):
    config = get_config()
    account = config["email_acc_info"]
    day = datetime.now().strftime("%Y%m%d")
    output_dir = os.path.join(config["save_folder"], "citizen_data", day)
    return process_emails_to_csv(
        account["email"], account["password"], output_dir, config["save_folder"], max_results=100
    )


if __name__ == "__main__":
    pull_data()
