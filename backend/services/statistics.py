"""
统计分析服务

为职位样本生成结构化市场统计结果。
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import median
from typing import Any, Optional


COMMON_SKILLS = {
    "python": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "go": "Go",
    "rust": "Rust",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "react": "React",
    "vue": "Vue",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "llm": "LLM",
    "nlp": "NLP",
    "spark": "Spark",
    "hadoop": "Hadoop",
    "airflow": "Airflow",
}


def _to_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _to_int(value: Any) -> Optional[int]:
    """将任意输入安全转换为 int，失败时返回 None。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_salary_text(salary_text: Optional[str]) -> Optional[dict[str, Any]]:
    """
    解析薪资字符串并返回统一结构:
    {
      "min_annual": float,
      "max_annual": float,
      "currency": "AUD",
      "period": "year" | "month" | "hour",
      "raw": str
    }
    """
    if not salary_text:
        return None

    raw = salary_text.strip()
    s = raw.lower().replace(",", "").replace(" ", "")
    if not s:
        return None

    currency = "AUD"
    if "usd" in s or "$us" in s:
        currency = "USD"
    elif "gbp" in s or "£" in raw:
        currency = "GBP"
    elif "eur" in s or "€" in raw:
        currency = "EUR"

    period = "year"
    if any(token in s for token in ["/month", "monthly", "permonth"]):
        period = "month"
    elif any(token in s for token in ["/hour", "hourly", "perhour", "/hr", "ph"]):
        period = "hour"

    values: list[float] = []
    for match in re.findall(r"(\d+(?:\.\d+)?)k", s):
        values.append(float(match) * 1000)
    for match in re.findall(r"(\d{2,7}(?:\.\d+)?)", s):
        num = float(match)
        # 对年薪文本保留原有噪音过滤；时薪场景允许解析小于 30 的合法数值。
        if num < 30 and "k" not in s and period != "hour":
            continue
        if num <= 1000 and period == "hour":
            values.append(num)
        elif num >= 1000:
            values.append(num)

    if not values:
        return None

    min_val = min(values)
    max_val = max(values)

    if period == "month":
        min_annual = min_val * 12
        max_annual = max_val * 12
    elif period == "hour":
        min_annual = min_val * 40 * 52
        max_annual = max_val * 40 * 52
    else:
        min_annual = min_val
        max_annual = max_val

    return {
        "min_annual": float(min_annual),
        "max_annual": float(max_annual),
        "currency": currency,
        "period": period,
        "raw": raw,
    }


