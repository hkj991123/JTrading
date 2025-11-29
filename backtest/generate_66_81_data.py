"""
生成66/81参数的回测数据
使用本地缓存数据避免网络问题
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

# ============ 配置参数 ============
ETF_CODE = "512890"
ETF_NAME = "红利低波ETF"
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 66
RSI_SELL_THRESHOLD = 81
INITIAL_CAPITAL = 100000

# 分红数据
DIVIDEND_DATA = [
    {'date': '2017-01-06', 'dividend': 0.028},
    {'date': '2018-01-05', 'dividend': 0.041},
    {'date': '2019-01-04', 'dividend': 0.058},
    {'date': '2020-01-09', 'dividend': 0.074},
    {'date': '2021-01-07', 'dividend': 0.048},
    {'date': '2022-01-06', 'dividend': 0.042},
    {'date': '2023-01-05', 'dividend': 0.072},
    {'date': '2024-01-04', 'dividend': 0.064},
    {'date': '2024-07-11', 'dividend': 0.030},
    {'date': '2025-01-06', 'dividend': 0.058},
]


def calculate_rsi(prices, period=14):
    """计算RSI指标"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    for i in range(period, len(prices)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def get_data_from_json():
    """从本地JSON文件获取数据"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "backtest_result.json")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取每日价格数据
    strategy_values = data['daily_values']['strategy']
    
    df = pd.DataFrame([{
        'date': pd.to_datetime(d['date']),
        'close': d['close']
    } for d in strategy_values])
    
    df = df.sort_values('date').reset_index(drop=True)
    
    # 提取其他基准数据
    benchmarks = {}
    for key in ['buyhold', 'buyhold_no_div', 'hs300', 'gold', 'nasdaq']:
        if key in data['daily_values'] and data['daily_values'][key]:
            benchmarks[key] = data['daily_values'][key]
    
    return df, benchmarks, data


def run_backtest(df, buy_threshold, sell_threshold):
    """执行RSI策略回测"""
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
    
    cash = INITIAL_CAPITAL
    shares = 0
    position = 0
    
    trades = []
    daily_values = []
    
    dividend_dict = {d['date']: d['dividend'] for d in DIVIDEND_DATA}
    
    for i, row in df.iterrows():
        date = row['date']
        price = row['close']
        rsi = row['rsi']
        date_str = date.strftime('%Y-%m-%d')
        
        # 处理分红
        if date_str in dividend_dict and shares > 0:
            dividend_per_share = dividend_dict[date_str]
            dividend_amount = shares * dividend_per_share
            new_shares = dividend_amount / price
            shares += new_shares
            trades.append({
                'date': date_str,
                'action': '分红再投',
                'price': price,
                'shares': new_shares,
                'amount': dividend_amount,
                'rsi': rsi if pd.notna(rsi) else None,
                'total_shares': shares,
                'cash': cash
            })
        
        # RSI信号判断
        if pd.notna(rsi):
            if rsi < buy_threshold and position == 0:
                shares_to_buy = int(cash / price / 100) * 100
                if shares_to_buy > 0:
                    cost = shares_to_buy * price
                    cash -= cost
                    shares += shares_to_buy
                    position = 1
                    trades.append({
                        'date': date_str,
                        'action': '买入',
                        'price': price,
                        'shares': shares_to_buy,
                        'amount': cost,
                        'rsi': rsi,
                        'total_shares': shares,
                        'cash': cash
                    })
                    
            elif rsi > sell_threshold and position == 1:
                if shares > 0:
                    sell_shares = int(shares / 100) * 100
                    if sell_shares > 0:
                        revenue = sell_shares * price
                        cash += revenue
                        shares -= sell_shares
                        if shares < 100:
                            cash += shares * price
                            shares = 0
                        position = 0
                        trades.append({
                            'date': date_str,
                            'action': '卖出',
                            'price': price,
                            'shares': sell_shares,
                            'amount': revenue,
                            'rsi': rsi,
                            'total_shares': shares,
                            'cash': cash
                        })
        
        total_value = cash + shares * price
        daily_values.append({
            'date': date_str,
            'close': price,
            'rsi': rsi if pd.notna(rsi) else None,
            'cash': cash,
            'shares': shares,
            'total_value': total_value,
            'return': (total_value / INITIAL_CAPITAL - 1) * 100
        })
    
    return trades, daily_values


def calculate_statistics(daily_values, trades):
    """计算统计指标"""
    if not daily_values:
        return {}
    
    returns = [d['return'] for d in daily_values]
    values = [d['total_value'] for d in daily_values]
    
    # 计算最大回撤
    peak = values[0]
    max_drawdown = 0
    for v in values:
        if v > peak:
            peak = v
        drawdown = (peak - v) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # 计算年化收益
    days = len(daily_values)
    total_return = returns[-1]
    annual_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100 if days > 0 else 0
    
    # 交易统计
    buy_trades = [t for t in trades if t['action'] == '买入']
    sell_trades = [t for t in trades if t['action'] == '卖出']
    
    wins = 0
    for i, sell in enumerate(sell_trades):
        if i < len(buy_trades):
            if sell['price'] > buy_trades[i]['price']:
                wins += 1
    win_rate = (wins / len(sell_trades) * 100) if sell_trades else 0
    
    return {
        'total_return': round(total_return, 2),
        'annual_return': round(annual_return, 2),
        'max_drawdown': round(max_drawdown, 2),
        'trade_count': len(buy_trades),
        'win_rate': round(win_rate, 2),
        'start_date': daily_values[0]['date'],
        'end_date': daily_values[-1]['date'],
        'days': days
    }


def main():
    print("=" * 60)
    print(f"生成 RSI({RSI_BUY_THRESHOLD}/{RSI_SELL_THRESHOLD}) 回测数据")
    print("=" * 60)
    
    # 1. 获取数据
    df, benchmarks, old_data = get_data_from_json()
    print(f"从本地JSON获取到 {len(df)} 条数据")
    print(f"数据范围: {df['date'].min()} 至 {df['date'].max()}")
    
    # 2. 执行回测
    print(f"\n执行 RSI < {RSI_BUY_THRESHOLD} 买入, > {RSI_SELL_THRESHOLD} 卖出 策略...")
    trades, strategy_values = run_backtest(df, RSI_BUY_THRESHOLD, RSI_SELL_THRESHOLD)
    
    # 3. 计算统计
    strategy_stats = calculate_statistics(strategy_values, trades)
    
    print(f"\n【RSI策略 {RSI_BUY_THRESHOLD}/{RSI_SELL_THRESHOLD}】")
    print(f"  总收益率: {strategy_stats['total_return']:.2f}%")
    print(f"  年化收益: {strategy_stats['annual_return']:.2f}%")
    print(f"  最大回撤: {strategy_stats['max_drawdown']:.2f}%")
    print(f"  交易次数: {strategy_stats['trade_count']} 次")
    print(f"  胜率: {strategy_stats['win_rate']:.2f}%")
    
    # 打印交易记录
    print("\n【交易记录】")
    for t in trades:
        if t['action'] in ['买入', '卖出']:
            print(f"  {t['date']} {t['action']} @ {t['price']:.3f} (RSI={t['rsi']:.2f})")
    
    # 4. 保留原有基准数据的统计
    old_stats = old_data['statistics']
    backtest_days = strategy_stats['days']
    
    # 5. 准备导出数据
    export_data = {
        'meta': {
            'etf_code': ETF_CODE,
            'etf_name': ETF_NAME,
            'strategy': f'RSI({RSI_PERIOD}) < {RSI_BUY_THRESHOLD} 买入, > {RSI_SELL_THRESHOLD} 卖出',
            'initial_capital': INITIAL_CAPITAL,
            'start_date': strategy_stats['start_date'],
            'end_date': strategy_stats['end_date'],
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'statistics': {
            'strategy': strategy_stats,
            'buyhold': old_stats['buyhold'],
            'buyhold_no_div_return': old_stats.get('buyhold_no_div_return'),
            'buyhold_no_div_annual': old_stats.get('buyhold_no_div_annual'),
            'hs300_return': old_stats.get('hs300_return'),
            'hs300_annual': old_stats.get('hs300_annual'),
            'gold_return': old_stats.get('gold_return'),
            'gold_annual': old_stats.get('gold_annual'),
            'nasdaq_return': old_stats.get('nasdaq_return'),
            'nasdaq_annual': old_stats.get('nasdaq_annual'),
            'backtest_days': backtest_days,
        },
        'trades': trades,
        'daily_values': {
            'strategy': strategy_values,
            'buyhold': benchmarks.get('buyhold', []),
            'buyhold_no_div': benchmarks.get('buyhold_no_div', []),
            'hs300': benchmarks.get('hs300', []),
            'gold': benchmarks.get('gold', []),
            'nasdaq': benchmarks.get('nasdaq', []),
        }
    }
    
    # 6. 保存文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 保存到backtest目录
    output_file = os.path.join(script_dir, "backtest_result.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    print(f"\n回测结果已保存至: {output_file}")
    
    # 保存到docs目录
    docs_output = os.path.join(os.path.dirname(script_dir), "docs", "backtest_result.json")
    with open(docs_output, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False)
    print(f"网页数据已保存至: {docs_output}")
    
    print("\n" + "=" * 60)
    print("完成！")


if __name__ == "__main__":
    main()
