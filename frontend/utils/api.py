import httpx
from typing import Optional, List, Dict, Any

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
    
    async def search_jobs(self, query: str, location: Optional[str] = None, max_results: int = 20) -> List[Dict[str, Any]]:
        """搜索职位"""
        async with httpx.AsyncClient() as client:
            params = {"query": query, "max_results": max_results}
            if location:
                params["location"] = location
            response = await client.get(f"{self.base_url}/api/jobs/search", params=params)
            response.raise_for_status()
            return response.json()
    
    async def analyze_market(self, query: str, location: Optional[str] = None) -> Dict[str, Any]:
        """市场分析"""
        async with httpx.AsyncClient() as client:
            params = {"query": query}
            if location:
                params["location"] = location
            response = await client.get(f"{self.base_url}/api/market/analyze", params=params)
            response.raise_for_status()
            return response.json()
    
    async def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取历史记录"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/history", params={"limit": limit})
            response.raise_for_status()
            return response.json()
