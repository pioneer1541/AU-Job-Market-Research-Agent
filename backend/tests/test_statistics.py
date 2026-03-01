"""StatisticsService 单元测试。"""

from backend.services.statistics import StatisticsService, parse_salary_text


def _build_jobs() -> list[dict]:
    """构造测试职位样本（纯本地数据，不调用外部服务）。"""
    return [
        {
            "id": "job-1",
            "title": "Senior Python Developer",
            "company": "Tech A",
            "location": "Melbourne",
            "salary": "$120k - $150k",
            "description": "Python Django AWS",
            "posted_date": "2026-02-20",
        },
        {
            "id": "job-2",
            "title": "Data Engineer",
            "company": "Tech B",
            "location": "Sydney",
            "salary": "AUD 100000 - 130000",
            "description": "SQL Airflow Spark",
            "posted_date": "2026-02-21",
        },
        {
            "id": "job-3",
            "title": "ML Engineer",
            "company": "Tech A",
            "location": "Remote",
            "salary": None,
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
        assert "competition_intensity" in insights
        assert "skill_profile" in insights
        assert "employer_profile" in insights

        # 验证兼容字段仍存在
        assert "top_skills" in insights
        assert "salary_stats" in insights
        assert isinstance(insights["skill_profile"].get("top_skills", []), list)
