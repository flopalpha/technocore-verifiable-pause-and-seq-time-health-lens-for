"""Verifiable pause and seq-time health lens. Read-only helpers for safe writes."""

import hashlib
import json


def public_checksum(text):
    """Return sha256 hex of public text. No keys used."""
    if not isinstance(text, str):
        text = json.dumps(text, sort_keys=True)
    data = text.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def normalize_url(url):
    """Trim and lower a public pointer for fair compare."""
    s = str(url).strip()
    while s.endswith("/"):
        s = s[:-1]
    return s.lower()


def health_gate(health, max_lag=5):
    """Decide if a write suggestion is allowed. Returns allowed flag."""
    status = str(health.get("status", "unknown")).strip().lower()
    lag_raw = health.get("seq_lag", 0)
    try:
        lag = int(lag_raw)
    except (TypeError, ValueError):
        lag = 0
    if status != "ok":
        reason = "paused: health status is " + status
        return {"allowed": False, "paused": True, "reason": reason}
    if lag > max_lag:
        reason = "paused: seq lag " + str(lag) + " over limit " + str(max_lag)
        return {"allowed": False, "paused": True, "reason": reason}
    reason = "health ok with lag " + str(lag)
    return {"allowed": True, "paused": False, "reason": reason}


def filter_since(messages, since_seq):
    """Keep messages with seq above cursor. Pure list filter."""
    out = []
    for m in messages:
        try:
            seq = int(m.get("seq", 0))
        except (TypeError, ValueError, AttributeError):
            continue
        if seq > since_seq:
            out.append(m)
    return out


def seq_freshness(messages, now_seq, stall_threshold=10):
    """Summarize seq time and flag stalled heartbeats."""
    try:
        now = int(now_seq)
    except (TypeError, ValueError):
        now = 0
    max_seq = 0
    hb_seq = 0
    kinds = {}
    for m in messages:
        try:
            seq = int(m.get("seq", 0))
        except (TypeError, ValueError, AttributeError):
            continue
        if seq > max_seq:
            max_seq = seq
        kind = str(m.get("kind", "unknown"))
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "heartbeat" and seq > hb_seq:
            hb_seq = seq
    lag = now - max_seq
    if lag < 0:
        lag = 0
    if hb_seq == 0:
        hb_lag = now
    else:
        hb_lag = now - hb_seq
        if hb_lag < 0:
            hb_lag = 0
    stalled = lag > stall_threshold
    hb_stalled = hb_lag > stall_threshold
    if stalled:
        note = "stalled: lag " + str(lag) + " over " + str(stall_threshold)
    else:
        note = "fresh: lag " + str(lag) + " within " + str(stall_threshold)
    return {
        "now_seq": now,
        "max_seq": max_seq,
        "lag": lag,
        "stalled": stalled,
        "heartbeat_seq": hb_seq,
        "heartbeat_lag": hb_lag,
        "heartbeat_stalled": hb_stalled,
        "counts": kinds,
        "note": note,
    }


def explain_first_nonce_cost(nonce, base_cost=10, init_cost=40):
    """Explain first-nonce cost from public metadata only. No signing."""
    try:
        n = int(nonce)
    except (TypeError, ValueError):
        n = 0
    if n < 0:
        n = 0
    if n == 0:
        total = base_cost + init_cost
        parts = {"base": base_cost, "init": init_cost}
        note = "first nonce pays base plus init; later nonces pay base only"
    else:
        total = base_cost
        parts = {"base": base_cost, "init": 0}
        note = "repeat nonce pays base only; first nonce already paid init"
    return {"nonce": n, "total": total, "parts": parts, "note": note}


def preview_dedup(intents):
    """Show what a dedup intercept would block. No writes done."""
    seen = {}
    unique = []
    dups = []
    for item in intents:
        reg = str(item.get("registry", "")).strip()
        key = str(item.get("key", "")).strip()
        val = str(item.get("value", "")).strip()
        tag = (reg, key, val)
        if tag in seen:
            dups.append(item)
        else:
            seen[tag] = True
            unique.append(item)
    return {
        "unique": unique,
        "duplicates": dups,
        "would_write": len(unique),
        "would_block": len(dups),
    }


def pointer_consistency(ann_a, ann_b):
    """Check 2.6 and 2.8 pointers agree on KV mirror and Medium carrier."""
    kv_a = normalize_url(ann_a.get("kv", ""))
    kv_b = normalize_url(ann_b.get("kv", ""))
    med_a = normalize_url(ann_a.get("medium", ""))
    med_b = normalize_url(ann_b.get("medium", ""))
    body_a = str(ann_a.get("body", ""))
    body_b = str(ann_b.get("body", ""))
    sum_a = public_checksum(body_a)
    sum_b = public_checksum(body_b)
    kv_match = kv_a == kv_b and kv_a != ""
    med_match = med_a == med_b and med_a != ""
    body_match = sum_a == sum_b
    consistent = kv_match and med_match
    if consistent:
        details = "pointers agree on kv and medium"
    else:
        details = "pointers differ: kv_match=" + str(kv_match) + " medium_match=" + str(med_match)
    return {
        "consistent": consistent,
        "kv_match": kv_match,
        "medium_match": med_match,
        "body_match": body_match,
        "checksum_a": sum_a,
        "checksum_b": sum_b,
        "details": details,
    }


def advise_long_poll(poll_interval_s, wait_s, cursor_used, messages_per_min=6):
    """Suggest wait plus cursor and show read-load savings."""
    try:
        gap = float(poll_interval_s)
    except (TypeError, ValueError):
        gap = 2.0
    try:
        wait = float(wait_s)
    except (TypeError, ValueError):
        wait = 10.0
    if gap < 1.0:
        gap = 1.0
    if wait < 1.0:
        wait = 1.0
    before = 3600.0 / gap
    if cursor_used:
        after_gap = wait
        if after_gap < gap:
            after_gap = gap
        after = 3600.0 / after_gap
        suggestion = "keep wait " + str(wait_s) + " with since cursor"
    else:
        after = before
        suggestion = "add wait 10 with since cursor to cut reads"
    factor = 1.0
    if after > 0:
        factor = before / after
    return {
        "before_per_hour": round(before, 2),
        "after_per_hour": round(after, 2),
        "savings_factor": round(factor, 2),
        "suggestion": suggestion,
        "cursor_used": bool(cursor_used),
    }


def make_audit_entry(action, allowed, reason):
    """Build one audit record."""
    return {"action": str(action), "allowed": bool(allowed), "reason": str(reason)}


def write_audit_log(path, entries):
    """Write audit entries as JSON list."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, sort_keys=True)


def read_audit_log(path):
    """Read audit entries from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def parse_room_page(page):
    """Split a saved room page into messages and now_seq."""
    msgs = page.get("messages", [])
    now = page.get("now_seq", 0)
    try:
        now_int = int(now)
    except (TypeError, ValueError):
        now_int = 0
    if not isinstance(msgs, list):
        msgs = []
    return msgs, now_int
