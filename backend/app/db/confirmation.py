"""Interactive guard for one-off database writes."""

from sqlalchemy.engine import make_url


def confirm_database_write(database_url: str, *, action: str, expected: str, input_fn=None) -> None:
    host = make_url(database_url).host or "unknown"
    print(f"Target database host: {host}")
    print(f"This will {action} synthetic demo data or passwords in that database.")
    read_input = input_fn or input
    if read_input(f"Type {expected} to continue: ") != expected:
        raise SystemExit("Confirmation did not match; no database changes were made.")
