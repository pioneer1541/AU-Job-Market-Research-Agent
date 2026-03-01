"""
JD Analyzer Service - 职位描述分析服务

使用 LLM 分析职位描述，提取结构化信息。
"""
import json
import logging
import re
from typing import Any, Optional

try:
    from ..agents.state import JobListing, AnalysisResult
except ImportError:
    from agents.state import JobListing, AnalysisResult

try:
    from .llm_client import LLMClient
except ImportError:
    from llm_client import LLMClient


logger = logging.getLogger(__name__)


# 系统提示 - 使用中文提高中文 JD 分析效果
SYSTEM_PROMPT = """你是一个专业的职位描述分析师。你的任务是从职位描述中提取结构化信息。

请分析职位描述，提取以下信息并以 JSON 格式返回：

1. hard_skills: 硬技能列表（技术栈、工具、框架、平台）
2. soft_skills: 软技能列表（沟通、协作、领导力等）
3. years_of_experience: 经验年限（如 "3-5年"、"5年以上"；无法判断则为 null）
4. industry_keywords: 行业关键词列表（如 "SaaS", "FinTech", "医疗信息化"）
5. responsibility_themes: 职责主题列表（如 "后端开发", "系统设计", "跨团队协作"）
6. qualifications: 任职资格列表（学历、证书、语言、硬性要求）
7. skills_required: 兼容字段，等于 hard_skills
8. experience_level: 经验级别，必须是以下之一: "Junior", "Mid", "Senior", "Lead"
9. salary_estimate: 薪资估算（如果原文没有，根据市场情况估算范围，如 "80000-120000 AUD/年"）
10. key_requirements: 兼容字段，可复用 qualifications 的关键条目
11. industry: 行业分类（如 "科技", "金融", "医疗" 等）

请只返回 JSON，不要添加任何其他文字。JSON 格式如下：
{
    "hard_skills": ["Python", "FastAPI"],
    "soft_skills": ["沟通协作", "问题解决"],
    "years_of_experience": "5年以上",
    "industry_keywords": ["SaaS", "云计算"],
    "responsibility_themes": ["后端开发", "系统设计"],
    "qualifications": ["计算机相关专业本科及以上", "具备 Python 项目经验"],
    "skills_required": ["Python", "FastAPI"],
    "experience_level": "Senior",
    "salary_estimate": "80000-120000 AUD/年",
    "key_requirements": ["要求1", "要求2", "要求3"],
    "industry": "行业"
}"""


