"""StatisticsService 单元测试。"""

import pytest

from backend.services.statistics import StatisticsService, parse_salary_text
from backend.services.report_generator import HAS_JINJA2, ReportGenerator


def _build_jobs() -> list[dict]:
    """构造测试职位样本（纯本地数据，不调用外部服务）。"""
    return [
        {
            "id": "job-1",
            "title": "Senior Python Developer",
            "company": "Tech A",
            "location": "Melbourne",
            "salary": "$120k - $150k",
            "url": "https://example.com/job-1",
            "num_applicants": 88,
            "description": "Python Django AWS",
            "posted_date": "2026-02-20",
        },
        {
            "id": "job-2",
            "title": "Data Engineer",
            "company": "Tech B",
            "location": "Sydney",
            "salary": "AUD 100000 - 130000",
            "url": "https://example.com/job-2",
            "num_applicants": 137,
            "description": "SQL Airflow Spark",
            "posted_date": "2026-02-21",
        },
        {
            "id": "job-3",
            "title": "ML Engineer",
            "company": "Tech A",
            "location": "Remote",
            "salary": "$160k - $200k",
            "url": "https://example.com/job-3",
            "num_applicants": 66,
            "description": "Python TensorFlow Docker",
            "posted_date": "2026-02-22",
        },
    ]


def _build_analysis_results() -> list[dict]:
    return [
        {
            "job_id": "job-1",
            "skills_required": ["Python", "Django", "AWS"],
            "experience_level": "Senior",
            "salary_estimate": "$125k - $155k",
            "industry": "Software",
        },
        {
            "job_id": "job-2",
            "skills_required": ["SQL", "Airflow", "Spark"],
            "experience_level": "Mid",
            "salary_estimate": "$110k - $135k",
            "industry": "Software",
        },
        {
            "job_id": "job-3",
            "skills_required": ["Python", "TensorFlow", "Docker"],
            "experience_level": "Mid",
            "salary_estimate": "$140k - $160k",
            "industry": "AI",
        },
    ]


class TestParseSalaryText:
    """薪资解析测试。"""

    def test_parse_salary_text_k_range(self):
        parsed = parse_salary_text("$120k - $150k")

        assert parsed is not None
        assert parsed["currency"] == "AUD"
        assert parsed["period"] == "year"
        assert parsed["min_annual"] == 120000.0
        assert parsed["max_annual"] == 150000.0

    def test_parse_salary_text_hourly(self):
        parsed = parse_salary_text("USD 85/hour")

        assert parsed is not None
        assert parsed["currency"] == "USD"
        assert parsed["period"] == "hour"
        # 85 * 40 * 52
        assert parsed["min_annual"] == 176800.0
        assert parsed["max_annual"] == 176800.0

    def test_parse_salary_text_empty(self):
        assert parse_salary_text(None) is None
        assert parse_salary_text("") is None


