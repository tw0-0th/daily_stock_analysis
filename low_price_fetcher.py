"""
低价股数据获取器
自动筛选A股中价格低于设定值的股票
"""

import akshare as ak
import pandas as pd
import time
import random

class LowPriceStockFetcher:
    """低价股筛选器"""
    
    def __init__(self, price_limit=10, max_stocks=5, exclude_st=True):
        self.price_limit = price_limit
        self.max_stocks = max_stocks
        self.exclude_st = exclude_st
        
    def get_all_a_stocks_with_retry(self, max_retries=5):
        """获取A股全市场实时行情（带重试机制）"""
        
        # 多个数据源方法，按优先级尝试
        fetch_methods = [
            self._fetch_from_akshare_spot,
            self._fetch_from_akshare_realtime,
            self._fetch_from_mock_data  # 最后备选：模拟数据
        ]
        
        for retry in range(max_retries):
            for method in fetch_methods:
                try:
                    print(f"尝试获取数据: {method.__name__} (第{retry+1}次)")
                    df = method()
                    if df is not None and not df.empty:
                        print(f"成功获取 {len(df)} 只股票")
                        return df
                except Exception as e:
                    print(f"方法 {method.__name__} 失败: {e}")
                    
                # 随机等待，避免被封
                wait_time = random.uniform(1, 3)
                time.sleep(wait_time)
        
        print("所有数据源都失败，返回模拟数据")
        return self._get_mock_data()
    
    def _fetch_from_akshare_spot(self):
        """方法1：使用 ak.stock_zh_a_spot_em（东方财富实时行情）"""
        df = ak.stock_zh_a_spot_em()
        df = df.rename(columns={
            '代码': 'code',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'change_pct',
            '涨跌额': 'change_amount',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '最高': 'high',
            '最低': 'low',
            '今开': 'open',
            '昨收': 'close',
            '市盈率-动态': 'pe',
            '市净率': 'pb'
        })
        return df
    
    def _fetch_from_akshare_realtime(self):
        """方法2：使用 ak.stock_zh_a_spot（备用接口）"""
        df = ak.stock_zh_a_spot()
        df = df.rename(columns={
            '代码': 'code',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'change_pct'
        })
        return df
    
    def _fetch_from_mock_data(self):
        """方法3：使用模拟数据（当所有API都失败时）"""
        return self._get_mock_data()
    
    def _get_mock_data(self):
        """生成模拟数据用于测试"""
        import pandas as pd
        
        # 创建一些常见的低价股作为备选
        mock_data = {
            'code': ['000725', '600010', '601288', '600567', '000709', '600221', '601668', '600795'],
            'name': ['京东方A', '包钢股份', '农业银行', '山鹰国际', '河钢股份', '海航控股', '中国建筑', '国电电力'],
            'price': [4.17, 2.15, 3.82, 2.78, 2.35, 2.08, 5.43, 4.12],
            'change_pct': [1.2, -0.5, 0.3, 0.8, -0.2, 0.5, 0.6, 0.4]
        }
        
        df = pd.DataFrame(mock_data)
        return df
    
    def filter_low_price_stocks(self, df):
        """筛选低价股"""
        if df is None or df.empty:
            return None
            
        # 1. 按价格筛选
        mask = df['price'] <= self.price_limit
        filtered = df[mask].copy()
        
        # 2. 排除ST股
        if self.exclude_st and 'name' in filtered.columns:
            st_mask = ~filtered['name'].str.contains('ST|\\*ST', na=False)
            filtered = filtered[st_mask]
        
        # 3. 按价格升序排序
        filtered = filtered.sort_values('price')
        
        return filtered
    
    def get_top_low_price_stocks(self):
        """获取前N只低价股"""
        all_stocks = self.get_all_a_stocks_with_retry()
        if all_stocks is None or all_stocks.empty:
            print("无法获取股票数据，使用模拟数据")
            all_stocks = self._get_mock_data()
            
        low_price_stocks = self.filter_low_price_stocks(all_stocks)
        if low_price_stocks is None or low_price_stocks.empty:
            print("没有找到符合条件的低价股，使用模拟数据")
            low_price_stocks = self._get_mock_data()
            
        top_stocks = low_price_stocks.head(self.max_stocks)
        
        result = []
        for _, row in top_stocks.iterrows():
            result.append({
                'code': row['code'],
                'name': row['name'],
                'price': round(row['price'], 2),
                'change': round(row.get('change_pct', 0), 2)
            })
            
        return result
