"""
FastAPI 应用入口

AI 智能测试平台 - 主应用程序
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import access_log_middleware, auth_middleware
from app.core.response import ResponseModel
from app.db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    启动时初始化资源，关闭时清理资源
    """
    # 启动时执行：先初始化日志，再做其他
    setup_logging()
    logger.info("🚀 AI 智能测试平台启动中...")
    logger.info("📋 环境: %s", settings.ENV)
    logger.info("🔗 数据库: %s...", settings.DATABASE_URL[:20])
    logger.info("🤖 AI 模型: %s", settings.AI_MODEL)
    # 初始化数据库
    await init_db.main()

    yield

    # 关闭时执行
    logger.info("👋 AI 智能测试平台已关闭")


# 创建 FastAPI 应用实例
# 生产环境(ENV=production)关闭 /docs、/redoc、openapi.json,避免对外暴露接口结构
_docs_enabled = settings.ENV.lower() not in ("production", "prod")
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI 智能测试平台 - 基于 FastAPI + Vue3 的智能测试用例生成平台",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if _docs_enabled else None,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    lifespan=lifespan,
)


# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 添加 GZip 压缩中间件
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 注册业务中间件（注意：最后注册的最先执行）
# 执行顺序：access_log_middleware → auth_middleware → 路由
app.middleware("http")(auth_middleware)
app.middleware("http")(access_log_middleware)


# 挂载静态文件目录（本地模式下用于上传文件的访问，COS 模式下前端直接访问 COS）
upload_dir = Path(settings.UPLOAD_DIR)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


# 注册 API 路由
app.include_router(api_router, prefix=settings.API_V1_STR)


# 根路径健康检查
@app.get("/", response_model=ResponseModel[dict])
async def root() -> ResponseModel[dict]:
    """
    根路径健康检查

    Returns:
        ResponseModel: 包含服务信息的响应
    """
    return ResponseModel(
        data={
            "service": settings.PROJECT_NAME,
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs",
            "redoc": "/redoc",
        }
    )


# 健康检查端点
@app.get("/health", response_model=ResponseModel[dict])
async def health_check() -> ResponseModel[dict]:
    """
    健康检查端点

    Returns:
        ResponseModel: 包含健康状态的响应
    """
    return ResponseModel(data={"status": "healthy"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8888,
        reload=True,
    )

# 版权声明：此代码为木森老师自动化测试ai智能体开发课程2503期的配套代码，版权为木森老师所有，仅用于教学和学习，不用于商业用途。
# 请在进行商业用途使用前，先联系木森老师（微信：python771 或邮箱：121292679@qq.com）确认授权。
# 倒卖课程和代码将被视为侵权行为，将被法律追究。