class TestStatisticsService:
    """StatisticsService 核心逻辑测试。"""

    def test_compute_sample_overview(self):
        service = StatisticsService()
        jobs = _build_jobs()
        analysis_results = _build_analysis_results()

        overview = service.compute_sample_overview(jobs, analysis_results)

        assert overview["total_jobs"] == 3
        assert overview["unique_companies"] == 2
        assert overview["unique_locations"] == 3
        assert overview["salary_coverage_pct"] > 60
        assert overview["analysis_coverage_pct"] == 100.0
        assert overview["date_range"]["start"] == "2026-02-20"
        assert overview["date_range"]["end"] == "2026-02-22"

    def test_compute_sample_overview_with_empty_dates(self):
        service = StatisticsService()
        jobs = [
            {"id": "j1", "posted_date": None},
            {"id": "j2", "posted_date": ""},
            {"id": "j3", "posted_date": "invalid-date"},
        ]

        overview = service.compute_sample_overview(jobs, analysis_results=[])

        assert overview["date_range"]["start"] == "暂无数据"
        assert overview["date_range"]["end"] == "暂无数据"

    def test_analyze_job_volume_trend_with_empty_dates(self):
        service = StatisticsService()
        jobs = [{"id": "j1", "posted_date": None}, {"id": "j2", "posted_date": ""}]

        trend = service.analyze_job_volume_trend(jobs)

        assert trend["series"] == []
        assert trend["trend"] == "暂无数据"
        assert trend["avg_daily_postings"] == 0

    def test_analyze_salary(self):
        service = StatisticsService()
        jobs = _build_jobs()
        analysis_results = _build_analysis_results()

        salary = service.analyze_salary(jobs, analysis_results)

        assert salary["count"] >= 3
        assert salary["currency"] in {"AUD", "USD", "GBP", "EUR"}
        assert salary["annual"]["avg"] >= salary["annual"]["min"]
        assert salary["annual"]["max"] >= salary["annual"]["avg"]
        assert isinstance(salary["bands"], dict)

    def test_generate_market_insights(self):
        service = StatisticsService()
        jobs = _build_jobs()
        analysis_results = _build_analysis_results()

        insights = service.generate_market_insights(jobs, analysis_results)

        # 验证新版模块化字段完整返回
        assert "sample_overview" in insights
        assert "trend_analysis" in insights
        assert "salary_analysis" in insights
        assert "applicant_analysis" in insights
        assert "competition_intensity" in insights
        assert "skill_profile" in insights
        assert "employer_profile" in insights
        assert "top_jobs" in insights

        # 验证兼容字段仍存在
        assert "top_skills" in insights
        assert "salary_stats" in insights
        assert isinstance(insights["skill_profile"].get("top_skills", []), list)

    def test_analyze_applicants(self):
        service = StatisticsService()
        jobs = _build_jobs()
        analysis_results = _build_analysis_results()

        applicant = service.analyze_applicants(jobs, analysis_results)

        assert applicant["count"] == 3
        assert applicant["avg_applicants_per_job"] == 97.0
        assert "Senior" in applicant["by_experience"]
        assert applicant["by_experience"]["Senior"]["avg_applicants"] == 88.0
        assert "100k-150k" in applicant["by_salary_band"]
        assert applicant["by_salary_band"]["100k-150k"]["jobs"] >= 1

    def test_get_top_jobs(self):
        service = StatisticsService()
        jobs = _build_jobs()

        top_jobs = service.get_top_jobs(jobs, top_n=3)
        top_by_applicants = top_jobs.get("top_by_applicants", [])
        top_by_salary = top_jobs.get("top_by_salary", [])

        assert len(top_by_applicants) == 3
        assert top_by_applicants[0]["title"] == "Data Engineer"
        assert top_by_applicants[0]["num_applicants"] == 137
        assert len(top_by_salary) == 3
        assert top_by_salary[0]["title"] == "ML Engineer"
        assert top_by_salary[0]["salary_max_annual"] >= top_by_salary[1]["salary_max_annual"]

    def test_filter_low_salary_jobs(self):
        service = StatisticsService()
        jobs = [
            {"id": "low-hourly", "salary": "AUD 22/hour"},
            {"id": "low-annual", "salary": "AUD 48000"},
            {"id": "ok-hourly", "salary": "AUD 24/hour"},
            {"id": "ok-annual", "salary": "AUD 60000"},
            {"id": "unknown", "salary": None},
        ]

        result = service.filter_low_salary_jobs(jobs)
        filtered_jobs = result["filtered_jobs"]
        stats = result["filter_stats"]

        filtered_ids = {job["id"] for job in filtered_jobs}
        assert "low-hourly" not in filtered_ids
        assert "low-annual" not in filtered_ids
        assert "ok-hourly" in filtered_ids
        assert "ok-annual" in filtered_ids
        assert "unknown" in filtered_ids
        assert stats["total_jobs_before_filter"] == 5
        assert stats["total_jobs_after_filter"] == 3
        assert stats["filtered_low_salary_jobs"] == 2
        assert stats["hourly_threshold_aud"] == 24
        assert stats["annual_threshold_aud"] == 50000


