"""
LLM Client - OpenAI Compatible Interface

使用 OpenAI 兼容接口调用 LLM 服务。
支持异步调用，配置从环境变量读取。
"""
import asyncio
import logging
from typing import Optional, Any
from openai import AsyncOpenAI
from openai import RateLimitError, APIError, APIConnectionError

try:
    from ..config import get_settings
except ImportError:
    from config import get_settings


logger = logging.getLogger(__name__)


class LLMClient:
    """
    异步 LLM 客户端，使用 OpenAI 兼容接口。
    
    特性:
    - 支持异步调用
    - 自动重试（限流、网络错误）
    - 从环境变量读取配置
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        settings = get_settings()
        
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        if not self.api_key:
            raise ValueError("LLM API key is required. Set LLM_API_KEY environment variable.")
        
        self._client: Optional[AsyncOpenAI] = None
    
    async def __aenter__(self) -> "LLMClient":
        """异步上下文管理器入口"""
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._client:
            await self._client.close()
            self._client = None
    
    @property
    def client(self) -> AsyncOpenAI:
        """获取底层 AsyncOpenAI 客户端"""
        if not self._client:
            raise RuntimeError("LLMClient must be used as async context manager")
        return self._client
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> str:
        """
        发送补全请求到 LLM。
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示（可选）
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数传递给 API
            
        Returns:
            LLM 响应文本
            
        Raises:
            RateLimitError: 超过重试次数后仍被限流
            APIError: API 错误
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                
                return response.choices[0].message.content or ""
                
            except RateLimitError as e:
                last_error = e
                wait_time = self.retry_delay * (2 ** attempt)  # 指数退避
                logger.warning(f"Rate limit hit, retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                
            except APIConnectionError as e:
                last_error = e
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(f"Connection error, retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                
            except APIError as e:
                # 对于其他 API 错误，不重试
                logger.error(f"API error: {e}")
                raise
        
        # 所有重试都失败了
        logger.error(f"All retries exhausted: {last_error}")
        raise last_error or APIError("Unknown error after retries")
    
    async def close(self):
        """关闭客户端连接"""
        if self._client:
            await self._client.close()
            self._client = None


# 便捷函数
async def get_llm_response(
    prompt: str,
    system_prompt: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    快速获取 LLM 响应的便捷函数。
    
    用法:
        response = await get_llm_response("Hello!")
    """
    async with LLMClient() as client:
        return await client.complete(prompt, system_prompt=system_prompt, **kwargs)
