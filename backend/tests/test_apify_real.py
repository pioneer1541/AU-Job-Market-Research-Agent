"""
真实 Apify API 调用测试

此测试会真实调用 Apify Seek Scraper API（付费 API）。
仅在用户明确批准后运行。

运行方式：
    python -m pytest backend/tests/test_apify_real.py -v -s

或直接运行：
    python backend/tests/test_apify_real.py
"""
import sys
import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Any

# 先加载 .env 文件
from dotenv import load_dotenv
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
load_dotenv(project_root / ".env")
load_dotenv()  # 也尝试从当前目录加载

# Add backend to path
sys.path.insert(0, str(backend_dir))

import pytest

# 配置详细日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Fixtures 目录
FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_DIR.mkdir(exist_ok=True)

# 测试参数
SEARCH_QUERY = "AI Engineer"
LOCATION = "Melbourne"
MAX_ITEMS = 5  # 减少 API 消耗


def check_api_token() -> bool:
    """检查 API Token 是否可用"""
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        logger.warning("APIFY_API_TOKEN 环境变量未设置")
        return False
    if token == "your_apify_token_here":
        logger.warning("APIFY_API_TOKEN 是占位符，请设置真实 token")
        return False
    logger.info(f"APIFY_API_TOKEN 已加载: {token[:15]}...")
    return True


@pytest.mark.skipif(
    not check_api_token(),
    reason="APIFY_API_TOKEN 未设置或是占位符"
)
@pytest.mark.asyncio
async def test_real_seek_scraper():
    """
    真实调用 Apify Seek Scraper

    查询墨尔本 AI Engineer 职位，保存原始数据到 fixtures 目录。
    """
    from services.apify_client import ApifyClient, ApifyError

    logger.info(f"=" * 60)
    logger.info(f"开始真实 API 调用")
    logger.info(f"查询: {SEARCH_QUERY}")
    logger.info(f"地点: {LOCATION}")
    logger.info(f"最大数量: {MAX_ITEMS}")
    logger.info(f"=" * 60)

    raw_results = None
    parsed_results = []

    try:
        async with ApifyClient() as client:
            logger.info("Apify 客户端初始化成功")

            # 调用 Seek Scraper
            logger.info("启动 Seek Scraper Actor...")
            raw_results = await client.run_seek_scraper(
                search_query=SEARCH_QUERY,
                location=LOCATION,
                max_items=MAX_ITEMS
            )

            logger.info(f"API 返回 {len(raw_results)} 条原始数据")

            # 解析数据
            for i, raw_job in enumerate(raw_results, 1):
                try:
                    parsed = ApifyClient.parse_to_job_listing(raw_job)
                    parsed_results.append(parsed)
                    logger.info(f"  [{i}] {parsed['title']} @ {parsed['company']}")
                except Exception as e:
                    logger.warning(f"  [{i}] 解析失败: {e}")

    except ApifyError as e:
        logger.error(f"Apify API 错误: {e}")
        raise
    except Exception as e:
        logger.error(f"未知错误: {type(e).__name__}: {e}")
        raise

    # 保存原始数据到 fixtures
    if raw_results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存完整原始数据
        raw_file = FIXTURES_DIR / f"seek_response_{timestamp}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(raw_results, f, ensure_ascii=False, indent=2)
        logger.info(f"原始数据已保存: {raw_file}")

        # 同时保存为标准文件名（用于 mock 测试）
        standard_file = FIXTURES_DIR / "seek_response.json"
        with open(standard_file, "w", encoding="utf-8") as f:
            json.dump(raw_results, f, ensure_ascii=False, indent=2)
        logger.info(f"标准文件已更新: {standard_file}")

    # 验证结果
    assert raw_results is not None, "API 未返回数据"
    assert len(raw_results) > 0, "API 返回空列表"
    assert len(parsed_results) > 0, "没有成功解析的数据"

    logger.info(f"=" * 60)
    logger.info(f"测试完成！成功获取 {len(parsed_results)} 条职位数据")
    logger.info(f"=" * 60)


def test_load_fixture():
    """
    测试加载 fixtures 数据（不需要 API）
    """
    fixture_file = FIXTURES_DIR / "seek_response.json"

    if not fixture_file.exists():
        pytest.skip(f"Fixture 文件不存在: {fixture_file}")

    with open(fixture_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"加载 fixture: {len(data)} 条数据")
    assert isinstance(data, list), "Fixture 应该是列表格式"

    # 显示第一条数据结构
    if data:
        first = data[0]
        logger.info(f"第一条数据的字段: {list(first.keys())}")


if __name__ == "__main__":
    """直接运行此脚本"""
    import argparse

    parser = argparse.ArgumentParser(description="真实 Apify API 测试")
    parser.add_argument("--save-only", action="store_true", 
                       help="仅保存数据，不运行 pytest")
    args = parser.parse_args()

    if args.save_only:
        # 仅保存数据模式
        async def save_data():
            if not check_api_token():
                print("错误: APIFY_API_TOKEN 未设置")
                return

            from services.apify_client import ApifyClient

            print(f"正在获取 {SEARCH_QUERY} 在 {LOCATION} 的职位数据...")

            async with ApifyClient() as client:
                results = await client.run_seek_scraper(
                    search_query=SEARCH_QUERY,
                    location=LOCATION,
                    max_items=MAX_ITEMS
                )

            # 保存数据
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            raw_file = FIXTURES_DIR / f"seek_response_{timestamp}.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"已保存: {raw_file}")

            standard_file = FIXTURES_DIR / "seek_response.json"
            with open(standard_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"已更新: {standard_file}")

            print(f"\n获取到 {len(results)} 条职位数据:")
            for i, job in enumerate(results[:5], 1):
                title = job.get("title", "N/A")
                company = job.get("companyProfile", {}).get("name", 
                         job.get("advertiser", {}).get("name", "Unknown"))
                print(f"  {i}. {title} @ {company}")

        asyncio.run(save_data())
    else:
        # 运行 pytest
        pytest.main([__file__, "-v", "-s"])