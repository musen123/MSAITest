"""
中间件

实现：
  - auth_middleware：解析 Bearer Token，把 user_id / username 写入 request.state
  - access_log_middleware：访问日志中间件，记录每个 HTTP 请求的方法/路径/状态码/耗时/IP/用户，
    错误时额外记录响应体（脱敏后）。
    同时把非 GET 的业务请求**入库**到 sys_operation_log（操作日志审计）。
"""

import asyncio
import logging
import re
import time
import traceback
from typing import Awaitable, Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.core.security import verify_token
from app.crud.auth import user_crud
from app.crud.auth.operation_log import operation_log_crud
from app.db.session import async_session

logger = logging.getLogger(__name__)

# 不记录访问日志的路径（高频/无业务价值）
_EXCLUDE_PATHS = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/uploads",
    "/",
)

# 操作日志入库排除前缀（只过滤掉完全无业务价值的路径，其余业务 API 都入库）
_LOG_EXCLUDE_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/uploads",
)

# 敏感字段脱敏：匹配 "key":"value" 或 "key": "value"，value 替换为 ***
_SENSITIVE_FIELDS = ("password", "token", "secret", "api_key", "authorization", "access_token", "refresh_token")
_SENSITIVE_PATTERN = re.compile(
    r'("(?:%s)"\s*:\s*)("[^"]*"|\d+|true|false|null)' % "|".join(_SENSITIVE_FIELDS),
    re.IGNORECASE,
)


def _mask_sensitive(text: str) -> str:
    """对 JSON 字符串中的敏感字段做脱敏"""
    if not text:
        return text
    return _SENSITIVE_PATTERN.sub(r'\1"***"', text)


# ==================== 操作日志：模块/动作推断 ====================

# 路径前缀 → 中文模块名（**长前缀在前**，避免 /users 被 /users/llm-configes 抢占）
_MODULE_PREFIXES: list[tuple[str, str]] = [
    ("/api/v1/users/llm-configs", "大模型配置"),
    ("/api/v1/users", "用户管理"),
    ("/api/v1/roles", "角色管理"),
    ("/api/v1/logs/operation-logs", "操作日志"),
    ("/api/v1/projects", "项目管理"),
    ("/api/v1/auth/login", "认证授权"),
    ("/api/v1/auth", "认证授权"),
    ("/api/v1/bugs", "缺陷管理"),
    ("/api/v1/chat", "对话会话"),
    ("/api/v1/func-test", "功能测试"),
    ("/api/v1/api-test", "接口测试"),
    ("/api/v1/web-test", "Web测试"),
    ("/api/v1/knowledge", "知识库"),
    ("/api/v1/reports", "测试报告"),
    ("/api/v1/test-environment", "测试环境"),
]

# HTTP 方法 → 操作日志枚举值（写入数据库，与 sys_operation_log.action 枚举对齐）
# 实际写库的 enum: login/logout/create/update/delete/query/export/import
_ACTION_VALUES: dict[str, str] = {
    "GET": "query",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}

# HTTP 方法 → 中文动作（用于生成可读的描述）
_ACTION_LABELS: dict[str, str] = {
    "GET": "查询",
    "POST": "创建",
    "PUT": "更新",
    "PATCH": "更新",
    "DELETE": "删除",
}


def _should_record_operation(method: str, path: str) -> bool:
    """是否需要将本次请求写入操作日志表"""
    if path.startswith(_LOG_EXCLUDE_PREFIXES):
        return False
    # GET 请求不入审计表（避免表爆炸），保留在访问日志中
    if method.upper() == "GET":
        return False
    return True


def _infer_module(path: str) -> str:
    """从 URL 路径推断模块名"""
    for prefix, name in _MODULE_PREFIXES:
        if path.startswith(prefix):
            return name
    return "系统管理"


