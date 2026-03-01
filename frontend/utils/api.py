import os
from collections import Counter
from datetime import datetime
from typing import Optional, Dict, Any, Iterable

import httpx


DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_API_TIMEOUT_SECONDS = 300.0


class APIError(Exception):
    """前端 API 调用异常。"""


def get_default_api_url() -> str:
    """从环境变量读取 API 地址，未配置时使用本地默认地址。"""
    return (
        os.getenv("BACKEND_URL")
        or os.getenv("JOB_MARKET_API_URL")
        or os.getenv("API_BASE_URL")
        or DEFAULT_API_URL
    ).rstrip("/")


def get_default_timeout() -> float:
    """读取前端 API 超时配置，默认 300 秒。"""
    raw_timeout = os.getenv("FRONTEND_API_TIMEOUT", str(DEFAULT_API_TIMEOUT_SECONDS))
    try:
        timeout = float(raw_timeout)
    except ValueError:
        return DEFAULT_API_TIMEOUT_SECONDS
    return timeout if timeout > 0 else DEFAULT_API_TIMEOUT_SECONDS


def _pick_first(mapping: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) is not None:
            return mapping.get(key)
    return default


def _to_count_dict(raw: Any) -> Dict[str, int]:
    if isinstance(raw, dict):
        out: Dict[str, int] = {}
        for key, value in raw.items():
            try:
                out[str(key)] = int(value)
            except (ValueError, TypeError):
                continue
        return out

    if isinstance(raw, list):
        out: Dict[str, int] = {}
        for item in raw:
            if isinstance(item, dict):
                label = _pick_first(item, ["name", "label", "key", "location", "skill", "company", "type"])
                count = _pick_first(item, ["count", "value", "jobs", "total"], 0)
                if not label:
                    continue
                try:
                    out[str(label)] = int(count)
                except (ValueError, TypeError):
                    continue
            elif item:
                out[str(item)] = out.get(str(item), 0) + 1
        return out

    return {}


def _normalize_skills(raw_skills: Any) -> list[str]:
    if isinstance(raw_skills, list):
        if raw_skills and isinstance(raw_skills[0], dict):
            return [str(item.get("skill", "")).strip() for item in raw_skills if item.get("skill")]
        return [str(skill).strip() for skill in raw_skills if str(skill).strip()]
    if isinstance(raw_skills, str) and raw_skills.strip():
        return [raw_skills.strip()]
    return []


