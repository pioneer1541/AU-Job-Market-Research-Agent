from typing import Optional

import streamlit as st


def inject_report_styles() -> None:
    st.markdown(
        """
        <style>
            .report-card {
                background: linear-gradient(160deg, #ffffff 0%, #f8fafc 100%);
                border: 1px solid #e2e8f0;
                border-radius: 16px;
                padding: 16px 18px;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
                margin-bottom: 14px;
            }
            .report-card .label {
                color: #475569;
                font-size: 0.9rem;
                margin-bottom: 8px;
            }
            .report-card .value {
                color: #0f172a;
                font-size: 1.55rem;
                font-weight: 700;
                line-height: 1.2;
            }
            .report-card .hint {
                color: #64748b;
                font-size: 0.84rem;
                margin-top: 8px;
            }
            .section-title {
                margin: 14px 0 8px 0;
            }
            .section-title h3 {
                margin: 0;
                color: #0f172a;
                font-size: 1.3rem;
            }
            .section-title p {
                margin: 6px 0 0 0;
                color: #64748b;
                font-size: 0.92rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_meta_card(query: str, location: str, max_results: int, generated_at: str) -> None:
    location_text = location or "不限"
    st.markdown(
        (
            "<div class='report-card'>"
            "<div class='label'>报告元信息</div>"
            f"<div class='value'>{query}</div>"
            f"<div class='hint'>地点：{location_text} | 样本上限：{max_results} | 生成时间：{generated_at}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_stat_card(label: str, value: str, hint: Optional[str] = None) -> None:
    hint_html = f"<div class='hint'>{hint}</div>" if hint else ""
    st.markdown(
        (
            "<div class='report-card'>"
            f"<div class='label'>{label}</div>"
            f"<div class='value'>{value}</div>"
            f"{hint_html}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_section_title(title: str, subtitle: str = "") -> None:
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        (
            "<div class='section-title'>"
            f"<h3>{title}</h3>"
            f"{subtitle_html}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
