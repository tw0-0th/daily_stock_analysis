"""
新闻搜索服务
"""

import os
import requests
from typing import List, Dict

class NewsSearchService:
    """新闻搜索服务"""
    
    def __init__(self):
        self.tavily_api_keys = self._parse_api_keys(os.getenv('TAVILY_API_KEYS', ''))
        self.max_age_days = int(os.getenv('NEWS_MAX_AGE_DAYS', '3'))
        
    def _parse_api_keys(self, keys_str: str) -> List[str]:
        if not keys_str:
            return []
        return [k.strip() for k in keys_str.split(',') if k.strip()]
    
    def search_stock_news(self, stock_name: str, stock_code: str) -> str:
        """搜索单只股票的新闻，返回摘要"""
        if not self.tavily_api_keys:
            return "暂无新闻"
        
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": self.tavily_api_keys[0],
                "query": f"{stock_name} {stock_code} 股票 新闻",
                "search_depth": "basic",
                "max_results": 2
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if results:
                    titles = [f"• {r['title'][:40]}..." for r in results[:2]]
                    return "\n".join(titles)
            return "暂无新闻"
        except:
            return "暂无新闻"
    
    def get_market_hot_news(self, max_items: int = 3) -> List[str]:
        """获取市场热点新闻"""
        if not self.tavily_api_keys:
            return []
        
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": self.tavily_api_keys[0],
                "query": "A股 热点 新闻 要闻",
                "search_depth": "basic",
                "max_results": max_items
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                return [r['title'] for r in results[:max_items]]
            return []
        except:
            return []