class TestReportGenerator:
    """报告生成测试。"""

    def test_generate_report_contains_salary_filter_stats(self):
        generator = ReportGenerator()
        market_insights = {
            "sample_overview": {
                "total_jobs": 3,
                "unique_companies": 2,
                "unique_locations": 2,
                "salary_coverage_pct": 66.67,
                "analysis_coverage_pct": 100.0,
                "date_range": {"start": "2026-02-20", "end": "2026-02-22"},
            },
            "top_jobs": {
                "top_by_applicants": [
                    {
                        "title": "Data Engineer",
                        "company": "Tech B",
                        "num_applicants": 137,
                        "url": "https://example.com/job-2",
                    }
                ],
                "top_by_salary": [
                    {
                        "title": "ML Engineer",
                        "company": "Tech A",
                        "salary": "$160k - $200k",
                        "salary_max_annual": 200000,
                        "currency": "AUD",
                        "url": "https://example.com/job-3",
                    }
                ],
            },
            "applicant_analysis": {
                "count": 3,
                "coverage_pct": 100.0,
                "avg_applicants_per_job": 97.0,
                "by_experience": {
                    "Senior": {"jobs": 1, "total_applicants": 88, "avg_applicants": 88.0},
                    "Mid": {"jobs": 2, "total_applicants": 203, "avg_applicants": 101.5},
                },
                "by_salary_band": {
                    "100k-150k": {"jobs": 2, "total_applicants": 225, "avg_applicants": 112.5},
                    "150k-200k": {"jobs": 1, "total_applicants": 66, "avg_applicants": 66.0},
                },
            },
            "deep_analysis": {
                "top_hard_skills": [{"item": "Python", "count": 3}],
                "top_soft_skills": [{"item": "沟通协作", "count": 2}],
                "top_industry_keywords": [{"item": "SaaS", "count": 2}],
                "top_responsibility_themes": [{"item": "后端开发", "count": 3}],
                "top_qualifications": [{"item": "本科及以上", "count": 2}],
                "years_of_experience_distribution": {"4-5年": 2, "6-8年": 1},
            },
        }
        processed_data = {
            "salary_filter_stats": {
                "total_jobs_before_filter": 5,
                "total_jobs_after_filter": 3,
                "filtered_low_salary_jobs": 2,
                "filtered_ratio_pct": 40.0,
                "hourly_threshold_aud": 24,
                "annual_threshold_aud": 50000,
            }
        }

        generated = generator.generate(
            query="python developer",
            market_insights=market_insights,
            processed_data=processed_data,
            errors=[],
        )
        report = generated["report"]

        assert "低薪过滤前职位数: 5" in report
        assert "低薪过滤后职位数: 3" in report
        assert "过滤职位数: 2" in report
        assert "时薪 < 24 AUD 或年薪 < 50000 AUD" in report
        assert "平均每个职位申请人数: 97.0" in report
        assert "按经验级别申请人数" in report
        assert "按薪资区间申请人数" in report
        assert "## H. TOP3 职位" in report
        assert "## I. 深度分析" in report
        assert "## J. 求职建议" in report
        assert "硬技能 Top10" in report
        assert "经验年限分布" in report
        assert "申请人数最多 TOP3" in report
        assert "薪资最高 TOP3" in report
        assert generated["report_meta"]["section_order"] == ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

    def test_extract_salary_band_data_uses_chinese_labels(self):
        labels, values = ReportGenerator._extract_salary_band_data(
            {"salary_analysis": {"bands": {"<100k": 2, "100k-150k": 3, "150k-200k": 1, ">=200k": 4}}}
        )

        assert labels == ["10万以下", "10万-15万", "15万-20万", "20万及以上"]
        assert values == [2.0, 3.0, 1.0, 4.0]

    @pytest.mark.skipif(not HAS_JINJA2, reason="Jinja2 不可用时无法验证内联模板渲染。")
    def test_render_pdf_html_fallback_contains_table_and_chart_data_when_no_template_env(self):
        generator = ReportGenerator()
        generator._template_env = None
        market_insights = {
            "sample_overview": {
                "total_jobs": 12,
                "unique_companies": 5,
                "unique_locations": 3,
                "salary_coverage_pct": 80.0,
            },
            "salary_analysis": {"bands": {"100k-150k": 8, "150k-200k": 4}},
            "skill_profile": {"top_skills": [{"skill": "Python", "count": 10}, {"skill": "SQL", "count": 6}]},
        }

        html = generator._render_pdf_html(
            query="python developer",
            report_text="## A. 样本概览\n- 测试",
            generated_at="2026-03-01 00:00:00 UTC",
            market_insights=market_insights,
        )

        assert "关键数据概览" in html
        assert "薪资范围分布" in html
        assert "技能要求 Top10 分布" in html
        assert "10万-15万" in html
        assert "Python" in html

    @pytest.mark.skipif(not HAS_JINJA2, reason="Jinja2 不可用时无法验证模板异常兜底。")
    def test_render_pdf_html_fallback_when_external_template_raises(self):
        class BrokenTemplateEnv:
            def get_template(self, _template_name: str):
                raise RuntimeError("template load failed")

        generator = ReportGenerator()
        generator._template_env = BrokenTemplateEnv()
        market_insights = {
            "sample_overview": {"total_jobs": 2, "unique_companies": 1, "unique_locations": 1, "salary_coverage_pct": 100},
            "salary_analysis": {"bands": {"80k-100k": 2}},
            "skill_profile": {"top_skills": [{"skill": "Docker", "count": 2}]},
        }

        html = generator._render_pdf_html(
            query="devops engineer",
            report_text="## A. 元信息\n- 测试",
            generated_at="2026-03-01 00:00:00 UTC",
            market_insights=market_insights,
        )

        assert "关键数据概览" in html
        assert "薪资范围分布" in html
        assert "技能要求 Top10 分布" in html
        assert "Docker" in html
