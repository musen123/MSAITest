"""在线判定纯逻辑单测（契约 §7）

agent：心跳 ≤30s=online、≤60s=stale、否则 offline；无心跳=offline。
device：online = 所属 agent online 且 adb state=='device'。
"""

from datetime import datetime, timedelta

import pytest

from app.services.app_device.service import (
    AGENT_ONLINE_WINDOW_S,
    AGENT_STALE_WINDOW_S,
    agent_status,
    device_online,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 7, 1, 12, 0, 0)


def _hb(seconds_ago: float) -> datetime:
    return _NOW - timedelta(seconds=seconds_ago)


class TestAgentStatus:
    def test_no_heartbeat_is_offline(self):
        assert agent_status(None, now=_NOW) == "offline"

    def test_fresh_heartbeat_is_online(self):
        assert agent_status(_hb(0), now=_NOW) == "online"
        assert agent_status(_hb(10), now=_NOW) == "online"

    def test_boundary_30s_is_online(self):
        assert agent_status(_hb(AGENT_ONLINE_WINDOW_S), now=_NOW) == "online"

    def test_between_30_and_60_is_stale(self):
        assert agent_status(_hb(31), now=_NOW) == "stale"
        assert agent_status(_hb(45), now=_NOW) == "stale"

    def test_boundary_60s_is_stale(self):
        assert agent_status(_hb(AGENT_STALE_WINDOW_S), now=_NOW) == "stale"

    def test_beyond_60s_is_offline(self):
        assert agent_status(_hb(61), now=_NOW) == "offline"
        assert agent_status(_hb(3600), now=_NOW) == "offline"

    def test_future_heartbeat_treated_as_online(self):
        # 时钟漂移：心跳时间在"未来"按刚心跳处理，不误判下线
        assert agent_status(_hb(-5), now=_NOW) == "online"


class TestDeviceOnline:
    def test_online_agent_and_device_state(self):
        assert device_online("online", "device") is True

    def test_online_agent_bad_adb_state(self):
        assert device_online("online", "offline") is False
        assert device_online("online", "unauthorized") is False

    def test_stale_or_offline_agent_never_online(self):
        assert device_online("stale", "device") is False
        assert device_online("offline", "device") is False