def _build_description(method: str, path: str) -> str:
    """生成操作描述，例如：创建用户、更新角色、删除项目"""
    action_label = _ACTION_LABELS.get(method.upper(), "操作")

    # 去掉 /api/vN 前缀
    clean = re.sub(r"^/api/v\d+", "", path)
    # 去掉末尾纯数字 ID（如 /users/123）
    clean = re.sub(r"/\d+(/?$)", r"\1", clean)
    # 取剩余非空段
    parts = [p for p in clean.split("/") if p and not p.startswith("{")]

    if parts:
        # 把英文资源段转中文（仅做最小映射，复杂场景可后续扩展）
        resource_map = {
            "users": "用户",
            "roles": "角色",
            "permissions": "权限",
            "projects": "项目",
            "members": "成员",
            "modules": "模块",
            "interfaces": "接口",
            "test-cases": "用例",
            "test-suites": "套件",
            "test-tasks": "任务",
            "environments": "环境",
            "databases": "数据库",
            "functions": "函数",
            "variables": "变量",
            "executions": "执行记录",
            "documents": "文档",
            "requirements": "需求",
            "conversations": "会话",
            "actions": "操作",
            "histories": "历史",
            "business-flows": "业务流程",
            "case-data": "用例数据",
            "overview": "概览",
            "login": "登录",
            "logout": "登出",
            "options": "选项",
            "stats": "统计",
        }
        zh_parts = [resource_map.get(p.lower(), p) for p in parts]
        return f"{action_label}{''.join(zh_parts)}"
    return f"{action_label}{_infer_module(path)}"


async def _write_operation_log(
    *,
    user_id: Optional[int],
    username: Optional[str],
    method: str,
    path: str,
    query_string: Optional[str],
    status_code: int,
    duration_ms: float,
    ip: str,
    user_agent: Optional[str],
) -> None:
    """异步将操作日志写入 sys_operation_log 表

    任何异常都被吞掉并打到 logger.warn，避免日志写入失败影响主请求。
    """
    try:
        # action 存枚举值（与 OperationLog.Action 对齐），description 存中文可读描述
        action_enum = _ACTION_VALUES.get(method.upper(), method.lower())
        module = _infer_module(path)
        description = _build_description(method, path)

        # request_params：合并 query string（避免在中间件读 body 造成重复消费）
        request_params = query_string or None
        if request_params:
            request_params = _mask_sensitive(request_params)

        async with async_session() as db:
            await operation_log_crud.create(
                db,
                obj_in={
                    "user_id": user_id,
                    "username": username,
                    "module": module,
                    "action": action_enum,
                    "description": description,
                    "request_method": method.upper(),
                    "request_url": path,
                    "request_params": request_params,
                    "response_status": status_code,
                    "ip_address": ip,
                    "user_agent": user_agent,
                    "execution_time": int(duration_ms),
                },
            )
    except Exception as e:
        logger.warning("写入操作日志失败: %s: %s", type(e).__name__, e)


async def _read_response_body(response) -> tuple[bytes | None, Response | None]:
    """
    读取响应体的字节内容。

    返回 (body_bytes, replacement_response)：
      - body_bytes: 响应体字节；读取失败时为 None
      - replacement_response: 当原响应被消费了 body、需要替换时返回新的 Response；
        调用方应将返回值赋给变量 `response` 再 return。

    支持两种响应：
      - 普通 Response（如 JSONResponse）：用 `await response.body()` 读取后重新构造 Response
      - StreamingResponse：用 `body_iterator` 聚合 chunks
    """
    # 1) 普通 Response —— 有 `body` 属性，调用后会消费
    if hasattr(response, "body") and not _is_streaming(response):
        try:
            body_bytes = await response.body()
            new_resp = Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            return body_bytes, new_resp
        except Exception as e:
            logger.warning("读取错误响应体失败: %s: %s", type(e).__name__, e)
            return None, None

    # 2) StreamingResponse —— 聚合所有 chunk
    try:
        chunks: list[bytes] = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            chunks.append(chunk)
        body_bytes = b"".join(chunks)
        # 重新构造 Response（body_iterator 已消费）
        new_resp = Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=getattr(response, "media_type", None),
        )
        return body_bytes, new_resp
    except Exception as e:
        logger.warning("读取流式响应体失败: %s: %s", type(e).__name__, e)
        return None, None


def _is_streaming(response) -> bool:
    """判断是否为流式响应（Starlette 的 StreamingResponse / _StreamingResponse）"""
    cls_name = type(response).__name__
    return "Streaming" in cls_name


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "-"


async def auth_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """
    认证中间件

    从请求头中获取 token 并验证用户身份，将用户信息存储到 request.state 中。
    必须在依赖用户信息的中间件之前执行。
    """
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            user_id = verify_token(token, token_type="access")
            if user_id:
                async with async_session() as db:
                    user = await user_crud.get(db, id=int(user_id))
                    if user:
                        request.state.user_id = user.id
                        request.state.username = user.username
        except Exception as e:
            logger.warning("认证中间件失败: %s: %s", type(e).__name__, e)

    response = await call_next(request)
    return response


