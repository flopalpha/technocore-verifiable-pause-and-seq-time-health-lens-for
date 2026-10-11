"""Tests for lens. Uses only tempfile for files."""

import json
import tempfile
import unittest

import lens


class LensTest(unittest.TestCase):
    def test_health_gate_blocks_when_degraded(self):
        gate = lens.health_gate({"status": "degraded", "seq_lag": 0})
        self.assertFalse(gate["allowed"])
        self.assertTrue(gate["paused"])

    def test_health_gate_allows_when_ok(self):
        gate = lens.health_gate({"status": "ok", "seq_lag": 1}, max_lag=5)
        self.assertTrue(gate["allowed"])
        self.assertFalse(gate["paused"])

    def test_health_gate_blocks_on_lag(self):
        gate = lens.health_gate({"status": "ok", "seq_lag": 20}, max_lag=5)
        self.assertFalse(gate["allowed"])

    def test_seq_freshness_flags_stall(self):
        msgs = [{"seq": 90, "kind": "heartbeat"}, {"seq": 91, "kind": "guidance"}]
        fresh = lens.seq_freshness(msgs, 110, stall_threshold=10)
        self.assertTrue(fresh["stalled"])
        self.assertTrue(fresh["heartbeat_stalled"])

    def test_seq_freshness_fresh(self):
        msgs = [{"seq": 108, "kind": "heartbeat"}]
        fresh = lens.seq_freshness(msgs, 110, stall_threshold=10)
        self.assertFalse(fresh["stalled"])

    def test_filter_since(self):
        msgs = [{"seq": 1}, {"seq": 5}, {"seq": 9}]
        out = lens.filter_since(msgs, 4)
        self.assertEqual([m["seq"] for m in out], [5, 9])

    def test_first_nonce_cost(self):
        first = lens.explain_first_nonce_cost(0, base_cost=10, init_cost=40)
        repeat = lens.explain_first_nonce_cost(3, base_cost=10, init_cost=40)
        self.assertEqual(first["total"], 50)
        self.assertEqual(repeat["total"], 10)

    def test_dedup_preview(self):
        intents = [
            {"registry": "main", "key": "a", "value": "1"},
            {"registry": "main", "key": "a", "value": "1"},
            {"registry": "main", "key": "b", "value": "2"},
        ]
        res = lens.preview_dedup(intents)
        self.assertEqual(res["would_write"], 2)
        self.assertEqual(res["would_block"], 1)

    def test_pointer_consistency_ok(self):
        a = {"kv": "https://example.invalid/mirror", "medium": "https://example.invalid/post", "body": "hello"}
        b = {"kv": "https://example.invalid/mirror/", "medium": "https://example.invalid/post", "body": "hello"}
        res = lens.pointer_consistency(a, b)
        self.assertTrue(res["consistent"])
        self.assertTrue(res["kv_match"])

    def test_pointer_consistency_diff(self):
        a = {"kv": "https://example.invalid/one", "medium": "https://example.invalid/post", "body": "hello"}
        b = {"kv": "https://example.invalid/two", "medium": "https://example.invalid/post", "body": "hello"}
        res = lens.pointer_consistency(a, b)
        self.assertFalse(res["consistent"])

    def test_long_poll_advisor(self):
        res = lens.advise_long_poll(2, 10, False)
        self.assertIn("since cursor", res["suggestion"])
        res2 = lens.advise_long_poll(2, 10, True)
        self.assertGreater(res2["savings_factor"], 1.0)

    def test_audit_log_roundtrip(self):
        entries = [lens.make_audit_entry("write-suggestion", False, "paused")]
        with tempfile.TemporaryDirectory() as tmp:
            path = tmp + "/audit.json"
            lens.write_audit_log(path, entries)
            back = lens.read_audit_log(path)
        self.assertEqual(back, entries)

    def test_parse_room_page(self):
        page = {"messages": [{"seq": 3, "kind": "heartbeat"}], "now_seq": 5}
        msgs, now = lens.parse_room_page(page)
        self.assertEqual(now, 5)
        self.assertEqual(len(msgs), 1)


if __name__ == "__main__":
    unittest.main()
