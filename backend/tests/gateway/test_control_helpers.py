"""网关纯函数单测：子协议解析 / udid 拆解 / token 哈希

对应契约 §3（Sec-WebSocket-Protocol: ticket.<t>）、§7（udid =
"{agent_id}:{serial}"）、§2（token sha256 对 token_hash）。
"""

import hashlib

import pytest

from app.gateway.agent_ws import hash_token
from app.gateway.control_ws import pick_ticket_subprotocol, split_udid


# ── pick_ticket_subprotocol ───────────────────────────────────


def test_pick_ticket_single():
    assert pick_ticket_subprotocol("ticket.abc123") == "ticket.abc123"


def test_pick_ticket_among_multiple_with_spaces():
    # 逗号分隔 + 空白：原样返回命中的子协议（accept 回选要用同一字符串）
    assert pick_ticket_subprotocol("chat, ticket.abc , other") == "ticket.abc"


@pytest.mark.parametrize("header", [None, "", "chat", "ticket.", "ticketabc"])
def test_pick_ticket_missing_or_malformed(header):
    assert pick_ticket_subprotocol(header) is None


# ── split_udid ────────────────────────────────────────────────


def test_split_udid_ok():
    assert split_udid("3:ABC123") == (3, "ABC123")


def test_split_udid_serial_may_contain_colon():
    # 只按第一个冒号拆：serial 里出现冒号（如 tcpip ip:port）不截断
    assert split_udid("12:192.168.1.5:5555") == (12, "192.168.1.5:5555")


@pytest.mark.parametrize("udid", ["ABC123", ":ABC", "x:ABC", "3:", "", "-1:ABC"])
def test_split_udid_malformed(udid):
    assert split_udid(udid) is None


# ── hash_token ────────────────────────────────────────────────


def test_hash_token_sha256_hex():
    token = "tok-plain-123"
    assert hash_token(token) == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert len(hash_token(token)) == 64  # app_agent.token_hash 列宽（契约 §7）
