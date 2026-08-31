"""Persistent IMAP UID checkpoints for non-destructive incremental collectors."""

import fcntl
import json
import os
from pathlib import Path


def _state_path(save_folder, collector_name):
    return Path(save_folder) / ".email_state" / f"{collector_name}.json"


def acquire_collector_lock(save_folder, collector_name):
    path = _state_path(save_folder, collector_name).with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def _uidvalidity(mail):
    _code, values = mail.response("UIDVALIDITY")
    if not values:
        return None
    value = values[-1]
    return value.decode() if isinstance(value, bytes) else str(value)


def _all_uids(mail):
    status, data = mail.uid("search", None, "ALL")
    if status != "OK" or not data:
        raise RuntimeError(f"Unable to search IMAP UIDs: {status}")
    return [int(value) for value in data[0].split()]


def begin_incremental_run(mail, save_folder, collector_name):
    path = _state_path(save_folder, collector_name)
    validity = _uidvalidity(mail)
    all_uids = _all_uids(mail)
    highest_uid = max(all_uids, default=0)
    state = None
    if path.exists():
        with path.open() as handle:
            state = json.load(handle)
    if not state or state.get("uidvalidity") != validity:
        save_checkpoint(path, validity, highest_uid)
        return [], path, validity, highest_uid, True
    last_uid = int(state.get("last_uid", 0))
    return [uid for uid in all_uids if uid > last_uid], path, validity, highest_uid, False


def save_checkpoint(path, uidvalidity, last_uid):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as handle:
        json.dump({"uidvalidity": uidvalidity, "last_uid": int(last_uid)}, handle)
    os.replace(temporary, path)
