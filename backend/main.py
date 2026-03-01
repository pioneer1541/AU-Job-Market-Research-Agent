"""FastAPI application entry point.
FastAPI 应用入口
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from backend.api.routes import router as api_router
from backend.api.schemas import ErrorResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Starting Job Market Research Agent...")
    yield
    # 关闭时执行
    logger.info("Shutting down Job Market Research Agent...")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="Job Market Research Agent",
    description="AI-powered job market analysis API\n\nAI 驱动的就业市场分析 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ==================== CORS 中间件配置 ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # 本地前端开发
        "http://localhost:5173",  # Vite 默认端口
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*",  # 生产环境应限制为具体域名
    ],
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)


# ==================== 异常处理器 ====================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误
    
    当请求数据不符合 Pydantic 模型时触发
    """
    logger.warning(f"请求验证失败: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "请求数据验证失败",
            "detail": str(exc.errors()),
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """处理值错误"""
    logger.warning(f"值错误: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "ValueError",
            "message": str(exc),
            "detail": None,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常
    
    作为最后的兜底异常处理器
    """
    logger.error(f"未处理的异常: {type(exc).__name__}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "服务器内部错误",
            "detail": str(exc) if app.debug else None,
        },
    )


# ==================== 注册路由 ====================

app.include_router(api_router, prefix="/api")


# ==================== 根路径健康检查 ====================

@app.get("/", tags=["Root"])
async def root():
    """根路径，返回 API 信息"""
    return {
        "name": "Job Market Research Agent",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }
