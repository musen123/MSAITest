"""Midscene 报告签名 URL（P4-D 独立报告源）

报告是第三方带 JS 的自包含 HTML（用 localStorage 等 API），平台同源 iframe
会让报告 JS 摸到平台 JWT（G9 红线），严格 sandbox 又掐死其水合（不透明源
访问 localStorage 即抛 SecurityError → 空白）。解法＝**独立源**：报告经
网关（:8889，与平台跨端口=跨源）+ 短时效 HMAC 签名 URL 提供——报告在
自己的源里全量水合，拿不到平台任何凭据；签名解决 <iframe src> 带不了
Authorization 头的问题。

业务 API 签发（build_report_url），网关校验（verify_report_sig），
共享 settings.SECRET_KEY，两进程同库同配置。
"""

import hashlib
import hmac
import time

from app.core.config import settings

# 签名 URL 有效期（打开报告弹窗即签即用，10 分钟富余）
REPORT_URL_TTL_S = 600


def _sign(execution_id: int, exp: int) -> str:
    msg = f"app-report:{execution_id}:{exp}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def build_report_url(execution_id: int) -> str:
    """签发报告访问 URL（网关源，短时效）。"""
    exp = int(time.time()) + REPORT_URL_TTL_S
    base = settings.APP_REPORT_PUBLIC_BASE.rstrip("/")
    return f"{base}/api/v1/app/reports/{execution_id}?exp={exp}&sig={_sign(execution_id, exp)}"


def verify_report_sig(execution_id: int, exp: int, sig: str) -> bool:
    """网关侧校验：未过期且 HMAC 恒时比较通过。"""
    if exp < int(time.time()):
        return False
    return hmac.compare_digest(_sign(execution_id, exp), sig)
