from pathlib import Path

from extractor_modules.email.imap_checkpoint import begin_incremental_run, save_checkpoint


class FakeMailbox:
    def __init__(self, uids):
        self.uids = uids

    def response(self, name):
        assert name == "UIDVALIDITY"
        return "OK", [b"42"]

    def uid(self, command, *_args):
        assert command == "search"
        return "OK", [" ".join(map(str, self.uids)).encode()]


def test_checkpoint_bootstraps_without_replaying_existing_mail(tmp_path: Path):
    mailbox = FakeMailbox([10, 11])

    uids, state_path, validity, highest, bootstrapped = begin_incremental_run(
        mailbox, tmp_path, "twitter"
    )

    assert bootstrapped is True
    assert uids == []
    assert highest == 11
    assert state_path.exists()


def test_checkpoint_returns_only_new_stable_uids(tmp_path: Path):
    state = tmp_path / ".email_state" / "citizen.json"
    save_checkpoint(state, "42", 11)

    uids, *_ = begin_incremental_run(FakeMailbox([10, 11, 14, 15]), tmp_path, "citizen")

    assert uids == [14, 15]


def test_email_collectors_do_not_contain_delete_operations():
    module_root = Path("extractor_modules/email")
    source = "\n".join(
        (module_root / name).read_text(encoding="utf-8")
        for name in ("get_emails.py", "generate_csv.py", "citizen_scrape.py")
    )

    assert "mail.expunge" not in source
    assert "\\\\Deleted" not in source
