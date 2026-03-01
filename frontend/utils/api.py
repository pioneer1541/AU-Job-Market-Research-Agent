import os
from typing import Optional, Dict, Any

import httpx


DEFAULT_API_URL = "http://localhost:8000"


class APIError(Exception):
    """前端 API 调用异常。"""


def get_default_api_url() -> str:
    """从环境变量读取 API 地址，未配置时使用本地默认地址。"""
    return (
        os.getenv("JOB_MARKET_API_URL")
        or os.getenv("API_BASE_URL")
        or DEFAULT_API_URL
    ).rstrip("/")


class APIClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 20.0):
        self.base_url = (base_url or get_default_api_url()).rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise APIError("API 返回格式异常：预期为 JSON 对象。")
                return payload
        except httpx.ConnectError as exc:
            raise APIError(f"无法连接到后端服务：{self.base_url}") from exc
        except httpx.TimeoutException as exc:
            raise APIError("请求超时，请稍后重试。") from exc
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                err_json = exc.response.json()
                detail = err_json.get("message") or err_json.get("detail") or ""
            except Exception:
                detail = exc.response.text
            detail = detail or f"HTTP {exc.response.status_code}"
            raise APIError(f"API 请求失败：{detail}") from exc
        except httpx.RequestError as exc:
            raise APIError(f"请求异常：{str(exc)}") from exc
        except ValueError as exc:
            raise APIError("API 返回内容无法解析为 JSON。") from exc

    def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        max_results: int = 20,
    ) -> Dict[str, Any]:
        """调用职位搜索接口。"""
        payload: Dict[str, Any] = {"query": query, "max_results": max_results}
        if location:
            payload["location"] = location
        return self._request("POST", "/api/jobs/search", json=payload)

    def analyze_market(
        self,
        query: str,
        location: Optional[str] = None,
        max_results: int = 20,
    ) -> Dict[str, Any]:
        """调用市场分析接口。"""
        params: Dict[str, Any] = {"query": query, "max_results": max_results}
        if location:
            params["location"] = location
        return self._request("GET", "/api/analyze", params=params)

    def health_check(self) -> Dict[str, Any]:
        """调用健康检查接口。"""
        return self._request("GET", "/api/health")
