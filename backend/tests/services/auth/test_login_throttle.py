"""登录限流（login_throttle）与 auth_service.login 防武器化测试。

不依赖真实 Redis：用内存 FakeRedis（INCR/EXPIRE/SADD/SCARD/DELETE 最小实现）
替换 ``login_throttle.get_redis``；auth_service 侧用 stub 替换 user_crud 与
verify_password。
"""

from datetime import datetime, timedelta, timezone
from importlib import import_module
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.auth.user import UserStatus
from app.schemas.auth.login import LoginRequest
from app.services.auth import auth_service, login_throttle

# 包 __init__ 把 "auth_service" 属性重绑定为单例实例，遮蔽了子模块；
# 用 import_module 从 sys.modules 拿到真正的模块对象以便 monkeypatch。
auth_service_mod = import_module("app.services.auth.auth_service")


# ========================================
# 假 Redis
# ========================================


class FakeRedis:
    """最小内存 Redis（decode_responses=True 语义：字符串值）。"""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.sets: dict[str, set] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key):
        return self.kv.get(key)

    async def incr(self, key):
        self.kv[key] = str(int(self.kv.get(key, "0")) + 1)
        return int(self.kv[key])

    async def expire(self, key, seconds):
        self.ttls[key] = seconds
        return True

    async def sadd(self, key, *members):
        self.sets.setdefault(key, set()).update(members)
        return len(members)

    async def scard(self, key):
        return len(self.sets.get(key, set()))

    async def delete(self, *keys):
        n = 0
        for k in keys:
            n += int(self.kv.pop(k, None) is not None)
            n += int(self.sets.pop(k, None) is not None)
        return n


class BrokenRedis:
    """所有操作都抛异常，模拟 Redis 故障。"""

    async def get(self, key):
        raise ConnectionError("redis down")

    async def incr(self, key):
        raise ConnectionError("redis down")

    async def expire(self, key, seconds):
        raise ConnectionError("redis down")

    async def sadd(self, key, *members):
        raise ConnectionError("redis down")

    async def scard(self, key):
        raise ConnectionError("redis down")

    async def delete(self, *keys):
        raise ConnectionError("redis down")


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(login_throttle, "get_redis", lambda: fake)
    return fake


# ========================================
# login_throttle 单元测试
# ========================================


class TestCheckAllowed:
    async def test_ip_attempts_over_limit_raises_429(self, fake_redis):
        """单 IP 窗口内尝试次数超限 → 429。"""
        for _ in range(login_throttle.IP_MAX_ATTEMPTS + 1):
            await login_throttle.record_attempt("1.1.1.1")
        with pytest.raises(HTTPException) as exc:
            await login_throttle.check_allowed("1.1.1.1", "alice")
        assert exc.value.status_code == 429
        assert exc.value.detail == "登录尝试过于频繁，请稍后再试"

    async def test_pair_failures_over_limit_raises_429(self, fake_redis):
        """同 IP+账号 失败次数达上限 → 429。"""
        for _ in range(login_throttle.PAIR_MAX_FAILURES):
            await login_throttle.record_failure("1.1.1.1", "alice")
        with pytest.raises(HTTPException) as exc:
            await login_throttle.check_allowed("1.1.1.1", "alice")
        assert exc.value.status_code == 429

    async def test_within_limits_allowed(self, fake_redis):
        """窗口内未超限 → 放行。"""
        await login_throttle.record_attempt("1.1.1.1")
        await login_throttle.record_failure("1.1.1.1", "alice")
        await login_throttle.check_allowed("1.1.1.1", "alice")  # 不抛异常

    async def test_other_ip_same_account_not_blocked(self, fake_redis):
        """pair 限流是 IP+账号 维度：同账号换 IP 不被 429（由 IP 维度兜底）。"""
        for _ in range(login_throttle.PAIR_MAX_FAILURES):
            await login_throttle.record_failure("1.1.1.1", "alice")
        await login_throttle.check_allowed("2.2.2.2", "alice")  # 不抛异常

    async def test_keys_have_window_ttl(self, fake_redis):
        """计数 key 设置了窗口 TTL。"""
        await login_throttle.record_attempt("1.1.1.1")
        await login_throttle.record_failure("1.1.1.1", "alice")
        assert fake_redis.ttls["login:att:ip:1.1.1.1"] == login_throttle.WINDOW_SECONDS
        assert (
            fake_redis.ttls["login:fail:pair:1.1.1.1:alice"]
            == login_throttle.WINDOW_SECONDS
        )