async def access_log_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """
    访问日志中间件

    记录每个 HTTP 请求的 method / path / status / 耗时 / IP / 用户。
    错误请求（status >= 400）额外记录响应体前 500 字符（脱敏后）。
    未捕获异常时记录 traceback 并以 500 响应返回。

    非 GET 的业务请求额外**入库**到 sys_operation_log。

    注意：依赖 auth_middleware 先把 user_id/username 写入 request.state。
    注册顺序决定了执行顺序（最后注册的最先执行），auth_middleware 必须
    在本中间件之前注册，以便本中间件能在 call_next 之后拿到 user 信息。
    """
    path = request.url.path

    # 排除路径直接放行
    if path in _EXCLUDE_PATHS or path.startswith("/uploads/") or path.startswith("/docs"):
        return await call_next(request)

    method = request.method
    ip = _client_ip(request)
    user_agent = request.headers.get("User-Agent")
    query_string = str(request.url.query) if request.url.query else None

    start_time = time.time()
    status_code = 500
    error_message: str | None = None
    response_body_preview: str | None = None

    try:
        response = await call_next(request)
        status_code = response.status_code

        # 仅错误请求读取响应体
        if status_code >= 400:
            body_bytes, restore_response = await _read_response_body(response)
            if body_bytes is not None:
                body_text = body_bytes.decode("utf-8", errors="replace")
                # 截取前 500 字符后脱敏
                response_body_preview = _mask_sensitive(body_text[:500])
                if restore_response is not None:
                    response = restore_response

        duration_ms = (time.time() - start_time) * 1000

        # ⚠️ 必须在 call_next 之后读取：此时 auth_middleware 已经把
        # request.state.user_id / username 填充好了。
        user_id = getattr(request.state, "user_id", None)
        username = getattr(request.state, "username", None)
        user_label = username if username else (str(user_id) if user_id else "-")

        _emit_access_log(
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            ip=ip,
            user_label=user_label,
            error_message=error_message,
            body_preview=response_body_preview,
        )

        # 操作日志入库（非 GET 的业务请求）
        if _should_record_operation(method, path):
            try:
                asyncio.create_task(
                    _write_operation_log(
                        user_id=user_id,
                        username=username,
                        method=method,
                        path=path,
                        query_string=query_string,
                        status_code=status_code,
                        duration_ms=duration_ms,
                        ip=ip,
                        user_agent=user_agent,
                    )
                )
            except RuntimeError as e:
                # 无事件循环时回退到同步 await（理论上不会发生）
                logger.warning("无法调度操作日志后台任务: %s", e)

        return response

    except Exception as exc:
        # 未捕获异常：记 traceback，返回统一 500 响应
        error_message = f"{type(exc).__name__}: {exc}"
        tb = traceback.format_exc()
        duration_ms = (time.time() - start_time) * 1000

        # 同样在异常路径读取 user 信息
        user_id = getattr(request.state, "user_id", None)
        username = getattr(request.state, "username", None)
        user_label = username if username else (str(user_id) if user_id else "-")

        _emit_access_log(
            method=method,
            path=path,
            status_code=500,
            duration_ms=duration_ms,
            ip=ip,
            user_label=user_label,
            error_message=error_message,
            body_preview=None,
            traceback_text=tb,
        )

        # 异常请求也写一条操作日志，便于排查
        if _should_record_operation(method, path):
            try:
                asyncio.create_task(
                    _write_operation_log(
                        user_id=user_id,
                        username=username,
                        method=method,
                        path=path,
                        query_string=query_string,
                        status_code=500,
                        duration_ms=duration_ms,
                        ip=ip,
                        user_agent=user_agent,
                    )
                )
            except RuntimeError as e:
                logger.warning("无法调度操作日志后台任务: %s", e)

        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": "服务器内部错误", "data": None},
        )


def _emit_access_log(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    ip: str,
    user_label: str,
    error_message: str | None = None,
    body_preview: str | None = None,
    traceback_text: str | None = None,
) -> None:
    """
    输出访问日志

    级别策略：
      - 5xx / 未捕获异常 → ERROR
      - 4xx              → WARNING
      - 2xx / 3xx        → INFO
    """
    parts = [f"{method} {path} {status_code} {duration_ms:.1f}ms {ip} user={user_label}"]

    if error_message:
        parts.append(f'error="{error_message}"')
    if body_preview:
        parts.append(f"body={body_preview}")
    if traceback_text:
        # traceback 截前 1000 字符
        parts.append(f"traceback={traceback_text[:1000]}")

    message = " ".join(parts)

    if status_code >= 500:
        logger.error(message)
    elif status_code >= 400:
        logger.warning(message)
    else:
        logger.info(message)