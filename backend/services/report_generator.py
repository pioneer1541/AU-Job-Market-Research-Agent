"""
模块化报告生成服务
"""
from __future__ import annotations

import base64
import io
import logging
import os
import re
from html import escape
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    HAS_JINJA2 = True
except Exception:
    HAS_JINJA2 = False

try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except Exception:
    HAS_WEASYPRINT = False

logger = logging.getLogger(__name__)

INLINE_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{{ report_title }}</title>
  <style>
    @page {
      size: A4;
      margin: 24mm 15mm 22mm 15mm;
    }

    body {
      font-family: "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif;
      color: #1f2937;
      font-size: 11pt;
      line-height: 1.7;
      margin: 0;
      padding: 0;
    }

    h1 {
      font-size: 22pt;
      font-weight: 700;
      margin: 0 0 6mm 0;
      color: #0f172a;
    }

    .meta {
      font-size: 10pt;
      color: #475569;
      margin-bottom: 8mm;
    }

    h2 {
      font-size: 15pt;
      margin: 7mm 0 3mm 0;
      font-weight: 700;
      border-left: 4px solid #0ea5e9;
      padding-left: 8px;
      color: #111827;
    }

    p {
      margin: 0 0 2.5mm 0;
    }

    ul {
      margin: 1mm 0 3mm 6mm;
      padding: 0;
    }

    li {
      margin-bottom: 1.2mm;
    }

    .table-title {
      margin-top: 4mm;
      margin-bottom: 2mm;
      font-size: 13pt;
      font-weight: 700;
      color: #0f172a;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 6mm;
      font-size: 10pt;
    }

    th, td {
      border: 1px solid #d1d5db;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }

    th {
      background-color: #f3f4f6;
      font-weight: 700;
      color: #1f2937;
    }

    .chart-block {
      margin-bottom: 6mm;
      page-break-inside: avoid;
    }

    .chart-title {
      font-size: 13pt;
      font-weight: 700;
      margin: 0 0 2mm 0;
      color: #0f172a;
    }

    .chart-image {
      width: 100%;
      max-width: 160mm;
      border: 1px solid #e5e7eb;
      padding: 4px;
      background: #ffffff;
      margin-bottom: 2mm;
    }
  </style>
</head>
<body>
  <h1>{{ report_title }}</h1>
  <div class="meta">生成时间：{{ generated_at }}</div>

  <div class="table-title">关键数据概览</div>
  <table>
    <thead>
      <tr>
        <th>指标</th>
        <th>数值</th>
      </tr>
    </thead>
    <tbody>
      {% for item in key_metrics %}
      <tr>
        <td>{{ item.label }}</td>
        <td>{{ item.value }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="chart-block">
    <div class="chart-title">薪资范围分布</div>
    {% if salary_chart_base64 %}
    <img class="chart-image" src="data:image/png;base64,{{ salary_chart_base64 }}" alt="薪资范围分布饼状图">
    {% endif %}
    <table>
      <thead><tr><th>区间</th><th>数量</th></tr></thead>
      <tbody>
        {% for row in salary_chart_rows %}
        <tr><td>{{ row.label }}</td><td>{{ row.value }}</td></tr>
        {% endfor %}
        {% if not salary_chart_rows %}
        <tr><td colspan="2">暂无薪资分布数据</td></tr>
        {% endif %}
      </tbody>
    </table>
  </div>

  <div class="chart-block">
    <div class="chart-title">技能要求 Top10 分布</div>
    {% if skills_chart_base64 %}
    <img class="chart-image" src="data:image/png;base64,{{ skills_chart_base64 }}" alt="技能要求Top10饼状图">
    {% endif %}
    <table>
      <thead><tr><th>技能</th><th>数量</th></tr></thead>
      <tbody>
        {% for row in skills_chart_rows %}
        <tr><td>{{ row.label }}</td><td>{{ row.value }}</td></tr>
        {% endfor %}
        {% if not skills_chart_rows %}
        <tr><td colspan="2">暂无技能分布数据</td></tr>
        {% endif %}
      </tbody>
    </table>
  </div>

  {% for section in sections %}
  <h2>{{ section.title }}</h2>
    {% for block in section.blocks %}
      {% if block.type == "paragraph" %}
      <p>{{ block.text }}</p>
      {% elif block.type == "bullets" %}
      <ul>
        {% for item in block.items %}
        <li>{{ item }}</li>
        {% endfor %}
      </ul>
      {% endif %}
    {% endfor %}
  {% endfor %}
</body>
</html>
"""


def _fmt_int(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{int(round(value)):,}"


class ReportGenerator:
    """按照 A-G 结构生成报告。"""

    def __init__(self, llm_generate_fn: Optional[Callable[[str], str]] = None):
        # 默认使用 mock 生成逻辑；测试环境不调用真实 LLM API。
        self.llm_generate_fn = llm_generate_fn
        self._template_env: Optional[Environment] = None
        if HAS_JINJA2:
            template_dir = self._resolve_template_dir()
            if template_dir:
                self._template_env = Environment(
                    loader=FileSystemLoader(str(template_dir)),
                    autoescape=select_autoescape(["html", "xml"]),
                )
                logger.info("PDF 模板目录已加载: %s", template_dir)
            else:
                logger.warning("未找到 report.html 模板文件，将使用内联 HTML 模板生成 PDF。")

    @staticmethod
    def _resolve_template_dir() -> Optional[Path]:
        """尝试多个候选路径以适配本地、容器和 Railway 的目录结构。"""
        current_file = Path(__file__).resolve()
        project_root = current_file.parents[2] if len(current_file.parents) >= 3 else current_file.parent
        env_template_dir = os.getenv("REPORT_TEMPLATE_DIR")

        candidates: list[Path] = []
        if env_template_dir:
            candidates.append(Path(env_template_dir).expanduser())
        candidates.extend(
            [
                current_file.parent.parent / "templates",
                project_root / "backend" / "templates",
                Path.cwd() / "backend" / "templates",
                Path.cwd() / "templates",
                Path("/app/backend/templates"),
                Path("/app/templates"),
            ]
        )

        checked: set[str] = set()
        for candidate in candidates:
            candidate_str = str(candidate)
            if candidate_str in checked:
                continue
            checked.add(candidate_str)
            template_file = candidate / "report.html"
            logger.info("尝试加载 PDF 模板路径: %s", template_file)
            if template_file.is_file():
                return candidate

        logger.error("所有候选路径均未找到 report.html，候选列表: %s", [str(path) for path in candidates])
        return None

    @staticmethod
    def _build_career_advice_prompt(
        total_jobs: int,
        salary_range: str,
        avg_applicants: float,
        top_skills: list[str],
        top_employers: list[str],
        experience_dist: dict[str, Any],
    ) -> str:
        return f"""
你是一位职业规划顾问。根据以下职位市场数据，为求职者撰写一份详细的分析建议报告。

数据：
- 样本量：{total_jobs}
- 薪资范围：{salary_range}
- 平均申请人数：{avg_applicants}
- 热门技能：{top_skills}
- 热门雇主：{top_employers}
- 经验要求分布：{experience_dist}

请从以下角度分析：
1. 市场需求分析 - 职位数量、趋势
2. 薪资分析 - 合理预期范围
3. 竞争分析 - 申请人数、难度评估
4. 技能建议 - 需要掌握的核心技能
5. 求职策略 - 具体建议

输出要求：
- 总字数 500-800 字
- 逻辑清晰，有数据支撑
- 实用性强，可操作
""".strip()

    @staticmethod
    def _build_mock_career_advice(
        total_jobs: int,
        salary_range: str,
        avg_applicants: float,
        top_skills: list[str],
        top_employers: list[str],
        experience_dist: dict[str, Any],
        trend_direction: str,
    ) -> str:
        skills_text = "、".join(top_skills[:8]) if top_skills else "Python、SQL、云平台与数据工程"
        employers_text = "、".join(top_employers[:5]) if top_employers else "头部科技公司与中大型用人企业"
        exp_text = "、".join(f"{k}:{v}" for k, v in list(experience_dist.items())[:6]) if experience_dist else "Mid/Senior 占比相对更高"
        competition_level = "高" if avg_applicants >= 80 else ("中" if avg_applicants >= 40 else "较低")

        advice = (
            f"从本次样本看，市场共覆盖 {total_jobs} 个岗位，需求趋势为 {trend_direction}。这说明相关岗位并非短期热点，而是处在持续招聘周期中。"
            f"你在投递前应先明确目标层级：若以 3-5 年经验岗位为主，就要把履历聚焦在可量化成果上，例如“提升系统稳定性”“缩短交付周期”“降低成本比例”。"
            f"薪资区间集中在 {salary_range}，建议把期望薪资拆分为“可接受区间+理想区间”，并结合城市、雇主类型、岗位职责调整谈薪策略。"
            f"若当前背景偏执行层，可优先争取进入区间中位；若已有架构、项目负责或跨团队协作经历，可争取上四分位。"
            f"竞争方面，平均申请人数约 {avg_applicants}，整体属于{competition_level}竞争。你需要把“海投”改为“精投”：每周筛选高匹配岗位，逐条对齐 JD 关键词并定制简历摘要。"
            f"技能要求上，市场高频集中在 {skills_text}，建议按“基础能力-工程化能力-业务落地能力”三层构建。基础层强调语言与数据处理，工程层强调部署、监控与自动化，落地层强调把技术转成业务指标。"
            f"雇主侧方面，{employers_text} 持续活跃，说明头部企业与稳定团队仍是主要机会来源。建议建立目标公司清单，按“岗位匹配度、成长空间、团队技术栈”打分，优先投递前 20%。"
            f"经验分布显示 {exp_text}，意味着企业更看重可直接上手能力。你可以准备 2-3 个项目案例，覆盖需求澄清、技术选型、风险处理和复盘，面试时用 STAR 结构表达。"
            "实际执行上，建议采用 4 周求职节奏：第 1 周完成简历和作品集重构，第 2 周集中投递并进行模拟面试，第 3 周复盘反馈补齐短板，第 4 周冲刺谈薪和 offer 比较。"
            "当拿到多个机会时，不只看薪资总额，还要比较岗位职责边界、导师机制和技术积累价值，避免短期薪资上涨但长期成长受限。"
        )

        # 保证在 500-800 字范围内（按字符粗略近似）。
        if len(advice) < 500:
            advice += "此外，保持固定学习节奏与输出习惯，如每周一次技术复盘、每月一次项目沉淀，有助于在竞争中形成可持续优势。"
        if len(advice) > 800:
            advice = advice[:800]
        return advice

    def generate_career_advice(self, market_insights: dict[str, Any]) -> str:
        """基于市场洞察生成中文求职建议（默认 mock LLM）。"""
        sample = market_insights.get("sample_overview", {}) or {}
        salary = market_insights.get("salary_analysis", {}) or {}
        applicant = market_insights.get("applicant_analysis", {}) or {}
        trend = market_insights.get("trend_analysis", {}) or {}
        skills = market_insights.get("skill_profile", {}) or {}
        employers = market_insights.get("employer_profile", {}) or {}
        experience_dist = market_insights.get("experience_distribution", {}) or {}

        annual = salary.get("annual", {}) or {}
        salary_range = f"{_fmt_int(annual.get('min'))} ~ {_fmt_int(annual.get('max'))} {salary.get('currency', 'AUD')}"
        top_skills = [str(item.get("skill", "")).strip() for item in (skills.get("top_skills", []) or []) if isinstance(item, dict) and item.get("skill")]
        top_employers = [str(item.get("company", "")).strip() for item in (employers.get("top_employers", []) or []) if isinstance(item, dict) and item.get("company")]
        total_jobs = int(sample.get("total_jobs") or market_insights.get("total_jobs") or 0)
        avg_applicants = float(applicant.get("avg_applicants_per_job") or 0)
        trend_direction = str(trend.get("trend", "stable")).strip() or "stable"

        prompt = self._build_career_advice_prompt(
            total_jobs=total_jobs,
            salary_range=salary_range,
            avg_applicants=avg_applicants,
            top_skills=top_skills,
            top_employers=top_employers,
            experience_dist=experience_dist if isinstance(experience_dist, dict) else {},
        )

        use_real_llm = os.getenv("ENABLE_REAL_LLM_CAREER_ADVICE", "false").lower() in {"1", "true", "yes", "on"}
        if use_real_llm and self.llm_generate_fn:
            try:
                text = (self.llm_generate_fn(prompt) or "").strip()
                if text:
                    return text[:800]
            except Exception:
                pass

        return self._build_mock_career_advice(
            total_jobs=total_jobs,
            salary_range=salary_range,
            avg_applicants=avg_applicants,
            top_skills=top_skills,
            top_employers=top_employers,
            experience_dist=experience_dist if isinstance(experience_dist, dict) else {},
            trend_direction=trend_direction,
        )

    @staticmethod
    def _strip_markdown_prefix(line: str) -> str:
        text = line.strip()
        while text.startswith("#"):
            text = text[1:].strip()
        if text.startswith("- "):
            text = f"• {text[2:]}"
        return text

    def generate_pdf(
        self,
        query: str,
        report_text: str,
        generated_at: Optional[str] = None,
        market_insights: Optional[dict[str, Any]] = None,
    ) -> bytes:
        """将 Markdown 报告文本转为专业 PDF（HTML 模板 + 图表）。"""
        if not (HAS_WEASYPRINT and HAS_JINJA2):
            return self._generate_basic_pdf_bytes(query=query, report_text=report_text, generated_at=generated_at)

        html = self._render_pdf_html(
            query=query,
            report_text=report_text,
            generated_at=generated_at,
            market_insights=market_insights or {},
        )
        return HTML(string=html).write_pdf()

    @staticmethod
    def _coerce_number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _build_pie_chart_base64(self, title: str, labels: list[str], values: list[float]) -> str:
        if not HAS_MATPLOTLIB or not labels or not values or sum(values) <= 0:
            return ""

        # 配置中文字体回退，避免标题和标签出现乱码（方框）。
        plt.rcParams["font.sans-serif"] = [
            "Noto Sans CJK SC",
            "Microsoft YaHei",
            "SimHei",
            "PingFang SC",
            "WenQuanYi Zen Hei",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False

        # 使用更高区分度的饼图配色，提升可读性。
        color_palette = [
            "#4E79A7",
            "#F28E2B",
            "#E15759",
            "#76B7B2",
            "#59A14F",
            "#EDC948",
            "#B07AA1",
            "#FF9DA7",
            "#9C755F",
            "#BAB0AC",
        ]

        fig, ax = plt.subplots(figsize=(5.6, 4.2))
        ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=135,
            colors=color_palette,
            textprops={"fontsize": 9},
        )
        ax.axis("equal")
        ax.set_title(title, fontsize=13, fontweight="bold")
        fig.tight_layout()

        chart_buffer = io.BytesIO()
        fig.savefig(chart_buffer, format="png", dpi=140, bbox_inches="tight")
        plt.close(fig)
        return base64.b64encode(chart_buffer.getvalue()).decode("utf-8")

    @staticmethod
    def _extract_salary_band_data(market_insights: dict[str, Any]) -> tuple[list[str], list[float]]:
        salary_analysis = market_insights.get("salary_analysis", {}) or {}
        bands = salary_analysis.get("bands", {}) or {}
        labels: list[str] = []
        values: list[float] = []
        for band, raw_count in bands.items():
            count = ReportGenerator._coerce_number(raw_count)
            if count > 0:
                labels.append(f"薪资区间 {band}")
                values.append(count)
        return labels, values

    @staticmethod
    def _extract_top_skills_data(market_insights: dict[str, Any], limit: int = 10) -> tuple[list[str], list[float]]:
        skill_profile = market_insights.get("skill_profile", {}) or {}
        top_skills = skill_profile.get("top_skills", []) or []
        labels: list[str] = []
        values: list[float] = []
        for item in top_skills[:limit]:
            if not isinstance(item, dict):
                continue
            skill = str(item.get("skill", "")).strip()
            count = ReportGenerator._coerce_number(item.get("count"))
            if skill and count > 0:
                labels.append(skill)
                values.append(count)
        return labels, values

    @staticmethod
    def _build_key_metrics_table(market_insights: dict[str, Any]) -> list[dict[str, str]]:
        sample = market_insights.get("sample_overview", {}) or {}
        salary = market_insights.get("salary_analysis", {}) or {}
        annual = salary.get("annual", {}) or {}
        applicant = market_insights.get("applicant_analysis", {}) or {}

        return [
            {"label": "样本职位数", "value": _fmt_int(sample.get("total_jobs"))},
            {"label": "雇主数", "value": _fmt_int(sample.get("unique_companies"))},
            {"label": "城市/地点数", "value": _fmt_int(sample.get("unique_locations"))},
            {"label": "薪资覆盖率", "value": f"{sample.get('salary_coverage_pct', 0)}%"},
            {"label": "年化平均薪资", "value": _fmt_int(annual.get("avg"))},
            {"label": "年化中位薪资", "value": _fmt_int(annual.get("median"))},
            {"label": "平均申请人数", "value": str(applicant.get("avg_applicants_per_job", 0))},
            {"label": "竞争等级", "value": str((market_insights.get("competition_intensity", {}) or {}).get("competition_level", "N/A"))},
        ]

    def _parse_report_sections(self, report_text: str) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        current: Optional[dict[str, Any]] = None
        bullet_buffer: list[str] = []

        def flush_bullets() -> None:
            nonlocal bullet_buffer, current
            if bullet_buffer and current is not None:
                current["blocks"].append({"type": "bullets", "items": bullet_buffer[:]})
                bullet_buffer = []

        for raw_line in report_text.splitlines():
            line = raw_line.strip()
            if not line:
                flush_bullets()
                continue
            if line.startswith("# "):
                continue
            if line.startswith("## "):
                flush_bullets()
                title = line[3:].strip()
                current = {"title": title, "blocks": []}
                sections.append(current)
                continue
            if current is None:
                current = {"title": "报告内容", "blocks": []}
                sections.append(current)
            if re.match(r"^[-*]\s+", line):
                bullet_buffer.append(re.sub(r"^[-*]\s+", "", line))
            else:
                flush_bullets()
                current["blocks"].append({"type": "paragraph", "text": line})

        flush_bullets()
        return sections

    def _render_pdf_html(
        self,
        query: str,
        report_text: str,
        generated_at: Optional[str],
        market_insights: dict[str, Any],
    ) -> str:
        generated_time = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        sections = self._parse_report_sections(report_text)
        key_metrics = self._build_key_metrics_table(market_insights)
        salary_labels, salary_values = self._extract_salary_band_data(market_insights)
        skill_labels, skill_values = self._extract_top_skills_data(market_insights, limit=10)

        salary_chart = self._build_pie_chart_base64(
            title="薪资范围分布",
            labels=salary_labels,
            values=salary_values,
        )
        skill_chart = self._build_pie_chart_base64(
            title="技能要求 Top10 分布",
            labels=skill_labels,
            values=skill_values,
        )
        salary_chart_rows = [{"label": label, "value": _fmt_int(value)} for label, value in zip(salary_labels, salary_values)]
        skills_chart_rows = [{"label": label, "value": _fmt_int(value)} for label, value in zip(skill_labels, skill_values)]

        context = {
            "report_title": f"{query} 市场分析报告",
            "generated_at": generated_time,
            "sections": sections,
            "key_metrics": key_metrics,
            "salary_chart_base64": salary_chart,
            "skills_chart_base64": skill_chart,
            "salary_chart_rows": salary_chart_rows,
            "skills_chart_rows": skills_chart_rows,
        }

        if self._template_env:
            try:
                template = self._template_env.get_template("report.html")
                return template.render(**context)
            except Exception:
                # 模板存在但渲染失败时回退，避免 PDF 内容退化。
                logger.exception("渲染外部 report.html 失败，将回退到内联模板。")

        return self._render_inline_html_template(context)

    def _render_inline_html_template(self, context: dict[str, Any]) -> str:
        """内联模板兜底，确保关键表格和图表相关数据可展示。"""
        if HAS_JINJA2:
            inline_env = Environment(autoescape=select_autoescape(["html", "xml"]))
            template = inline_env.from_string(INLINE_REPORT_TEMPLATE)
            return template.render(**context)

        # 理论上不会走到这里（generate_pdf 已检查 Jinja2），保留兜底避免空白页面。
        lines = [self._strip_markdown_prefix(raw) for raw in str(context.get("sections", "")).splitlines() if raw.strip()]
        body = "".join(f"<p>{escape(line)}</p>" for line in lines)
        return f"<html><body><h1>{escape(str(context.get('report_title', '报告')))}</h1>{body}</body></html>"

    @staticmethod
    def _pdf_escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _generate_basic_pdf_bytes(
        self,
        query: str,
        report_text: str,
        generated_at: Optional[str] = None,
    ) -> bytes:
        """无第三方依赖的最小 PDF 兜底实现（仅基础文本）。"""
        safe_title = "".join(ch if ord(ch) < 128 else " " for ch in f"{query} Report")
        safe_time = "".join(ch if ord(ch) < 128 else " " for ch in (generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")))
        lines = [safe_title, f"Generated at: {safe_time}", ""] + [
            "".join(ch if ord(ch) < 128 else " " for ch in self._strip_markdown_prefix(raw))
            for raw in report_text.splitlines()
            if raw.strip()
        ]
        content_stream = "BT /F1 11 Tf 50 800 Td 14 TL "
        for line in lines[:180]:
            content_stream += f"({self._pdf_escape(line[:110])}) Tj T* "
        content_stream += "ET"

        objects = [
            "<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            f"<< /Length {len(content_stream.encode('latin-1', errors='replace'))} >>\nstream\n{content_stream}\nendstream",
        ]
        out = io.BytesIO()
        out.write(b"%PDF-1.4\n")
        offsets = [0]
        for i, obj in enumerate(objects, start=1):
            offsets.append(out.tell())
            out.write(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1", errors="replace"))
        xref_start = out.tell()
        out.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        out.write(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.write(f"{off:010d} 00000 n \n".encode("latin-1"))
        out.write(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_start}\n%%EOF"
            ).encode("latin-1")
        )
        return out.getvalue()

    def generate(
        self,
        query: str,
        market_insights: dict[str, Any],
        processed_data: Optional[dict[str, Any]] = None,
        errors: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        processed_data = processed_data or {}
        errors = errors or []

        sample = market_insights.get("sample_overview", {}) or {}
        trend = market_insights.get("trend_analysis", {}) or {}
        salary = market_insights.get("salary_analysis", {}) or {}
        applicant = market_insights.get("applicant_analysis", {}) or {}
        competition = market_insights.get("competition_intensity", {}) or {}
        skills = market_insights.get("skill_profile", {}) or {}
        deep_analysis = market_insights.get("deep_analysis", {}) or {}
        employers = market_insights.get("employer_profile", {}) or {}
        top_jobs = market_insights.get("top_jobs", {}) or {}
        salary_filter_stats = processed_data.get("salary_filter_stats", {}) or {}

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        sections: dict[str, str] = {}
        sections["A"] = (
            "## A. 报告元信息\n"
            f"- 查询关键词: `{query}`\n"
            f"- 生成时间: {generated_at}\n"
            f"- 数据管道阶段: {processed_data.get('pipeline_stage', 'analyze')}\n"
            f"- 错误数: {len(errors)}\n"
        )

        filter_lines = ""
        if salary_filter_stats:
            # 在报告中展示低薪过滤统计，明确过滤前后样本变化。
            filter_lines = (
                f"- 低薪过滤前职位数: {_fmt_int(salary_filter_stats.get('total_jobs_before_filter'))}\n"
                f"- 低薪过滤后职位数: {_fmt_int(salary_filter_stats.get('total_jobs_after_filter'))}\n"
                f"- 过滤职位数: {_fmt_int(salary_filter_stats.get('filtered_low_salary_jobs'))}\n"
                f"- 过滤占比: {salary_filter_stats.get('filtered_ratio_pct', 0)}%\n"
                f"- 过滤阈值: 时薪 < {salary_filter_stats.get('hourly_threshold_aud', 24)} AUD 或年薪 < {salary_filter_stats.get('annual_threshold_aud', 50000)} AUD\n"
            )

        sections["B"] = (
            "## B. 样本概览\n"
            f"- 样本职位数: {_fmt_int(sample.get('total_jobs'))}\n"
            f"- 雇主数: {_fmt_int(sample.get('unique_companies'))}\n"
            f"- 城市/地点数: {_fmt_int(sample.get('unique_locations'))}\n"
            f"- 薪资覆盖率: {sample.get('salary_coverage_pct', 0)}%\n"
            f"- 分析覆盖率: {sample.get('analysis_coverage_pct', 0)}%\n"
            f"- 日期范围: {sample.get('date_range', {}).get('start', 'N/A')} ~ {sample.get('date_range', {}).get('end', 'N/A')}\n"
            f"{filter_lines}"
        )

        trend_items = trend.get("series", [])[:10]
        trend_lines = "\n".join(
            f"  - {item.get('date')}: {item.get('count')} 条"
            for item in trend_items
        ) or "  - 暂无有效发布日期数据"
        sections["C"] = (
            "## C. 需求侧分析\n"
            f"- 趋势方向: {trend.get('trend', 'unknown')}\n"
            f"- 日均职位量: {trend.get('avg_daily_postings', 0)}\n"
            "- 近期职位量序列:\n"
            f"{trend_lines}\n"
        )

        annual = salary.get("annual", {}) or {}
        sections["D"] = (
            "## D. 薪资分析\n"
            f"- 样本量: {_fmt_int(salary.get('count'))}\n"
            f"- 币种: {salary.get('currency', 'N/A')}\n"
            f"- 年化平均: {_fmt_int(annual.get('avg'))}\n"
            f"- 年化中位数: {_fmt_int(annual.get('median'))}\n"
            f"- 年化范围: {_fmt_int(annual.get('min'))} ~ {_fmt_int(annual.get('max'))}\n"
            f"- 四分位: P25={_fmt_int(annual.get('p25'))}, P75={_fmt_int(annual.get('p75'))}\n"
            f"- 薪资带分布: {salary.get('bands', {})}\n"
        )

        applicant_exp = applicant.get("by_experience", {}) if isinstance(applicant, dict) else {}
        applicant_salary = applicant.get("by_salary_band", {}) if isinstance(applicant, dict) else {}
        applicant_exp_lines = "\n".join(
            f"  - {level}: 平均 {item.get('avg_applicants', 0)} 人/职位（样本 {item.get('jobs', 0)}）"
            for level, item in applicant_exp.items()
            if isinstance(item, dict)
        ) or "  - 暂无按经验级别申请人数数据"
        applicant_salary_lines = "\n".join(
            f"  - {band}: 平均 {item.get('avg_applicants', 0)} 人/职位（样本 {item.get('jobs', 0)}）"
            for band, item in applicant_salary.items()
            if isinstance(item, dict)
        ) or "  - 暂无按薪资区间申请人数数据"

        sections["E"] = (
            "## E. 竞争强度\n"
            f"- 竞争等级: {competition.get('competition_level', 'unknown')}\n"
            f"- 单公司平均岗位数: {competition.get('jobs_per_company', 0)}\n"
            f"- 头部公司占比: {competition.get('top_company_share_pct', 0)}%\n"
            f"- 头部地点占比: {competition.get('top_location_share_pct', 0)}%\n"
            f"- 申请人数样本量: {_fmt_int(applicant.get('count'))}\n"
            f"- 申请人数覆盖率: {applicant.get('coverage_pct', 0)}%\n"
            f"- 平均每个职位申请人数: {applicant.get('avg_applicants_per_job', 0)}\n"
            "- 按经验级别申请人数:\n"
            f"{applicant_exp_lines}\n"
            "- 按薪资区间申请人数:\n"
            f"{applicant_salary_lines}\n"
        )

        top_skills = skills.get("top_skills", [])[:10]
        skill_lines = "\n".join(
            f"  - {item.get('skill')}: {item.get('count')}"
            for item in top_skills
        ) or "  - 暂无技能数据"
        sections["F"] = (
            "## F. 技能画像\n"
            f"- 技能总数(去重): {skills.get('total_unique_skills', 0)}\n"
            "- Top 技能:\n"
            f"{skill_lines}\n"
        )

        top_employers = employers.get("top_employers", [])[:10]
        employer_lines = "\n".join(
            f"  - {item.get('company')}: {item.get('count')}"
            for item in top_employers
        ) or "  - 暂无雇主数据"
        sections["G"] = (
            "## G. 雇主画像\n"
            f"- 雇主总数: {employers.get('unique_employers', 0)}\n"
            f"- 远程/混合岗位占比: {employers.get('remote_ratio_pct', 0)}%\n"
            f"- 雇主集中度(HHI): {employers.get('employer_concentration_hhi', 0)}\n"
            "- Top 雇主:\n"
            f"{employer_lines}\n"
        )

        top_apply_jobs = top_jobs.get("top_by_applicants", [])[:3]
        top_apply_lines = "\n".join(
            f"  - {idx}. {item.get('title', 'N/A')} | {item.get('company', 'N/A')} | 申请人数: {item.get('num_applicants', 0)} | {item.get('url', '')}"
            for idx, item in enumerate(top_apply_jobs, start=1)
        ) or "  - 暂无申请人数数据"

        top_salary_jobs = top_jobs.get("top_by_salary", [])[:3]
        top_salary_lines = "\n".join(
            f"  - {idx}. {item.get('title', 'N/A')} | {item.get('company', 'N/A')} | 薪资: {item.get('salary', 'N/A')} | {item.get('url', '')}"
            for idx, item in enumerate(top_salary_jobs, start=1)
        ) or "  - 暂无薪资数据"

        sections["H"] = (
            "## H. TOP3 职位\n"
            "- 申请人数最多 TOP3:\n"
            f"{top_apply_lines}\n"
            "- 薪资最高 TOP3:\n"
            f"{top_salary_lines}\n"
        )

        hard_skill_lines = "\n".join(
            f"  - {item.get('item')}: {item.get('count')}"
            for item in deep_analysis.get("top_hard_skills", [])[:10]
        ) or "  - 暂无硬技能数据"
        soft_skill_lines = "\n".join(
            f"  - {item.get('item')}: {item.get('count')}"
            for item in deep_analysis.get("top_soft_skills", [])[:10]
        ) or "  - 暂无软技能数据"
        industry_keyword_lines = "\n".join(
            f"  - {item.get('item')}: {item.get('count')}"
            for item in deep_analysis.get("top_industry_keywords", [])[:10]
        ) or "  - 暂无行业关键词数据"
        responsibility_lines = "\n".join(
            f"  - {item.get('item')}: {item.get('count')}"
            for item in deep_analysis.get("top_responsibility_themes", [])[:10]
        ) or "  - 暂无职责主题数据"
        qualification_lines = "\n".join(
            f"  - {item.get('item')}: {item.get('count')}"
            for item in deep_analysis.get("top_qualifications", [])[:10]
        ) or "  - 暂无任职资格数据"
        years_lines = "\n".join(
            f"  - {bucket}: {count}"
            for bucket, count in (deep_analysis.get("years_of_experience_distribution", {}) or {}).items()
        ) or "  - 暂无经验年限数据"

        sections["I"] = (
            "## I. 深度分析\n"
            "- 硬技能 Top10:\n"
            f"{hard_skill_lines}\n"
            "- 软技能 Top10:\n"
            f"{soft_skill_lines}\n"
            "- 行业关键词 Top10:\n"
            f"{industry_keyword_lines}\n"
            "- 职责主题 Top10:\n"
            f"{responsibility_lines}\n"
            "- 任职资格 Top10:\n"
            f"{qualification_lines}\n"
            "- 经验年限分布:\n"
            f"{years_lines}\n"
        )

        career_advice = self.generate_career_advice(market_insights)
        sections["J"] = (
            "## J. 求职建议\n"
            f"{career_advice}\n"
        )

        report = "\n".join(
            [
                "# Job Market Research Report",
                "# 职位市场研究报告",
                "",
                sections["A"],
                sections["B"],
                sections["C"],
                sections["D"],
                sections["E"],
                sections["F"],
                sections["G"],
                sections["H"],
                sections["I"],
                sections["J"],
            ]
        )

        return {
            "report": report,
            "report_sections": sections,
            "report_meta": {
                "query": query,
                "generated_at": generated_at,
                "section_order": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
            },
        }