class TestRecordFailure:
    async def test_two_distinct_ips_not_distributed(self, fake_redis):
        """2 个不同 IP 失败 → 不构成分布式攻击。"""
        assert await login_throttle.record_failure("1.1.1.1", "alice") is False
        assert await login_throttle.record_failure("2.2.2.2", "alice") is False

    async def test_three_distinct_ips_is_distributed(self, fake_redis):
        """第 3 个不同 IP 失败 → 构成分布式攻击。"""
        await login_throttle.record_failure("1.1.1.1", "alice")
        await login_throttle.record_failure("2.2.2.2", "alice")
        assert await login_throttle.record_failure("3.3.3.3", "alice") is True

    async def test_same_ip_repeated_failures_not_distributed(self, fake_redis):
        """同一 IP 反复失败（ distinct 只有 1）→ 不构成分布式攻击。"""
        for _ in range(4):
            assert await login_throttle.record_failure("1.1.1.1", "alice") is False


class TestClear:
    async def test_clear_removes_pair_and_failips(self, fake_redis):
        """clear 删除 pair 计数与 failips 集合。"""
        await login_throttle.record_failure("1.1.1.1", "alice")
        await login_throttle.record_failure("2.2.2.2", "alice")
        await login_throttle.clear("1.1.1.1", "alice")
        # failips 集合已删：新 IP 失败后 distinct 从 1 重新计数
        assert await login_throttle.record_failure("3.3.3.3", "alice") is False
        # pair 计数已删：check_allowed 不再因旧计数 429
        await login_throttle.check_allowed("1.1.1.1", "alice")


class TestFailOpen:
    """Redis 故障时所有函数 fail-open：放行 / 返回 False，绝不阻塞登录。"""

    @pytest.fixture(autouse=True)
    def _broken_redis(self, monkeypatch):
        monkeypatch.setattr(login_throttle, "get_redis", lambda: BrokenRedis())

    async def test_check_allowed_passes_when_redis_down(self):
        await login_throttle.check_allowed("1.1.1.1", "alice")  # 不抛异常

    async def test_record_attempt_swallows_errors(self):
        await login_throttle.record_attempt("1.1.1.1")  # 不抛异常

    async def test_record_failure_returns_false_when_redis_down(self):
        assert await login_throttle.record_failure("1.1.1.1", "alice") is False

    async def test_clear_swallows_errors(self):
        await login_throttle.clear("1.1.1.1", "alice")  # 不抛异常


# ========================================
# auth_service.login 集成向测试（stub user_crud / verify_password）
# ========================================


def _make_user(**overrides) -> SimpleNamespace:
    user = SimpleNamespace(
        id=1,
        username="alice",
        email="alice@example.com",
        real_name="Alice",
        avatar=None,
        role_codes=["user"],
        permissions=[],
        password_hash="hashed",
        status=UserStatus.ACTIVE,
        locked_until=None,
        login_fail_count=0,
        last_login_at=None,
        last_login_ip=None,
    )
    for k, v in overrides.items():
        setattr(user, k, v)
    return user


class _StubUserCrud:
    """模拟 user_crud：就地修改 user 对象，记录 lock_user 调用次数。"""

    def __init__(self, user) -> None:
        self.user = user
        self.lock_calls = 0

    async def get_by_account(self, db, *, account):
        return self.user

    async def increment_login_fail_count(self, db, *, user):
        user.login_fail_count += 1
        return user

    async def lock_user(self, db, *, user, lock_minutes=30):
        self.lock_calls += 1
        user.status = UserStatus.LOCKED
        lock_time = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
        user.locked_until = int(lock_time.timestamp())
        return user

    async def update_status(self, db, *, user, status):
        user.status = status
        return user

    async def reset_login_fail_count(self, db, *, user):
        user.login_fail_count = 0
        user.locked_until = None
        return user

    async def update_login_info(self, db, *, user, ip_address=None):
        user.last_login_ip = ip_address
        user.login_fail_count = 0
        user.locked_until = None
        return user


@pytest.fixture
def login_env(monkeypatch, fake_redis):
    """组装 auth_service.login 测试环境：stub user_crud + 可控 verify_password。"""

    def setup(user, *, password_ok: bool) -> _StubUserCrud:
        stub = _StubUserCrud(user)
        monkeypatch.setattr(auth_service_mod, "user_crud", stub)
        monkeypatch.setattr(
            auth_service_mod, "verify_password", lambda p, h: password_ok
        )
        return stub

    return setup


