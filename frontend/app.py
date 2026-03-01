import streamlit as st

st.set_page_config(
    page_title="Job Market Research",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Job Market Research Agent")
st.markdown("AI 驱动的职位市场研究工具")

# 侧边栏配置
with st.sidebar:
    st.header("配置")
    api_url = st.text_input("API 地址", value="http://localhost:8000")
    
# 主要功能导航
st.markdown("""
### 功能
1. **职位搜索** - 搜索和分析职位
2. **市场分析** - 查看市场趋势
3. **历史记录** - 查看过往研究
""")
