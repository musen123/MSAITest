"""隧道控制帧协议 v1 编解码单测（契约 §2）

锁住：
- decode_frame 只放行「JSON 对象 + 非空字符串 type」；
- 出站帧构造符合契约字段（v=1、registered 带 heartbeat_interval_s=10 等）；
- rpc_payload 规约：ok 严格为 True 才算成功，失败缺 error 自动补 internal；
- new_rpc_id 形如 r-<uuid4> 且逐次唯一。

纯净：不起 WS 服务、不碰 DB/Redis。
"""

import json
import uuid

import pytest

from app.gateway.frames import (
    HEARTBEAT_INTERVAL_S,
    FrameError,
    decode_frame,
    error_frame,
    new_rpc_id,
    registered_frame,
    rpc_payload,
    rpc_request_frame,
)


# ── decode_frame ──────────────────────────────────────────────


def test_decode_frame_ok():
    frame = decode_frame(
        '{"v":1,"type":"heartbeat","ts":1700000000,"devices":[]}'
    )
    assert frame["type"] == "heartbeat"
    assert frame["devices"] == []


def test_decode_frame_bad_json():
    with pytest.raises(FrameError):
        decode_frame("{not json")


@pytest.mark.parametrize("raw", ['[1,2]', '"x"', "123", "null"])
def test_decode_frame_not_object(raw):
    with pytest.raises(FrameError):
        decode_frame(raw)


@pytest.mark.parametrize(
    "raw",
    [
        '{"v":1}',                # 缺 type
        '{"v":1,"type":123}',     # type 非字符串
        '{"v":1,"type":""}',      # type 空串
        '{"v":1,"type":null}',    # type 为 null
    ],
)
def test_decode_frame_bad_type(raw):
    with pytest.raises(FrameError):
        decode_frame(raw)


# ── 出站帧构造 ────────────────────────────────────────────────


def test_registered_frame_shape():
    assert registered_frame(3) == {
        "v": 1,
        "type": "registered",
        "agent_id": 3,
        "heartbeat_interval_s": HEARTBEAT_INTERVAL_S,
    }
    assert HEARTBEAT_INTERVAL_S == 10  # 契约 §2 固定值


def test_rpc_request_frame_shape():
    frame = rpc_request_frame("r-1", "ping", {"a": 1}, 15000)
    assert frame == {
        "v": 1,
        "type": "rpc_request",
        "id": "r-1",
        "cmd": "ping",
        "params": {"a": 1},
        "timeout_ms": 15000,
    }


def test_rpc_request_frame_params_none_becomes_empty_dict():
    assert rpc_request_frame("r-1", "ping", None, 1000)["params"] == {}


def test_error_frame_shape():
    frame = error_frame("bad_frame", "非法 JSON")
    assert frame == {"v": 1, "type": "error", "code": "bad_frame", "message": "非法 JSON"}


def test_frames_are_json_serializable():
    for frame in (
        registered_frame(1),
        rpc_request_frame(new_rpc_id(), "ping", {}, 1000),
        error_frame("x", "y"),
    ):
        json.dumps(frame)


# ── rpc_payload 规约 ──────────────────────────────────────────


def test_rpc_payload_ok():
    payload = rpc_payload(
        {"v": 1, "type": "rpc_response", "id": "r-1", "ok": True, "result": {"pong": True}}
    )
    assert payload == {"ok": True, "result": {"pong": True}}


def test_rpc_payload_ok_missing_result_defaults_empty():
    assert rpc_payload({"ok": True}) == {"ok": True, "result": {}}


def test_rpc_payload_error_passthrough():
    err = {"code": "not_implemented", "message": "S1 填充"}
    payload = rpc_payload({"ok": False, "error": err})
    assert payload == {"ok": False, "error": err}


@pytest.mark.parametrize(
    "frame",
    [
        {"ok": False},                    # 失败缺 error
        {"ok": False, "error": {}},       # error 空对象
        {"ok": False, "error": "boom"},   # error 非对象
        {"ok": "true"},                   # ok 非布尔（严格 is True）
        {},                               # ok 缺失
    ],
)
def test_rpc_payload_failure_fills_internal_error(frame):
    payload = rpc_payload(frame)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "internal"


# ── new_rpc_id ────────────────────────────────────────────────


def test_new_rpc_id_format_and_unique():
    ids = {new_rpc_id() for _ in range(100)}
    assert len(ids) == 100
    for rpc_id in ids:
        assert rpc_id.startswith("r-")
        uuid.UUID(rpc_id[2:])  # 合法 uuid，非法会抛