def _login_req(password: str = "whatever") -> LoginRequest:
    return LoginRequest(account="alice", password=password)


class TestAuthServiceLoginThrottle:
    async def test_single_ip_five_failures_never_locks(self, login_env):
        """防武器化核心：单 IP 连续失败 5 次 → 全部 401，账号不被锁定。"""
        user = _make_user()
        stub = login_env(user, password_ok=False)
        for _ in range(5):
            with pytest.raises(HTTPException) as exc:
                await auth_service.login(
                    None, obj_in=_login_req(), client_ip="1.1.1.1"
                )
            assert exc.value.status_code == 401
            assert exc.value.detail == "账号或密码错误"
        assert stub.lock_calls == 0
        assert user.status == UserStatus.ACTIVE
        assert user.login_fail_count == 5

    async def test_single_ip_sixth_attempt_is_429_not_lock(self, login_env):
        """单 IP 第 6 次尝试被 pair 限流 429（而不是锁账号）。"""
        user = _make_user()
        stub = login_env(user, password_ok=False)
        for _ in range(5):
            with pytest.raises(HTTPException):
                await auth_service.login(
                    None, obj_in=_login_req(), client_ip="1.1.1.1"
                )
        with pytest.raises(HTTPException) as exc:
            await auth_service.login(None, obj_in=_login_req(), client_ip="1.1.1.1")
        assert exc.value.status_code == 429
        assert stub.lock_calls == 0

    async def test_distributed_attack_locks_account(self, login_env):
        """3 个不同 IP 各失败数次（单 IP 未达 pair 上限）→ 触发 lock_user。"""
        user = _make_user()
        stub = login_env(user, password_ok=False)
        for ip in ("1.1.1.1", "2.2.2.2"):
            for _ in range(2):
                with pytest.raises(HTTPException) as exc:
                    await auth_service.login(
                        None, obj_in=_login_req(), client_ip=ip
                    )
                assert exc.value.status_code == 401
        assert stub.lock_calls == 0  # 2 个 IP 时还不锁

        # 第 3 个不同 IP 的失败 → distinct IP = 3 → 锁定
        with pytest.raises(HTTPException) as exc:
            await auth_service.login(None, obj_in=_login_req(), client_ip="3.3.3.3")
        assert exc.value.status_code == 401
        assert stub.lock_calls == 1
        assert user.status == UserStatus.LOCKED
        assert user.locked_until is not None

    async def test_expired_lock_unlocks_and_resets_fail_count(self, login_env):
        """锁过期自动解锁时清零 login_fail_count（失败也生效：清零后再 +1）。"""
        past = int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())
        user = _make_user(
            status=UserStatus.LOCKED, locked_until=past, login_fail_count=5
        )
        stub = login_env(user, password_ok=False)
        with pytest.raises(HTTPException) as exc:
            await auth_service.login(None, obj_in=_login_req(), client_ip="1.1.1.1")
        assert exc.value.status_code == 401
        assert user.status == UserStatus.ACTIVE
        # 清零后本次失败 +1 → 1；若未清零会是 6
        assert user.login_fail_count == 1
        assert stub.lock_calls == 0

    async def test_success_clears_throttle_and_records_ip(self, login_env):
        """登录成功：清理限流状态、last_login_ip 记录真实客户端 IP。"""
        user = _make_user()
        stub = login_env(user, password_ok=False)
        # 先失败 4 次（pair 计数 = 4）
        for _ in range(4):
            with pytest.raises(HTTPException):
                await auth_service.login(
                    None, obj_in=_login_req(), client_ip="1.1.1.1"
                )
        # 密码输对 → 成功，pair 计数被 clear
        login_env(user, password_ok=True)
        resp = await auth_service.login(None, obj_in=_login_req(), client_ip="9.9.9.9")
        assert resp.access_token
        assert user.last_login_ip == "9.9.9.9"

        # 再失败 1 次：若 pair 未清零会是第 5 次 → 429；清零后应为 401
        login_env(user, password_ok=False)
        with pytest.raises(HTTPException) as exc:
            await auth_service.login(None, obj_in=_login_req(), client_ip="1.1.1.1")
        assert exc.value.status_code == 401
        assert stub.lock_calls == 0
