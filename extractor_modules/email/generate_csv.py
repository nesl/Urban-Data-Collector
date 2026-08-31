"""Acquire Twitter/X notification emails without interpreting their content."""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime

from extractor_modules.email.get_emails import connect_to_gmail_imap, fetch_emails_by_uid
from extractor_modules.email.imap_checkpoint import acquire_collector_lock, begin_incremental_run, save_checkpoint
from extractor_modules.email.raw_email import normalize_email, write_raw_batch
from extractor_modules.common.config import get_config


def _is_twitter_notification(email: dict) -> bool:
    text = f"{email.get('sender', '')} {email.get('subject', '')}".lower()
    return "twitter" in text or "x.com" in text


def collect_raw_twitter(*, limit: int = 100, output_root: str | None = None) -> int:
    config = get_config()
    state_root = config["save_folder"]
    output_root = output_root or state_root
    account = config["email_acc_info"]
    collector_lock = acquire_collector_lock(state_root, "twitter")
    if collector_lock is None:
        logging.info("Another Twitter email extraction is running; skipping")
        return 0

    with connect_to_gmail_imap(account["email"], account["password"]) as mail:
        uids, state_path, uidvalidity, highest_uid, bootstrapped = begin_incremental_run(
            mail, state_root, "twitter"
        )
        if bootstrapped:
            logging.info("Initialized Twitter checkpoint at UID %s", highest_uid)
            return 0

        selected_uids = uids[:limit]
        emails = fetch_emails_by_uid(mail, selected_uids)
        if len(emails) != len(selected_uids):
            raise RuntimeError("Not every selected Twitter email could be fetched; checkpoint unchanged")

        records = [normalize_email(item, "twitter") for item in emails if _is_twitter_notification(item)]
        day = datetime.now().strftime("%Y%m%d")
        path = write_raw_batch(records, os.path.join(output_root, "twitter_data", day))
        if path:
            logging.info("Saved %d raw Twitter emails to %s", len(records), path)
        if selected_uids:
            save_checkpoint(state_path, uidvalidity, selected_uids[-1])
        return len(records)


def pull_data(chosen_sensors=None, exclude_sensors=None):
    return collect_raw_twitter()


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire raw Twitter/X notification emails")
    parser.add_argument("-l", "--limit", type=int, default=100)
    parser.add_argument("-p", "--production", help="Override the output root")
    parser.add_argument("--scheduled", action="store_true", help="Use the configured output root")
    parser.add_argument("-d", "--delete", action="store_true", help="Deprecated and ignored")
    args = parser.parse_args()
    if args.delete:
        logging.warning("--delete is deprecated and ignored; emails remain in the inbox")
    collect_raw_twitter(limit=args.limit, output_root=args.production)


if __name__ == "__main__":
    main()
