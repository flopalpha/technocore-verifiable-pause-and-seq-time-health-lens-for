"""Command line for the health lens. Reads saved JSON, prints JSON result."""

import argparse
import json
import sys

import lens


def load_json(path):
    """Read a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_parser():
    """Build arg parser."""
    p = argparse.ArgumentParser(description="Verifiable pause and seq-time lens")
    p.add_argument("--health-file", default="", help="saved health JSON path")
    p.add_argument("--room-file", default="", help="saved room page JSON path")
    p.add_argument("--now-seq", default="0", help="current seq time")
    p.add_argument("--since", default="0", help="since cursor")
    p.add_argument("--max-lag", default="5", help="max allowed lag")
    p.add_argument("--audit-out", default="", help="where to write audit JSON")
    return p


def main(argv=None):
    """Run checks on saved files and print result JSON."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        now_seq = int(args.now_seq)
    except (TypeError, ValueError):
        now_seq = 0
    try:
        since = int(args.since)
    except (TypeError, ValueError):
        since = 0
    try:
        max_lag = int(args.max_lag)
    except (TypeError, ValueError):
        max_lag = 5
    result = {}
    audit = []
    if args.health_file:
        health = load_json(args.health_file)
        gate = lens.health_gate(health, max_lag)
        result["gate"] = gate
        audit.append(lens.make_audit_entry("write-suggestion", gate["allowed"], gate["reason"]))
    if args.room_file:
        page = load_json(args.room_file)
        msgs = page.get("messages", [])
        page_now = page.get("now_seq", now_seq)
        try:
            use_now = int(page_now)
        except (TypeError, ValueError):
            use_now = now_seq
        fresh = lens.seq_freshness(lens.filter_since(msgs, since), use_now)
        result["freshness"] = fresh
        audit.append(lens.make_audit_entry("freshness-check", True, fresh["note"]))
    if args.audit_out:
        lens.write_audit_log(args.audit_out, audit)
        result["audit_written"] = args.audit_out
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    main()