def _extract_module_dict(market_insights: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = market_insights.get(key, {})
    return value if isinstance(value, dict) else {}


def _normalize_analyze_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = payload
    if isinstance(payload.get("data"), dict):
        data = payload["data"]
    elif isinstance(payload.get("result"), dict):
        data = payload["result"]
    elif isinstance(payload.get("analysis"), dict):
        data = payload["analysis"]

    raw_jobs = _pick_first(data, ["jobs", "job_listings", "samples"], []) or []
    jobs = raw_jobs if isinstance(raw_jobs, list) else []

    raw_market_insights = _pick_first(data, ["market_insights", "insights", "summary"], {}) or {}
    market_insights = raw_market_insights if isinstance(raw_market_insights, dict) else {}
    sample_overview = _extract_module_dict(market_insights, "sample_overview")
    trend_analysis = _extract_module_dict(market_insights, "trend_analysis")
    salary_analysis = _extract_module_dict(market_insights, "salary_analysis")
    applicant_analysis = _extract_module_dict(market_insights, "applicant_analysis")
    competition_intensity = _extract_module_dict(market_insights, "competition_intensity")
    skill_profile = _extract_module_dict(market_insights, "skill_profile")
    employer_profile = _extract_module_dict(market_insights, "employer_profile")
    top_jobs = _extract_module_dict(market_insights, "top_jobs")

    top_skills = _normalize_skills(
        _pick_first(market_insights, ["top_skills", "skills", "topSkills"], [])
    )
    if not top_skills:
        top_skills = _normalize_skills(skill_profile.get("top_skills", []))

    top_companies_raw = _pick_first(
        market_insights,
        ["top_companies", "top_employers", "companies", "topCompanies"],
        [],
    )
    if isinstance(top_companies_raw, list):
        if top_companies_raw and isinstance(top_companies_raw[0], dict):
            top_companies = [str(item.get("company", "")).strip() for item in top_companies_raw if item.get("company")]
        else:
            top_companies = [str(item).strip() for item in top_companies_raw if str(item).strip()]
    else:
        top_companies = []
    if not top_companies:
        top_companies = [
            str(item.get("company", "")).strip()
            for item in employer_profile.get("top_employers", []) or []
            if isinstance(item, dict) and item.get("company")
        ]

    location_distribution = _to_count_dict(
        _pick_first(
            market_insights,
            ["location_distribution", "top_locations", "locations", "locationDistribution"],
            {},
        )
    )

    experience_distribution = _to_count_dict(
        _pick_first(
            market_insights,
            ["experience_distribution", "experience_levels", "experienceDistribution"],
            {},
        )
    )

    salary_distribution = _to_count_dict(
        _pick_first(
            market_insights,
            ["salary_distribution", "salary_bands", "salaryDistribution"],
            {},
        )
    )

    job_type_distribution = _to_count_dict(
        _pick_first(
            market_insights,
            ["job_type_distribution", "employment_type_distribution", "jobTypeDistribution"],
            {},
        )
    )

    if not top_companies and jobs:
        company_counts = Counter(str(job.get("company", "")).strip() for job in jobs if job.get("company"))
        top_companies = [name for name, _ in company_counts.most_common(10)]

    normalized_insights: Dict[str, Any] = {
        "total_jobs": _pick_first(
            market_insights,
            ["total_jobs", "total", "job_count"],
            sample_overview.get("total_jobs", len(jobs)),
        ),
        "avg_salary_range": _pick_first(market_insights, ["avg_salary_range", "average_salary", "salary_range"]),
        "top_skills": top_skills,
        "top_companies": top_companies,
        "experience_distribution": experience_distribution,
        "location_distribution": location_distribution,
        "salary_distribution": salary_distribution,
        "job_type_distribution": job_type_distribution,
        "competition_level": _pick_first(market_insights, ["competition_level", "competition", "market_heat"]),
        "sample_overview": sample_overview,
        "trend_analysis": trend_analysis,
        "salary_analysis": salary_analysis,
        "applicant_analysis": applicant_analysis,
        "competition_intensity": competition_intensity,
        "skill_profile": skill_profile,
        "employer_profile": employer_profile,
        "top_jobs": top_jobs,
        "report_meta": _extract_module_dict(market_insights, "report_meta"),
        "report_sections": market_insights.get("report_sections", {}) if isinstance(market_insights.get("report_sections"), dict) else {},
    }

    report = _pick_first(data, ["report", "analysis_report", "markdown_report"], "") or ""

    meta = _pick_first(data, ["meta", "metadata"], {})
    if not isinstance(meta, dict):
        meta = {}

    meta.setdefault("generated_at", datetime.now().isoformat(timespec="seconds"))

    return {
        "market_insights": normalized_insights,
        "jobs": jobs,
        "report": str(report),
        "meta": meta,
    }


def _normalize_report_detail_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """将报告详情接口返回结构适配为分析页可直接使用的数据。"""
    normalized = _normalize_analyze_payload(payload)
    report_id = str(payload.get("id", "")).strip()
    query = str(payload.get("query", "")).strip()
    location = str(payload.get("location", "")).strip()

    try:
        max_results = int(payload.get("max_results", 20))
    except (TypeError, ValueError):
        max_results = 20

    created_at = str(payload.get("created_at", "")).strip()
    normalized["meta"]["report_id"] = report_id
    normalized["meta"]["query"] = query
    normalized["meta"]["location"] = location
    normalized["meta"]["max_results"] = max_results
    if created_at:
        normalized["meta"]["generated_at"] = created_at

    normalized["query"] = query
    normalized["location"] = location
    normalized["max_results"] = max_results
    normalized["report_id"] = report_id
    normalized["created_at"] = created_at
    return normalized


class APIClient:
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = (base_url or get_default_api_url()).rstrip("/")
        self.timeout = timeout if timeout is not None else get_default_timeout()

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
        """调用市场分析接口并标准化响应结构。"""
        params: Dict[str, Any] = {"query": query, "max_results": max_results}
        if location:
            params["location"] = location

        payload = self._request("GET", "/api/analyze", params=params)
        return _normalize_analyze_payload(payload)

    def health_check(self) -> Dict[str, Any]:
        """调用健康检查接口。"""
        return self._request("GET", "/api/health")

    def list_reports(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """调用历史报告列表接口。"""
        params = {"limit": int(limit), "offset": int(offset)}
        return self._request("GET", "/api/reports", params=params)

    def get_report_detail(self, report_id: str) -> Dict[str, Any]:
        """调用报告详情接口并标准化为分析页结构。"""
        payload = self._request("GET", f"/api/reports/{report_id}")
        return _normalize_report_detail_payload(payload)