def _normalize_string_list(value: Any) -> list[str]:
    """将 LLM 返回值标准化为字符串列表。"""
    if value is None:
        return []

    if isinstance(value, str):
        raw_items = re.split(r"[,\n;；、]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        return []

    normalized: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if not text:
            continue
        if text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_years_of_experience(value: Any) -> Optional[str]:
    """将经验年限统一为字符串表达。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return f"{int(value)}年"
    if isinstance(value, list):
        items = _normalize_string_list(value)
        return items[0] if items else None

    text = str(value).strip()
    return text or None


def parse_llm_response(response: str) -> dict:
    """
    解析 LLM 响应，提取 JSON 数据。
    
    Args:
        response: LLM 返回的文本
        
    Returns:
        解析后的字典
    """
    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 JSON 块
    json_patterns = [
        r'```json\s*([\s\S]*?)\s*```',  # ```json ... ```
        r'```\s*([\s\S]*?)\s*```',       # ``` ... ```
        r'\{[\s\S]*\}',                   # 直接匹配 {...}
    ]
    
    for pattern in json_patterns:
        match = re.search(pattern, response)
        if match:
            try:
                json_str = match.group(1) if '```' in pattern else match.group(0)
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    
    logger.warning(f"Failed to parse LLM response as JSON: {response[:200]}...")
    return {}


def validate_experience_level(level: str) -> str:
    """验证并规范化经验级别"""
    valid_levels = ["Junior", "Mid", "Senior", "Lead"]
    
    # 映射常见变体
    level_mapping = {
        "entry": "Junior",
        "junior": "Junior",
        "初级": "Junior",
        "mid": "Mid",
        "middle": "Mid",
        "中级": "Mid",
        "senior": "Senior",
        "高级": "Senior",
        "lead": "Lead",
        "principal": "Lead",
        "资深": "Senior",
        "技术负责人": "Lead",
    }
    
    normalized = level_mapping.get(level.lower().strip(), level)
    
    if normalized not in valid_levels:
        # 尝试模糊匹配
        for valid in valid_levels:
            if valid.lower() in level.lower():
                return valid
        # 默认返回 Mid
        logger.warning(f"Unknown experience level '{level}', defaulting to 'Mid'")
        return "Mid"
    
    return normalized


async def analyze_job(
    job: JobListing,
    client: Optional[LLMClient] = None,
) -> AnalysisResult:
    """
    分析单个职位描述。
    
    Args:
        job: 职位数据
        client: LLM 客户端（可选，不传则创建新客户端）
        
    Returns:
        AnalysisResult: 分析结果
    """
    # 构建分析提示
    prompt = f"""请分析以下职位描述：

职位标题: {job['title']}
公司: {job['company']}
地点: {job['location']}
{'薪资: ' + job['salary'] if job.get('salary') else ''}

职位描述:
{job['description']}

请提取结构化信息并以 JSON 格式返回。"""
    
    own_client = client is None
    
    try:
        if own_client:
            client = LLMClient()
            await client.__aenter__()
        
        # 调用 LLM
        response = await client.complete(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,  # 较低温度以获得更一致的输出
            max_tokens=1000,
        )
        
        # 解析响应
        data = parse_llm_response(response)
        
        # 构建结果
        hard_skills = _normalize_string_list(data.get("hard_skills") or data.get("skills_required"))
        soft_skills = _normalize_string_list(data.get("soft_skills"))
        industry_keywords = _normalize_string_list(data.get("industry_keywords"))
        responsibility_themes = _normalize_string_list(data.get("responsibility_themes"))
        qualifications = _normalize_string_list(data.get("qualifications"))
        if not qualifications:
            qualifications = _normalize_string_list(data.get("key_requirements"))

        result: AnalysisResult = {
            "job_id": job["id"],
            "hard_skills": hard_skills,
            "soft_skills": soft_skills,
            "years_of_experience": _normalize_years_of_experience(data.get("years_of_experience")),
            "industry_keywords": industry_keywords,
            "responsibility_themes": responsibility_themes,
            "qualifications": qualifications,
            "skills_required": hard_skills,
            "experience_level": validate_experience_level(data.get("experience_level", "Mid")),
            "salary_estimate": data.get("salary_estimate") or job.get("salary"),
            "key_requirements": qualifications[:5],
            "industry": data.get("industry") or (industry_keywords[0] if industry_keywords else None),
        }
        
        logger.info(f"Analyzed job {job['id']}: {len(result['skills_required'])} skills, {result['experience_level']} level")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to analyze job {job['id']}: {e}")
        # 返回默认结果
        return AnalysisResult(
            job_id=job["id"],
            hard_skills=[],
            soft_skills=[],
            years_of_experience=None,
            industry_keywords=[],
            responsibility_themes=[],
            qualifications=[],
            skills_required=[],
            experience_level="Mid",
            salary_estimate=job.get("salary"),
            key_requirements=[],
            industry=None,
        )
    
    finally:
        if own_client and client:
            await client.__aexit__(None, None, None)


async def analyze_jobs_batch(
    jobs: list[JobListing],
    batch_size: int = 5,
    delay_between_batches: float = 1.0,
) -> list[AnalysisResult]:
    """
    批量分析职位描述。
    
    Args:
        jobs: 职位列表
        batch_size: 每批处理数量
        delay_between_batches: 批次间延迟（秒）
        
    Returns:
        分析结果列表
    """
    import asyncio
    
    results = []
    
    async with LLMClient() as client:
        for i in range(0, len(jobs), batch_size):
            batch = jobs[i:i + batch_size]
            
            # 并发处理批次
            batch_results = await asyncio.gather(
                *[analyze_job(job, client=client) for job in batch],
                return_exceptions=True,
            )
            
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch analysis failed for job {batch[j]['id']}: {result}")
                    # 添加默认结果
                    results.append(AnalysisResult(
                        job_id=batch[j]["id"],
                        hard_skills=[],
                        soft_skills=[],
                        years_of_experience=None,
                        industry_keywords=[],
                        responsibility_themes=[],
                        qualifications=[],
                        skills_required=[],
                        experience_level="Mid",
                        salary_estimate=batch[j].get("salary"),
                        key_requirements=[],
                        industry=None,
                    ))
                else:
                    results.append(result)
            
            # 批次间延迟，避免 API 限流
            if i + batch_size < len(jobs):
                await asyncio.sleep(delay_between_batches)
    
    return results
