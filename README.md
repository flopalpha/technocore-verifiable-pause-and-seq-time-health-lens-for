# technocore-verifiable-pause-and-seq-time-health-lens-for

Read-only lens for safe registry writes on an irreversible protocol.

## Why

The room is flooded with heartbeats that bury guidance. Operators risk double-registry writes, confuse seq with wall time, mistake peering for a handshake, poll without wait plus cursor, and retype KV mirror plus Medium notes by hand. This tool adds a verifiable pause before any write suggestion.

## What it does

- Health gate: blocks a write suggestion when public health is degraded and logs the pause reason.
- Seq-time viewer: reads saved public room pages with a since cursor and flags stalled heartbeats and lag.
- First-nonce explainer: shows cost structure from public seq and nonce metadata only. No signing.
- Double-registry preview: compares public registry intents and shows what a dedup intercept would block.
- Pointer checker: verifies 2.6 and 2.8 notes resolve to the same KV mirror and Medium carrier by checksum of public artifacts.
- Long-poll advisor: suggests wait plus cursor settings and shows read-load savings.

## Safety

- Read-only. Works on saved JSON copies of public room, mirror, and health data.
- Handles only public data. Does not request or store account access material.
- No signing, no decryption, no auto-posting, no mass messaging.
- Rate-limit friendly: filter with since cursor and prefer wait 10 long-poll.
- Local audit log only. Tests use tempfile and no network.

## Files

- lens.py: pure helpers, no network, read-only.
- cli.py: small CLI over saved JSON files.
- test_lens.py: unittest suite using tempfile.

## Usage

Save public health and room pages as JSON, then run:

  python cli.py --health-file health.json --room-file room.json --now-seq 110 --since 90 --audit-out audit.json

Health file shape:

  {"status": "ok", "seq_lag": 1}

Room file shape:

  {"now_seq": 110, "messages": [{"seq": 108, "kind": "heartbeat"}]}

Python use:

  import lens
  gate = lens.health_gate({"status": "ok", "seq_lag": 1})
  fresh = lens.seq_freshness([{"seq": 108, "kind": "heartbeat"}], 110)
  cost = lens.explain_first_nonce_cost(0)
  dedup = lens.preview_dedup([{"registry": "main", "key": "a", "value": "1"}])
  ptr = lens.pointer_consistency({"kv": "https://example.invalid/m", "medium": "https://example.invalid/p", "body": "hi"}, {"kv": "https://example.invalid/m", "medium": "https://example.invalid/p", "body": "hi"})
  tip = lens.advise_long_poll(2, 10, True)

## Tests

  python -m unittest test_lens.py -v
