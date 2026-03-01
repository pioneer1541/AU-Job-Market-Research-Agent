import streamlit as st
import sys

sys.path.insert(0, '.')
from utils.api import get_default_api_url

st.set_page_config(
    page_title="Job Market Research",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Job Market Research Agent")
st.markdown("AI 驱动的职位市场研究工具")

# 侧边栏配置
if "api_url" not in st.session_state:
    st.session_state["api_url"] = get_default_api_url()

with st.sidebar:
    st.header("配置")
    api_url = st.text_input("API 地址", value=st.session_state["api_url"], key="app_api_url")
    st.session_state["api_url"] = (api_url or get_default_api_url()).rstrip("/")
    st.caption("优先使用侧边栏配置；未配置时读取环境变量 `BACKEND_URL`、`JOB_MARKET_API_URL` 或 `API_BASE_URL`。")
    
# 主要功能导航
st.markdown("""
### 功能
1. **职位搜索** - 搜索和分析职位
2. **市场分析** - 查看市场趋势
3. **历史记录** - 查看过往研究
""")
