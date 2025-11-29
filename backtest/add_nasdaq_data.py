"""
添加纳指ETF数据到回测结果
"""
import pandas as pd
import json
import os
import time
import requests

try:
    import akshare as ak
except ImportError:
    print("请先安装 akshare: pip install akshare")
    exit(1)

INITIAL_CAPITAL = 100000
NASDAQ_CODE = "159941"
NASDAQ_NAME = "纳指ETF"

def get_nasdaq_data():
    """获取纳指ETF数据"""
    print(f"正在获取 {NASDAQ_NAME} ({NASDAQ_CODE}) 数据...")
    
    requests.adapters.DEFAULT_RETRIES = 5
    
    for retry in range(5):
        try:
            df = ak.fund_etf_hist_em(symbol=NASDAQ_CODE, period="daily", adjust="qfq")
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
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()
    
    if len(df) == 0:
        return []
    
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file = os.path.join(script_dir, "backtest_result.json")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    start_date = pd.to_datetime(data['meta']['start_date'])
    end_date = pd.to_datetime(data['meta']['end_date'])
    
    print(f"回测日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    nasdaq_df = get_nasdaq_data()
    
    if nasdaq_df is None:
        print("无法获取纳指ETF数据")
        return
    
    nasdaq_values = calculate_daily_values(nasdaq_df, start_date, end_date)
    
    if len(nasdaq_values) == 0:
        print("纳指ETF数据在回测日期范围内没有数据")
        return
    
    total_return = nasdaq_values[-1]['return']
    days = (end_date - start_date).days
    annual_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100
    
    print(f"\n纳指ETF 回测结果:")
    print(f"  总收益率: {total_return:.2f}%")
    print(f"  年化收益: {annual_return:.2f}%")
    
    data['daily_values']['nasdaq'] = nasdaq_values
    data['statistics']['nasdaq_return'] = round(total_return, 2)
    data['statistics']['nasdaq_annual'] = round(annual_return, 2)
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n数据已更新至: {json_file}")
    
    docs_file = os.path.join(os.path.dirname(script_dir), "docs", "backtest_result.json")
    with open(docs_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"网页数据已更新至: {docs_file}")

if __name__ == "__main__":
    main()