class StatisticsService:
    """职位市场统计计算服务。"""

    def get_top_jobs(self, jobs: list[dict[str, Any]], top_n: int = 3) -> dict[str, list[dict[str, Any]]]:
        """
        返回两个 TOPN 职位列表：
        1) 按申请人数排序
        2) 按薪资上限（年化）排序
        """
        # 兼容不同来源字段名，优先使用数值化后的申请人数。
        applicants_candidates = ["num_applicants", "numApplicants", "applicants", "application_count", "apply_count"]
        top_by_applicants: list[dict[str, Any]] = []
        for job in jobs:
            applicants: Optional[int] = None
            for field in applicants_candidates:
                if field in job and job.get(field) is not None:
                    applicants = _to_int(job.get(field))
                    if applicants is not None:
                        break
            if applicants is None:
                continue
            top_by_applicants.append(
                {
                    "title": str(job.get("title", "")).strip(),
                    "company": str(job.get("company", "")).strip(),
                    "num_applicants": applicants,
                    "url": str(job.get("url", "")).strip(),
                }
            )

        top_by_applicants = sorted(
            top_by_applicants,
            key=lambda item: item.get("num_applicants", 0),
            reverse=True,
        )[:top_n]

        top_by_salary: list[dict[str, Any]] = []
        for job in jobs:
            parsed_salary = parse_salary_text(job.get("salary"))
            if not parsed_salary:
                continue
            top_by_salary.append(
                {
                    "title": str(job.get("title", "")).strip(),
                    "company": str(job.get("company", "")).strip(),
                    "salary": str(parsed_salary.get("raw") or job.get("salary") or "").strip(),
                    "salary_max_annual": round(float(parsed_salary.get("max_annual", 0)), 0),
                    "currency": str(parsed_salary.get("currency", "AUD")),
                    "url": str(job.get("url", "")).strip(),
                }
            )

        top_by_salary = sorted(
            top_by_salary,
            key=lambda item: item.get("salary_max_annual", 0),
            reverse=True,
        )[:top_n]

        return {
            "top_by_applicants": top_by_applicants,
            "top_by_salary": top_by_salary,
        }

    def filter_low_salary_jobs(self, jobs: list[dict[str, Any]]) -> dict[str, Any]:
        """
        过滤低薪职位：
        - 时薪（AUD）低于 24
        - 年薪（AUD）低于 50,000
        """
        total_jobs = len(jobs)
        filtered_jobs: list[dict[str, Any]] = []
        filtered_out_jobs = 0
        evaluated_salary_jobs = 0

        for job in jobs:
            parsed_salary = parse_salary_text(job.get("salary"))
            if not parsed_salary:
                filtered_jobs.append(job)
                continue

            # 仅对 AUD 薪资做阈值过滤，避免跨币种误判。
            if parsed_salary.get("currency") != "AUD":
                filtered_jobs.append(job)
                continue

            evaluated_salary_jobs += 1
            period = parsed_salary.get("period")
            max_annual = parsed_salary.get("max_annual", 0.0)
            max_hourly = max_annual / (40 * 52)
            is_hourly_low = period == "hour" and max_hourly < 24
            is_annual_low = period != "hour" and max_annual < 50000

            if is_hourly_low or is_annual_low:
                filtered_out_jobs += 1
                continue

            filtered_jobs.append(job)

        return {
            "filtered_jobs": filtered_jobs,
            "filter_stats": {
                "total_jobs_before_filter": total_jobs,
                "total_jobs_after_filter": len(filtered_jobs),
                "filtered_low_salary_jobs": filtered_out_jobs,
                "filtered_ratio_pct": round(_safe_div(filtered_out_jobs, max(total_jobs, 1)) * 100, 2),
                "evaluated_salary_jobs": evaluated_salary_jobs,
                "hourly_threshold_aud": 24,
                "annual_threshold_aud": 50000,
            },
        }

    def compute_sample_overview(
        self,
        jobs: list[dict[str, Any]],
        analysis_results: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        analysis_results = analysis_results or []
        total_jobs = len(jobs)
        unique_companies = len({(j.get("company") or "").strip() for j in jobs if j.get("company")})
        unique_locations = len({(j.get("location") or "").strip() for j in jobs if j.get("location")})

        dated = [_to_date(j.get("posted_date")) for j in jobs]
        dated = [d for d in dated if d]
        date_min = min(dated).isoformat() if dated else None
        date_max = max(dated).isoformat() if dated else None

        salary_count = sum(1 for j in jobs if parse_salary_text(j.get("salary")))
        salary_coverage = round(_safe_div(salary_count, max(total_jobs, 1)) * 100, 2)
        analysis_coverage = round(_safe_div(len(analysis_results), max(total_jobs, 1)) * 100, 2)

        return {
            "total_jobs": total_jobs,
            "unique_companies": unique_companies,
            "unique_locations": unique_locations,
            "date_range": {"start": date_min, "end": date_max},
            "salary_coverage_pct": salary_coverage,
            "analysis_coverage_pct": analysis_coverage,
        }

    def analyze_job_volume_trend(self, jobs: list[dict[str, Any]]) -> dict[str, Any]:
        day_counter: Counter[str] = Counter()
        for job in jobs:
            d = _to_date(job.get("posted_date"))
            if d:
                day_counter[d.isoformat()] += 1

        if not day_counter:
            return {"series": [], "trend": "unknown", "avg_daily_postings": 0}

        series = [{"date": d, "count": c} for d, c in sorted(day_counter.items())]
        counts = [point["count"] for point in series]
        avg_daily = round(sum(counts) / len(counts), 2)

        midpoint = max(1, len(counts) // 2)
        first_avg = sum(counts[:midpoint]) / len(counts[:midpoint])
        second_avg = sum(counts[midpoint:]) / len(counts[midpoint:])
        delta = second_avg - first_avg
        if delta > 0.2:
            trend = "up"
        elif delta < -0.2:
            trend = "down"
        else:
            trend = "flat"

        return {"series": series, "trend": trend, "avg_daily_postings": avg_daily}

    def analyze_salary(
        self,
        jobs: list[dict[str, Any]],
        analysis_results: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        analysis_results = analysis_results or []
        salary_entries: list[dict[str, Any]] = []
        job_salary_by_id: dict[str, dict[str, Any]] = {}
        for job in jobs:
            parsed = parse_salary_text(job.get("salary"))
            if parsed:
                job_salary_by_id[job.get("id", "")] = parsed
                salary_entries.append(parsed)

        for result in analysis_results:
            parsed = parse_salary_text(result.get("salary_estimate"))
            job_id = result.get("job_id", "")
            if parsed and job_id and job_id not in job_salary_by_id:
                job_salary_by_id[job_id] = parsed
                salary_entries.append(parsed)

        if not salary_entries:
            return {
                "count": 0,
                "coverage_pct": 0,
                "currency": None,
                "annual": {},
                "bands": {},
                "by_experience": {},
            }

        annual_mids = [(item["min_annual"] + item["max_annual"]) / 2 for item in salary_entries]
        annual_lows = [item["min_annual"] for item in salary_entries]
        annual_highs = [item["max_annual"] for item in salary_entries]
        sorted_mids = sorted(annual_mids)
        p25_idx = max(0, math.floor((len(sorted_mids) - 1) * 0.25))
        p75_idx = max(0, math.floor((len(sorted_mids) - 1) * 0.75))

        bands = {"<100k": 0, "100k-150k": 0, "150k-200k": 0, ">=200k": 0}
        for mid in annual_mids:
            if mid < 100000:
                bands["<100k"] += 1
            elif mid < 150000:
                bands["100k-150k"] += 1
            elif mid < 200000:
                bands["150k-200k"] += 1
            else:
                bands[">=200k"] += 1

        by_exp: dict[str, list[float]] = defaultdict(list)
        for result in analysis_results:
            job_id = result.get("job_id", "")
            exp = result.get("experience_level", "Unknown") or "Unknown"
            salary_item = job_salary_by_id.get(job_id)
            if salary_item:
                mid = (salary_item["min_annual"] + salary_item["max_annual"]) / 2
                by_exp[exp].append(mid)

        by_experience = {}
        for exp, values in by_exp.items():
            if not values:
                continue
            by_experience[exp] = {
                "count": len(values),
                "avg": round(sum(values) / len(values), 0),
                "min": round(min(values), 0),
                "max": round(max(values), 0),
            }

        salary_stats_legacy = {
            "average": round(sum(annual_mids) / len(annual_mids), 0),
            "min": round(min(annual_lows), 0),
            "max": round(max(annual_highs), 0),
            "count": len(annual_mids),
            "currency": salary_entries[0]["currency"],
            "by_experience": by_experience,
            "by_industry": {},
        }

        return {
            "count": len(salary_entries),
            "coverage_pct": round(_safe_div(len(salary_entries), max(len(jobs), 1)) * 100, 2),
            "currency": salary_entries[0]["currency"],
            "annual": {
                "avg": round(sum(annual_mids) / len(annual_mids), 0),
                "median": round(median(annual_mids), 0),
                "min": round(min(annual_lows), 0),
                "max": round(max(annual_highs), 0),
                "p25": round(sorted_mids[p25_idx], 0),
                "p75": round(sorted_mids[p75_idx], 0),
            },
            "bands": bands,
            "by_experience": by_experience,
            "salary_stats_legacy": salary_stats_legacy,
        }

    def analyze_competition_intensity(self, jobs: list[dict[str, Any]]) -> dict[str, Any]:
        total_jobs = len(jobs)
        if total_jobs == 0:
            return {
                "competition_level": "unknown",
                "jobs_per_company": 0,
                "top_company_share_pct": 0,
                "top_location_share_pct": 0,
            }

        company_counts = Counter((j.get("company") or "Unknown").strip() for j in jobs)
        location_counts = Counter((j.get("location") or "Unknown").strip() for j in jobs)
        jobs_per_company = round(total_jobs / max(len(company_counts), 1), 2)
        top_company_share = round(_safe_div(max(company_counts.values()), total_jobs) * 100, 2)
        top_location_share = round(_safe_div(max(location_counts.values()), total_jobs) * 100, 2)

        score = total_jobs * 0.4 + jobs_per_company * 20 + top_company_share * 0.3
        if score >= 70:
            level = "high"
        elif score >= 35:
            level = "medium"
        else:
            level = "low"

        return {
            "competition_level": level,
            "jobs_per_company": jobs_per_company,
            "top_company_share_pct": top_company_share,
            "top_location_share_pct": top_location_share,
            "active_companies": len(company_counts),
            "active_locations": len(location_counts),
        }

    def extract_skill_profile(
        self,
        jobs: list[dict[str, Any]],
        analysis_results: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        analysis_results = analysis_results or []
        skill_counter: Counter[str] = Counter()

        for result in analysis_results:
            for skill in result.get("skills_required", []) or []:
                if skill:
                    skill_counter[skill.strip()] += 1

        for job in jobs:
            text = f"{job.get('title', '')} {job.get('description', '')}".lower()
            for token, canonical in COMMON_SKILLS.items():
                pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
                if re.search(pattern, text):
                    skill_counter[canonical] += 1

        top_skills = [{"skill": skill, "count": count} for skill, count in skill_counter.most_common(15)]
        return {
            "top_skills": top_skills,
            "total_unique_skills": len(skill_counter),
        }

    def analyze_employers(self, jobs: list[dict[str, Any]]) -> dict[str, Any]:
        if not jobs:
            return {
                "top_employers": [],
                "remote_ratio_pct": 0,
                "employer_concentration_hhi": 0,
            }

        company_counts = Counter((j.get("company") or "Unknown").strip() for j in jobs)
        top_employers = [
            {"company": company, "count": count}
            for company, count in company_counts.most_common(10)
        ]
        total_jobs = len(jobs)
        hhi = 0.0
        for count in company_counts.values():
            share = count / total_jobs
            hhi += share * share

        remote_jobs = 0
        for job in jobs:
            loc = (job.get("location") or "").lower()
            if "remote" in loc or "hybrid" in loc:
                remote_jobs += 1

        return {
            "top_employers": top_employers,
            "remote_ratio_pct": round(_safe_div(remote_jobs, total_jobs) * 100, 2),
            "employer_concentration_hhi": round(hhi, 4),
            "unique_employers": len(company_counts),
        }

    def generate_market_insights(
        self,
        jobs: list[dict[str, Any]],
        analysis_results: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        analysis_results = analysis_results or []
        sample_overview = self.compute_sample_overview(jobs, analysis_results)
        trend_analysis = self.analyze_job_volume_trend(jobs)
        salary_analysis = self.analyze_salary(jobs, analysis_results)
        competition_intensity = self.analyze_competition_intensity(jobs)
        skill_profile = self.extract_skill_profile(jobs, analysis_results)
        employer_profile = self.analyze_employers(jobs)
        top_jobs = self.get_top_jobs(jobs, top_n=3)

        exp_dist = Counter(
            (item.get("experience_level") or "Unknown")
            for item in analysis_results
        )
        top_locations = Counter((j.get("location") or "Unknown") for j in jobs)
        industry_dist = Counter((item.get("industry") or "Unknown") for item in analysis_results)

        return {
            "sample_overview": sample_overview,
            "trend_analysis": trend_analysis,
            "salary_analysis": salary_analysis,
            "competition_intensity": competition_intensity,
            "skill_profile": skill_profile,
            "employer_profile": employer_profile,
            "top_jobs": top_jobs,
            # 兼容旧字段
            "top_skills": skill_profile.get("top_skills", []),
            "experience_distribution": dict(exp_dist),
            "top_locations": [
                {"location": loc, "count": count}
                for loc, count in top_locations.most_common(5)
            ],
            "industry_distribution": dict(industry_dist),
            "total_analyzed": len(analysis_results),
            "salary_stats": salary_analysis.get("salary_stats_legacy"),
        }
