"""
外部工具服务 - 提供网络搜索等能力
"""
import logging
from typing import List, Dict

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

logger = logging.getLogger(__name__)

class ToolService:
    """工具服务管理器"""
    
    def __init__(self):
        self.ddgs = DDGS() if DDGS else None

    def web_search(self, query: str, max_results: int = 3) -> str:
        """
        执行网络搜索
        
        Args:
            query: 搜索关键词
            max_results: 返回结果数量
            
        Returns:
            str: 格式化后的搜索结果文本
        """
        try:
            if not self.ddgs:
                return "网络搜索不可用（未安装 ddgs 包）。"
            logger.info(f"正在执行网络搜索: {query}")
            results = self.ddgs.text(query, max_results=max_results)
            
            if not results:
                return "未找到相关网络结果。"
            
            formatted_results = []
            for i, res in enumerate(results, 1):
                title = res.get('title', '无标题')
                body = res.get('body', '')
                href = res.get('href', '')
                formatted_results.append(f"[Web结果 {i}] 标题: {title}\n来源: {href}\n摘要: {body}")
            
            return "\n\n".join(formatted_results)
            
        except Exception as e:
            logger.error(f"网络搜索失败: {e}")
            return f"网络搜索出现错误: {str(e)}"

# 单例实例
tool_service = ToolService()
