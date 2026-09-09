"""
Unit tests for sympose.slack_heartbeat — the Slack daemon liveness file
that GET /api/slack/status reads (ADR-082).
"""

import json
import time

from sympose import slack_heartbeat as hb


def test_no_file_reads_offline(tmp_path):
    status = hb.read_status(str(tmp_path))
    assert status["state"] == "offline"
    assert status["last_seen"] is None
    assert status["personas"] == []


def test_fresh_heartbeat_reads_connected(tmp_path):
    hb.write_heartbeat(str(tmp_path), ["samantha", "grace"])
    status = hb.read_status(str(tmp_path))
    assert status["state"] == "connected"
    assert status["personas"] == ["grace", "samantha"]  # sorted
    assert status["last_seen"] is not None
    assert (tmp_path / hb.HEARTBEAT_FILENAME).exists()


def test_ages_into_stale_then_offline(tmp_path):
    hb.write_heartbeat(str(tmp_path), ["samantha"])
    now = time.time()
    assert hb.read_status(str(tmp_path), now=now + hb.STALE_AFTER + 5)["state"] == "stale"
    off = hb.read_status(str(tmp_path), now=now + hb.OFFLINE_AFTER + 5)
    assert off["state"] == "offline"
    # last_seen survives so the UI can still say "last seen 3m ago"
    assert off["last_seen"] is not None
    assert off["personas"] == []


def test_clear_removes_the_file(tmp_path):
    hb.write_heartbeat(str(tmp_path), ["samantha"])
    hb.clear_heartbeat(str(tmp_path))
    assert not (tmp_path / hb.HEARTBEAT_FILENAME).exists()
    assert hb.read_status(str(tmp_path))["state"] == "offline"


def test_corrupt_file_reads_offline(tmp_path):
    (tmp_path / hb.HEARTBEAT_FILENAME).write_text("{not json")
    assert hb.read_status(str(tmp_path))["state"] == "offline"


def test_write_is_atomic_no_tmp_left_behind(tmp_path):
    hb.write_heartbeat(str(tmp_path), ["samantha"])
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != hb.HEARTBEAT_FILENAME]
    assert leftovers == []
    # and the file is valid JSON with the expected shape
    data = json.loads((tmp_path / hb.HEARTBEAT_FILENAME).read_text())
    assert set(data) == {"ts", "pid", "personas"}
