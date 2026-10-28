"""网关报告端点（P4-D 独立报告源，契约 §3.6）

GET /api/v1/app/reports/{execution_id}?exp=&sig=

Midscene 报告在**网关源**（与平台跨端口=跨源）返回：报告自己的 JS 在
本源全量水合（localStorage 可用），而本源不存在平台 JWT/任何凭据——
G9 红线以「源隔离」而非「掐脚本」满足。鉴权＝短时效 HMAC 签名
（业务 API build_report_url 签发，共享 SECRET_KEY），iframe src 直连。

文件名 = {execution_id}.html（int 路径参数天然防目录穿越），读
settings.APP_REPORT_DIR（与 exec 图落盘同目录、两进程同 cwd 语义）。
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.config import settings
from app.services.app_device.report_sign import verify_report_sig

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/v1/app/reports/{execution_id}")
async def serve_report(
    execution_id: int,
    exp: int = Query(...),
    sig: str = Query(...),
) -> FileResponse:
    """签名校验通过即回报告 HTML（独立源，无平台凭据可摸）。"""
    if not verify_report_sig(execution_id, exp, sig):
        raise HTTPException(403, detail="签名无效或已过期，请重新打开报告")
    report_dir = Path(settings.APP_REPORT_DIR).resolve()
    file_path = report_dir / f"{execution_id}.html"
    if not file_path.is_file():
        raise HTTPException(404, detail="报告文件不存在")
    return FileResponse(
        file_path,
        media_type="text/html; charset=utf-8",
        headers={
            # 签名短时效 + 报告含设备截图：禁共享缓存
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
