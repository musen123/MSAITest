"""
登录限流 / 防锁定武器化

基于 Redis 固定窗口计数（INCR + EXPIRE）实现两层限流与分布式攻击检测：

  - IP 维度尝试限流：``login:att:ip:{ip}``，窗口内尝试次数超过
    ``IP_MAX_ATTEMPTS`` → 抛 429；
  - IP+账号 维度失败限流：``login:fail:pair:{ip}:{account}``，窗口内失败次数
    达到 ``PAIR_MAX_FAILURES`` → 抛 429；
  - 分布式攻击检测：``login:failips:{account}`` 集合记录该账号的失败来源 IP，
    ``record_failure`` 返回 distinct IP 数是否达到 ``DISTINCT_IP_THRESHOLD``，
    由调用方（auth_service.login）据此决定是否锁定账号——
    单个 IP 反复输错密码只会被 pair 限流 429，不会把账号锁掉（防 DoS 武器化）。

设计原则：fail-open —— Redis 故障只记 warning 日志并放行 / 返回 False，
绝不让限流组件故障导致正常用户无法登录。
"""

import logging

from fastapi import HTTPException, status

from app.ai_core.runtime.event_bus import get_redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# ========================================
# 阈值（模块级常量，值取自 settings，可用 .env 覆盖）
# ========================================
WINDOW_SECONDS: int = settings.login_throttle_window_seconds
IP_MAX_ATTEMPTS: int = settings.login_throttle_ip_max_attempts
PAIR_MAX_FAILURES: int = settings.login_throttle_pair_max_failures
DISTINCT_IP_THRESHOLD: int = settings.login_lock_distinct_ip_threshold

# 失败来源 IP 集合 TTL：30 分钟（比计数窗口更长，覆盖跨窗口的慢速分布式攻击）
_FAILIPS_TTL_SECONDS: int = 1800

_TOO_MANY_DETAIL = "登录尝试过于频繁，请稍后再试"


def _ip_attempts_key(ip: str) -> str:
    return f"login:att:ip:{ip}"


def _pair_fail_key(ip: str, account: str) -> str:
    return f"login:fail:pair:{ip}:{account}"


def _failips_key(account: str) -> str:
    return f"login:failips:{account}"


async def check_allowed(ip: str, account: str) -> None:
    """
    登录前置限流检查。

    IP 尝试计数超上限或 IP+账号 失败计数达上限时抛 HTTPException 429；
    Redis 读取出错时放行（fail-open）。

    Args:
        ip: 客户端 IP
        account: 登录账号（用户名或邮箱）

    Raises:
        HTTPException: 429 登录尝试过于频繁
    """
    try:
        redis = get_redis()
        ip_count = await redis.get(_ip_attempts_key(ip))
        if ip_count is not None and int(ip_count) > IP_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=_TOO_MANY_DETAIL,
            )
        pair_count = await redis.get(_pair_fail_key(ip, account))
        if pair_count is not None and int(pair_count) >= PAIR_MAX_FAILURES:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=_TOO_MANY_DETAIL,
            )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 —— fail-open：Redis 故障不阻塞登录
        logger.warning("登录限流检查失败，放行: %s: %s", type(e).__name__, e)


async def record_attempt(ip: str) -> None:
    """
    记录一次登录尝试（IP 维度计数 +1，窗口 TTL）。

    Redis 出错仅记 warning（fail-open）。

    Args:
        ip: 客户端 IP
    """
    try:
        redis = get_redis()
        key = _ip_attempts_key(ip)
        await redis.incr(key)
        await redis.expire(key, WINDOW_SECONDS)
    except Exception as e:  # noqa: BLE001
        logger.warning("记录登录尝试失败: %s: %s", type(e).__name__, e)


async def record_failure(ip: str, account: str) -> bool:
    """
    记录一次密码失败：IP+账号 计数 +1（窗口 TTL），并把 IP 记入该账号的
    失败来源集合（30 分钟 TTL）。

    Args:
        ip: 客户端 IP
        account: 登录账号（用户名或邮箱）

    Returns:
        bool: 该账号的 distinct 失败来源 IP 数是否达到锁定阈值
              （True = 构成分布式攻击，调用方可锁定账号）；
              Redis 出错返回 False（fail-open，不误锁账号）。
    """
    try:
        redis = get_redis()
        pair_key = _pair_fail_key(ip, account)
        await redis.incr(pair_key)
        await redis.expire(pair_key, WINDOW_SECONDS)
        failips_key = _failips_key(account)
        await redis.sadd(failips_key, ip)
        await redis.expire(failips_key, _FAILIPS_TTL_SECONDS)
        distinct = int(await redis.scard(failips_key))
        return distinct >= DISTINCT_IP_THRESHOLD
    except Exception as e:  # noqa: BLE001
        logger.warning("记录登录失败计数失败: %s: %s", type(e).__name__, e)
        return False


async def clear(ip: str, account: str) -> None:
    """
    登录成功后清理该 IP+账号 的失败计数与该账号的失败来源 IP 集合。

    Redis 出错仅记 warning（fail-open）。

    Args:
        ip: 客户端 IP
        account: 登录账号（用户名或邮箱）
    """
    try:
        redis = get_redis()
        await redis.delete(_pair_fail_key(ip, account), _failips_key(account))
    except Exception as e:  # noqa: BLE001
        logger.warning("清理登录限流状态失败: %s: %s", type(e).__name__, e)
