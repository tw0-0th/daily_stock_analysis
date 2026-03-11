"""
低价股数据获取器
自动筛选A股中价格低于设定值的股票
"""

import akshare as ak
import pandas as pd
import os

class LowPriceStockFetcher:
    """低价股筛选器"""
    
    def __init__(self, price_limit=10, max_stocks=5, exclude_st=True):
        self.price_limit = price_limit
        self.max_stocks = max_stocks
        self.exclude_st = exclude_st
        
    def get_all_a_stocks(self):
        """获取A股全市场实时行情"""
        try:
            df = ak.stock_zh_a_spot_em()
            df = df.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_pct'
            })
            return df
        except Exception as e:
            print(f"获取A股数据失败: {e}")
            return None
    
    def filter_low_price_stocks(self, df):
        """筛选低价股"""
        if df is None or df.empty:
            return None
            
        # 1. 按价格筛选
        mask = df['price'] <= self.price_limit
        filtered = df[mask].copy()
        
        # 2. 排除ST股
        if self.exclude_st:
            st_mask = ~filtered['name'].str.contains('ST|\\*ST', na=False)
            filtered = filtered[st_mask]
        
        # 3. 按价格升序排序
        filtered = filtered.sort_values('price')
        
        return filtered
    
    def get_top_low_price_stocks(self):
        """获取前N只低价股"""
        all_stocks = self.get_all_a_stocks()
        if all_stocks is None:
            return []
            
        low_price_stocks = self.filter_low_price_stocks(all_stocks)
        if low_price_stocks is None or low_price_stocks.empty:
            return []
            
        top_stocks = low_price_stocks.head(self.max_stocks)
        
        result = []
        for _, row in top_stocks.iterrows():
            result.append({
                'code': row['code'],
                'name': row['name'],
                'price': round(row['price'], 2)
            })
            
        return result
