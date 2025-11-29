"""
添加标普500ETF数据到回测结果
"""
import pandas as pd
import json
import os
import time

try:
    import akshare as ak
except ImportError:
    print("请先安装 akshare: pip install akshare")
    exit(1)

INITIAL_CAPITAL = 100000
SP500_CODE = "513500"
SP500_NAME = "标普500ETF"

def get_sp500_data():
    """获取标普500ETF数据"""
    print(f"正在获取 {SP500_NAME} ({SP500_CODE}) 数据...")
    
    import requests
    requests.adapters.DEFAULT_RETRIES = 5
    
    for retry in range(5):
        try:
            df = ak.fund_etf_hist_em(symbol=SP500_CODE, period="daily", adjust="qfq")
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.rename(columns={
                '日期': 'date',
                '收盘': 'close'
            })
            df = df[['date', 'close']].sort_values('date').reset_index(drop=True)
            print(f"获取到 {len(df)} 条数据，从 {df['date'].min()} 到 {df['date'].max()}")
            return df
        except Exception as e:
            print(f"尝试 {retry + 1}/5 失败: {e}")
            time.sleep(3)
    
    return None

def calculate_daily_values(df, start_date, end_date):
    """计算每日收益率"""
    # 过滤日期范围
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()
    
    if len(df) == 0:
        return []
    
    # 计算买入持有收益
    start_price = df.iloc[0]['close']
    shares = int(INITIAL_CAPITAL / start_price / 100) * 100
    remaining_cash = INITIAL_CAPITAL - shares * start_price
    
    daily_values = []
    for _, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        
        total_value = remaining_cash + shares * price
        daily_values.append({
            'date': date_str,
            'total_value': total_value,
            'return': (total_value / INITIAL_CAPITAL - 1) * 100
        })
    
    return daily_values

def main():
    # 读取现有数据
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file = os.path.join(script_dir, "backtest_result.json")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    start_date = pd.to_datetime(data['meta']['start_date'])
    end_date = pd.to_datetime(data['meta']['end_date'])
    
    print(f"回测日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    # 获取标普500数据
    sp500_df = get_sp500_data()
    
    if sp500_df is None:
        print("无法获取标普500数据")
        return
    
    # 计算收益
    sp500_values = calculate_daily_values(sp500_df, start_date, end_date)
    
    if len(sp500_values) == 0:
        print("标普500数据在回测日期范围内没有数据")
        return
    
    # 计算总收益和年化收益
    total_return = sp500_values[-1]['return']
    days = (end_date - start_date).days
    annual_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100
    
    print(f"\n标普500ETF 回测结果:")
    print(f"  总收益率: {total_return:.2f}%")
    print(f"  年化收益: {annual_return:.2f}%")
    
    # 更新数据
    data['daily_values']['sp500'] = sp500_values
    data['statistics']['sp500_return'] = round(total_return, 2)
    data['statistics']['sp500_annual'] = round(annual_return, 2)
    
    # 保存更新后的数据
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n数据已更新至: {json_file}")
    
    # 同时更新 docs 目录
    docs_file = os.path.join(os.path.dirname(script_dir), "docs", "backtest_result.json")
    with open(docs_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"网页数据已更新至: {docs_file}")

if __name__ == "__main__":
    main()
