#!/usr/bin/env python3
"""Standalone consumer for one tenant's `leads.<tenant_id>` topic.

Deliberately independent of the backend (ADR-0026): this is what an external
client integrating with the product would write on their own, and importing
anything from `backend/` here would mean the contract does not stand alone.
"""
import argparse
import json
import sys
import uuid

from confluent_kafka import Consumer


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True, help="Tenant UUID; the topic is leads.<tenant>")
    parser.add_argument(
        "--bootstrap-servers", default="localhost:9094",
        help="Kafka bootstrap servers (default: %(default)s, the host-mapped port)",
    )
    parser.add_argument(
        "--from-beginning", action="store_true",
        help="Replay everything retained instead of only new messages",
    )
    parser.add_argument("--sasl-username", required=True, help="Issued by POST /agents/integration-credential")
    parser.add_argument("--sasl-password", required=True, help="Issued by POST /agents/integration-credential")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    topic = f"leads.{args.tenant}"

    consumer = Consumer({
        "bootstrap.servers": args.bootstrap_servers,
        "security.protocol": "SASL_PLAINTEXT",
        "sasl.mechanism": "SCRAM-SHA-256",
        "sasl.username": args.sasl_username,
        "sasl.password": args.sasl_password,
        # A fresh group per run, not a fixed one: reusing a group id would
        # make a second --from-beginning resume from where the first run's
        # committed offset left off instead of truly replaying from zero.
        "group.id": f"test-consumer-{args.tenant}-{uuid.uuid4().hex[:8]}",
        "auto.offset.reset": "earliest" if args.from_beginning else "latest",
    })
    consumer.subscribe([topic])

    mode = "from the beginning" if args.from_beginning else "from now"
    # flush=True on every line: this tool exists to show delivery happening,
    # and stdout is fully buffered the moment it is piped or redirected.
    print(f"Listening on {topic} ({mode}). Ctrl+C to stop.", flush=True)

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Error: {msg.error()}", file=sys.stderr, flush=True)
                continue

            headers = dict(msg.headers() or [])
            event_type = headers.get("event_type", b"?").decode()
            payload = json.loads(msg.value())
            print(f"[{event_type}] key={msg.key().decode()} {json.dumps(payload, indent=2)}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
