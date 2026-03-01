from typing import Dict, Any
from datetime import datetime

def format_salary(salary_range: Dict[str, Any]) -> str:
    """格式化薪资范围"""
    if not salary_range:
        return "面议"
    min_val = salary_range.get("min", 0)
    max_val = salary_range.get("max", 0)
    currency = salary_range.get("currency", "AUD")
    period = salary_range.get("period", "year")
    
    if min_val and max_val:
        return f"{currency} {min_val:,.0f} - {max_val:,.0f} / {period}"
    elif min_val:
        return f"{currency} {min_val:,.0f}+ / {period}"
    elif max_val:
        return f"{currency} Up to {max_val:,.0f} / {period}"
    return "面议"

def format_date(date_str: str) -> str:
    """格式化日期"""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return date_str

def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
