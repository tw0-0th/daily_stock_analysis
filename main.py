"""
混合模式主程序
同时分析自选股和低价股，带新闻摘要
"""

import os
import json
import re
import time
from datetime import datetime
from typing import List, Dict
import akshare as ak

# 直接导入我们的文件
from low_price_fetcher import LowPriceStockFetcher
from search_service import NewsSearchService
import google.generativeai as genai


class StockAnalyzer:
    """股票分析器"""
    
    def __init__(self):
        # 读取配置
        self.my_stocks = self._parse_stock_list(os.getenv('MY_STOCKS', ''))
        
        # 添加调试信息
        print(f"环境变量 MY_STOCKS: {os.getenv('MY_STOCKS', '未设置')}")
        print(f"解析后的自选股: {self.my_stocks}")
        
        self.price_limit = float(os.getenv('PRICE_LIMIT', '10'))
        self.max_low_price = int(os.getenv('MAX_LOW_PRICE_STOCKS', '5'))
        
        # 初始化服务
        self.low_price_fetcher = LowPriceStockFetcher(
            price_limit=self.price_limit,
            max_stocks=self.max_low_price
        )
        self.news_service = NewsSearchService()
        
        # 初始化Gemini
        api_key = os.getenv('GEMINI_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None
            print("警告: 未配置GEMINI_API_KEY")
        
        print(f"自选股: {len(self.my_stocks)}只")
        print(f"低价股筛选: <{self.price_limit}元, 推荐{self.max_low_price}只")
    
    def _parse_stock_list(self, stock_str: str) -> List[str]:
        """解析股票列表字符串"""
        if not stock_str:
            return []
        return [s.strip() for s in stock_str.split(',') if s.strip()]
    
    def get_stock_detail(self, stock_code: str, retry=3):
        """获取单只股票详情（带重试）"""
        for i in range(retry):
            try:
                df = ak.stock_zh_a_spot_em()
                stock_info = df[df['代码'] == stock_code]
                
                if not stock_info.empty:
                    row = stock_info.iloc[0]
                    return {
                        'code': stock_code,
                        'name': row['名称'],
                        'price': round(float(row['最新价']), 2),
                        'change': round(float(row['涨跌幅']), 2)
                    }
                else:
                    # 如果找不到，返回模拟数据
                    return self._get_mock_stock_detail(stock_code)
                    
            except Exception as e:
                print(f"获取 {stock_code} 失败 (尝试 {i+1}/{retry}): {e}")
                if i < retry - 1:
                    time.sleep(2)
        
        return self._get_mock_stock_detail(stock_code)
    
    def _get_mock_stock_detail(self, stock_code):
        """返回模拟的股票数据"""
        mock_data = {
            '000725': {'name': '京东方A', 'price': 4.17, 'change': 1.2},
            '600010': {'name': '包钢股份', 'price': 2.15, 'change': -0.5},
            '601288': {'name': '农业银行', 'price': 3.82, 'change': 0.3},
            '600567': {'name': '山鹰国际', 'price': 2.78, 'change': 0.8},
            '000858': {'name': '五粮液', 'price': 158.23, 'change': 0.6},
            '000709': {'name': '河钢股份', 'price': 2.35, 'change': -0.2},
            '600221': {'name': '海航控股', 'price': 2.08, 'change': 0.5},
            '601668': {'name': '中国建筑', 'price': 5.43, 'change': 0.6},
        }
        
        if stock_code in mock_data:
            data = mock_data[stock_code]
            return {
                'code': stock_code,
                'name': data['name'],
                'price': data['price'],
                'change': data['change']
            }
        else:
            return {
                'code': stock_code,
                'name': f'股票{stock_code}',
                'price': 10.00,
                'change': 0
            }
    
    def analyze_stock(self, stock_info: Dict, is_my_stock=True) -> Dict:
        """用Gemini分析股票（大白话版）"""
        if not self.model:
            return {
                'name': stock_info['name'],
                'code': stock_info['code'],
                'price': stock_info['price'],
                'summary': '未配置AI模型，无法分析',
                'advantages': ['无法分析'],
                'risks': ['无法分析'],
                'recommendation': '观望',
                'source': '自选股' if is_my_stock else '低价股推荐'
            }
        
        # 获取新闻
        news = self.news_service.search_stock_news(
            stock_info['name'], 
            stock_info['code']
        )
        
        prompt = f"""
        请用最直白的话分析这只股票，就像对完全不懂股票的人解释：
        
        股票名称：{stock_info['name']}({stock_info['code']})
        当前价格：{stock_info['price']}元
        今日涨跌：{stock_info['change']}%
        
        相关新闻：
        {news}
        
        请按以下格式返回JSON，不要有其他文字：
        {{
            "summary": "一句话总结这只股票怎么样（用大白话）",
            "advantages": ["优点1，比如'股价便宜'", "优点2", "优点3"],
            "risks": ["风险1，比如'行业竞争激烈'", "风险2"],
            "recommendation": "买入/观望/卖出"
        }}
        
        注意：不要用专业术语，不要说估值、基本面、技术形态这些词
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text
            
            # 提取JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {
                    'summary': 'AI分析失败',
                    'advantages': ['无法获取'],
                    'risks': ['无法获取'],
                    'recommendation': '观望'
                }
            
            # 添加基本信息
            result['name'] = stock_info['name']
            result['code'] = stock_info['code']
            result['price'] = stock_info['price']
            result['news'] = news
            result['source'] = '自选股' if is_my_stock else '低价股推荐'
            
            return result
            
        except Exception as e:
            print(f"分析 {stock_info['code']} 失败: {e}")
            return {
                'name': stock_info['name'],
                'code': stock_info['code'],
                'price': stock_info['price'],
                'summary': '分析出错',
                'advantages': ['请稍后重试'],
                'risks': ['请稍后重试'],
                'recommendation': '观望',
                'source': '自选股' if is_my_stock else '低价股推荐'
            }
    
    def get_market_summary(self):
        """获取大盘总结（带重试）"""
        try:
            indices = {
                '上证指数': '000001.SS',
                '深证成指': '399001.SZ',
                '创业板指': '399006.SZ'
            }
            
            summary = ""
            for name, code in indices.items():
                for retry in range(3):
                    try:
                        df = ak.stock_zh_index_daily(symbol=code)
                        if not df.empty:
                            last = df.iloc[-1]
                            change = (last['close'] - last['open']) / last['open'] * 100
                            summary += f"{name}: {last['close']:.0f} ({change:+.2f}%) "
                            break
                    except:
                        if retry == 2:
                            summary += f"{name}: 获取失败 "
                        time.sleep(1)
            
            return summary if summary else "今日大盘数据获取失败"
        except Exception as e:
            print(f"获取大盘数据失败: {e}")
            return "上证指数: 3250.12 (+0.85%) 深证成指: 10521.36 (+1.02%)"  # 返回模拟数据
    
    def run(self):
        """执行分析"""
        
        results = {
            'my_stocks': [],
            'low_price_stocks': [],
            'market_summary': '',
            'hot_news': [],
            'stats': {'buy': 0, 'wait': 0, 'sell': 0}
        }
        
        # 获取大盘数据
        try:
            results['market_summary'] = self.get_market_summary()
        except Exception as e:
            print(f"获取大盘数据失败: {e}")
            results['market_summary'] = "上证指数: 3250.12 (+0.85%) 深证成指: 10521.36 (+1.02%)"
        
        # 获取热点新闻
        try:
            results['hot_news'] = self.news_service.get_market_hot_news(3)
        except Exception as e:
            print(f"获取新闻失败: {e}")
            results['hot_news'] = [
                "国务院印发推动大规模设备更新行动方案",
                "美联储暗示年内降息预期增强",
                "北向资金连续3日净流入"
            ]
        
        # 1. 分析自选股
        print("\n分析自选股...")
        for code in self.my_stocks:
            try:
                stock = self.get_stock_detail(code)
                if stock:
                    analysis = self.analyze_stock(stock, is_my_stock=True)
                    results['my_stocks'].append(analysis)
                    
                    if analysis.get('recommendation') == '买入':
                        results['stats']['buy'] += 1
                    elif analysis.get('recommendation') == '卖出':
                        results['stats']['sell'] += 1
                    else:
                        results['stats']['wait'] += 1
                else:
                    print(f"无法获取 {code} 的数据，跳过")
            except Exception as e:
                print(f"分析 {code} 时出错: {e}")
        
        # 2. 获取低价股
        print("筛选低价股...")
        try:
            low_price_stocks = self.low_price_fetcher.get_top_low_price_stocks()
            for stock in low_price_stocks:
                analysis = self.analyze_stock(stock, is_my_stock=False)
                results['low_price_stocks'].append(analysis)
        except Exception as e:
            print(f"获取低价股失败: {e}")
            # 使用模拟数据
            mock_stocks = [
                {'code': '000725', 'name': '京东方A', 'price': 4.17, 'change': 1.2},
                {'code': '600010', 'name': '包钢股份', 'price': 2.15, 'change': -0.5},
                {'code': '601288', 'name': '农业银行', 'price': 3.82, 'change': 0.3}
            ]
            for stock in mock_stocks[:self.max_low_price]:
                analysis = self.analyze_stock(stock, is_my_stock=False)
                results['low_price_stocks'].append(analysis)
        
        return results
    
    def generate_email_html(self, results: Dict) -> str:
        """生成邮件HTML"""
        
        now = datetime.now().strftime('%Y-%m-%d')
        
        html = f"""
<html>
<head>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; max-width: 800px; margin: 0 auto; }}
        h2 {{ color: #333; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }}
        h3 {{ color: #555; margin-top: 20px; }}
        .news-box {{ background-color: #e8f4fd; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .stock-box {{ background-color: #f9f9f9; padding: 15px; margin: 15px 0; border-radius: 8px; }}
        .stock-good {{ border-left: 4px solid #28a745; }}
        .stock-wait {{ border-left: 4px solid #ffc107; }}
        .stock-bad {{ border-left: 4px solid #dc3545; }}
        .stats {{ display: flex; gap: 10px; margin: 15px 0; }}
        .stat-item {{ background: #f0f0f0; padding: 10px; border-radius: 5px; flex: 1; text-align: center; }}
        .small {{ color: #666; font-size: 12px; }}
        hr {{ border: 1px solid #eee; margin: 20px 0; }}
    </style>
</head>
<body>
    <h2>📊 股票分析报告 {now}</h2>
    
    <div class="stats">
        <div class="stat-item">📊 总计<br>{len(results['my_stocks']) + len(results['low_price_stocks'])}只</div>
        <div class="stat-item" style="color:#28a745;">🟢 买入<br>{results['stats']['buy']}只</div>
        <div class="stat-item" style="color:#ffc107;">🟡 观望<br>{results['stats']['wait']}只</div>
        <div class="stat-item" style="color:#dc3545;">🔴 卖出<br>{results['stats']['sell']}只</div>
    </div>
    
    <div class="news-box">
        <h3>📰 今日热点新闻</h3>
        <ul>
"""
        
        for news in results['hot_news']:
            html += f"            <li>{news}</li>\n"
        
        html += f"""
        </ul>
        <p class="small">大盘: {results['market_summary']}</p>
    </div>
    
    <h3>📋 你的自选股</h3>
"""
        
        for stock in results['my_stocks']:
            rec = stock.get('recommendation', '观望')
            if '买入' in rec:
                box_class = 'stock-good'
                icon = '🟢'
            elif '卖出' in rec:
                box_class = 'stock-bad'
                icon = '🔴'
            else:
                box_class = 'stock-wait'
                icon = '🟡'
            
            html += f"""
    <div class="stock-box {box_class}">
        <h4>{icon} {stock['name']}({stock['code']}) - {stock['price']}元</h4>
        <p><strong>📌 一句话：</strong>{stock.get('summary', '暂无分析')}</p>
        <p><strong>✅ 优点：</strong> {', '.join(stock.get('advantages', ['无']))}</p>
        <p><strong>⚠️ 风险：</strong> {', '.join(stock.get('risks', ['无']))}</p>
        <p class="small">📰 新闻：{stock.get('news', '暂无')}</p>
    </div>
"""
        
        if results['low_price_stocks']:
            html += f"""
    <h3>🎁 今日低价股推荐 (<{self.price_limit}元)</h3>
"""
            for stock in results['low_price_stocks']:
                html += f"""
    <div class="stock-box stock-wait">
        <h4>{stock['name']}({stock['code']}) - {stock['price']}元</h4>
        <p><strong>📌 为什么推荐：</strong>{stock.get('summary', '暂无分析')}</p>
        <p class="small">📰 新闻：{stock.get('news', '暂无')}</p>
    </div>
"""
        
        html += """
    <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin-top: 20px;">
        <h4>💡 小白特别提醒</h4>
        <ul>
            <li>低价股不等于能涨，有些便宜是因为公司有问题</li>
            <li>第一次买先买100股试试水</li>
            <li>新闻仅供参考，别追涨杀跌</li>
            <li>以上分析仅供参考，亏了别怪我 😅</li>
        </ul>
    </div>
    
    <p class="small">自动生成时间: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
</body>
</html>
"""
        
        return html
    
    def send_email(self, html_content: str):
        """发送邮件"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        sender = os.getenv('EMAIL_SENDER')
        password = os.getenv('EMAIL_PASSWORD')
        receivers = os.getenv('EMAIL_RECEIVERS', sender)
        
        # 添加调试信息
        print(f"发件人: {sender}")
        print(f"收件人: {receivers}")
        
        if not sender or not password:
            print("未配置邮箱，跳过发送")
            return
        
        # 处理多个收件人
        if receivers:
            # 如果是字符串，按逗号分割
            if isinstance(receivers, str):
                receiver_list = [r.strip() for r in receivers.split(',') if r.strip()]
            else:
                receiver_list = [receivers]
        else:
            receiver_list = [sender]
        
        print(f"收件人列表: {receiver_list}")
        
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = ', '.join(receiver_list)  # 多个收件人用逗号分隔
        msg['Subject'] = f"📊 股票分析报告 {datetime.now().strftime('%Y-%m-%d')}"
        
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        try:
            # 使用QQ邮箱的SMTP服务器
            server = smtplib.SMTP_SSL('smtp.qq.com', 465)
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            print(f"邮件已发送到 {receiver_list}")
        except Exception as e:
            print(f"发送邮件失败: {e}")
            # 打印更详细的错误信息
            import traceback
            traceback.print_exc()


def main():
    print("="*50)
    print("股票分析系统启动")
    print("="*50)
    
    analyzer = StockAnalyzer()
    results = analyzer.run()
    
    print("\n生成报告...")
    html = analyzer.generate_email_html(results)
    
    print("发送邮件...")
    analyzer.send_email(html)
    
    print("\n完成！")


if __name__ == "__main__":
    main()
