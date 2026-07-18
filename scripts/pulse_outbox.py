#!/usr/bin/env python3
"""R16 operational CLI for the Receptionist -> Pulse booking-event outbox.

The command never prints the webhook signing secret. Destructive schema rollback is
blocked while publishing is enabled and requires an explicit confirmation token.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import engine  # noqa: E402
from integrations.pulse_booking_events import (  # noqa: E402
    PulseBookingOutbox,
    drop_pulse_outbox_tables,
    ensure_pulse_outbox_tables,
    publisher_config_from_settings,
)


def _tables_present() -> dict[str, bool]:
    tables = set(inspect(engine).get_table_names())
    return {
        "pulse_booking_versions": "pulse_booking_versions" in tables,
        "pulse_booking_event_outbox": "pulse_booking_event_outbox" in tables,
    }


def _service() -> PulseBookingOutbox:
    config = publisher_config_from_settings()
    config.validate()
    return PulseBookingOutbox(engine, config)


def _pending_count() -> int:
    if not _tables_present()["pulse_booking_event_outbox"]:
        return 0
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM pulse_booking_event_outbox "
                    "WHERE status <> 'delivered'"
                )
            ).scalar_one()
        )


def command_schema_upgrade(_: argparse.Namespace) -> int:
    ensure_pulse_outbox_tables(engine)
    print(json.dumps({"ok": True, "action": "schema_upgrade", "tables": _tables_present()}))
    return 0


def command_schema_status(_: argparse.Namespace) -> int:
    print(
        json.dumps(
            {
                "ok": True,
                "action": "schema_status",
                "tables": _tables_present(),
                "pending_events": _pending_count(),
            },
            sort_keys=True,
        )
    )
    return 0


def command_schema_downgrade(args: argparse.Namespace) -> int:
    config = publisher_config_from_settings()
    if config.enabled:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "disable_publisher_before_schema_downgrade",
                }
            ),
            file=sys.stderr,
        )
        return 2
    pending = _pending_count()
    if pending and not args.allow_pending_loss:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "pending_events_exist",
                    "pending_events": pending,
                    "remedy": "deliver/export pending events or pass --allow-pending-loss",
                }
            ),
            file=sys.stderr,
        )
        return 3
    if args.confirm != "R16-DROP-OUTBOX":
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "confirmation_required",
                    "required": "--confirm R16-DROP-OUTBOX",
                }
            ),
            file=sys.stderr,
        )
        return 4
    drop_pulse_outbox_tables(engine)
    print(json.dumps({"ok": True, "action": "schema_downgrade", "tables": _tables_present()}))
    return 0


def command_status(_: argparse.Namespace) -> int:
    ensure_pulse_outbox_tables(engine)
    print(json.dumps(_service().status_summary(), ensure_ascii=False, sort_keys=True))
    return 0


def command_dispatch(args: argparse.Namespace) -> int:
    ensure_pulse_outbox_tables(engine)
    results = _service().dispatch_due(limit=args.limit)
    print(
        json.dumps(
            {
                "ok": True,
                "processed": len(results),
                "results": [
                    {
                        "event_id": item.event_id,
                        "status": item.status,
                        "attempt_count": item.attempt_count,
                        "http_status": item.http_status,
                        "error_category": item.error_category,
                    }
                    for item in results
                ],
                "secret_exposed": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def command_retry(args: argparse.Namespace) -> int:
    ensure_pulse_outbox_tables(engine)
    count = _service().retry_failed(event_id=args.event_id)
    print(
        json.dumps(
            {
                "ok": True,
                "retried": count,
                "event_id": args.event_id,
                "event_identity_preserved": True,
                "secret_exposed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Operate the R16 Pulse booking outbox")
    commands = root.add_subparsers(dest="command", required=True)

    p = commands.add_parser("schema-upgrade")
    p.set_defaults(func=command_schema_upgrade)
    p = commands.add_parser("schema-status")
    p.set_defaults(func=command_schema_status)
    p = commands.add_parser("schema-downgrade")
    p.add_argument("--confirm", default="")
    p.add_argument("--allow-pending-loss", action="store_true")
    p.set_defaults(func=command_schema_downgrade)
    p = commands.add_parser("status")
    p.set_defaults(func=command_status)
    p = commands.add_parser("dispatch")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=command_dispatch)
    p = commands.add_parser("retry")
    p.add_argument("--event-id", default=None)
    p.set_defaults(func=command_retry)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
