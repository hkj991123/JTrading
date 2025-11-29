"""
生成多组RSI策略参数的回测数据
包含 66/81, 68/71, 72/81 三组策略曲线

注意：512890是累积型ETF，分红已自动再投资体现在价格中，无需额外处理分红
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
INITIAL_CAPITAL = 100000

# 多组策略参数（按回测收益率排序）
STRATEGIES = [
    {'buy': 34, 'sell': 78, 'name': 'strategy_34_78', 'label': 'RSI(14) 34/78', 'primary': True},
    {'buy': 36, 'sell': 78, 'name': 'strategy_36_78', 'label': 'RSI(14) 36/78'},
    {'buy': 66, 'sell': 81, 'name': 'strategy_66_81', 'label': 'RSI(14) 66/81'},
]

# 理想化策略参数（EMA平滑，小数份额 - 等同ETF联结基金交易）
IDEAL_STRATEGY = {
    'rsi_period': 15,
    'buy': 32, 
    'sell': 77, 
    'name': 'strategy_ideal_15_32_77', 
    'label': 'RSI(15) 32/77 联结基金'
}


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


def calculate_rsi_ema(prices, period):
    """计算RSI指标（使用EMA平滑，更敏感）"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    # 使用EMA而非SMA
    alpha = 1 / period
    avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def run_backtest_ideal(df, rsi_period, buy_threshold, sell_threshold):
    """执行理想化RSI策略回测（允许小数份额，EMA平滑）"""
    df = df.copy()
    df['rsi'] = calculate_rsi_ema(df['close'], rsi_period)
    
    cash = float(INITIAL_CAPITAL)
    shares = 0.0
    position = 0
    
    trades = []
    daily_values = []
    
    for i, row in df.iterrows():
        date = row['date']
        price = row['close']
        rsi = row['rsi']
        date_str = date.strftime('%Y-%m-%d')
        
        if pd.notna(rsi):
            if rsi < buy_threshold and position == 0:
                # 全仓买入（允许小数份额）
                shares = cash / price
                cost = cash
                cash = 0.0
                position = 1
                trades.append({
                    'date': date_str,
                    'action': '买入',
                    'price': price,
                    'shares': shares,
                    'amount': cost,
                    'rsi': rsi,
                    'total_shares': shares,
                    'cash': cash
                })
                    
            elif rsi > sell_threshold and position == 1:
                # 全仓卖出
                revenue = shares * price
                cash = revenue
                sell_shares = shares
                shares = 0.0
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
    for key in ['buyhold', 'buyhold_no_div', 'hs300', 'gold', 'nasdaq', 'sp500']:
        if key in data['daily_values'] and data['daily_values'][key]:
            benchmarks[key] = data['daily_values'][key]
    
    return df, benchmarks, data


def run_backtest(df, buy_threshold, sell_threshold):
    """执行RSI策略回测
    
    注意：512890是累积型ETF，分红已体现在价格中，无需处理分红
    """
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
    
    cash = INITIAL_CAPITAL
    shares = 0
    position = 0
    
    trades = []
    daily_values = []
    
    for i, row in df.iterrows():
        date = row['date']
        price = row['close']
        rsi = row['rsi']
        date_str = date.strftime('%Y-%m-%d')
        
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
    
    # 计算年化收益（使用自然日天数，而非交易日数）
    trading_days = len(daily_values)
    total_return = returns[-1]
    # 计算起止日期的自然天数
    start_date = datetime.strptime(daily_values[0]['date'], '%Y-%m-%d')
    end_date = datetime.strptime(daily_values[-1]['date'], '%Y-%m-%d')
    calendar_days = (end_date - start_date).days
    annual_return = ((1 + total_return / 100) ** (365 / calendar_days) - 1) * 100 if calendar_days > 0 else 0
    
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
        'days': trading_days,
        'calendar_days': calendar_days
    }


def calculate_buy_and_hold(df):
    """计算买入持有策略
    
    注意：512890是累积型ETF，分红已体现在前复权价格中
    """
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
    print("=" * 60)
    print("生成多组RSI策略回测数据")
    print("=" * 60)
    
    # 1. 获取数据
    df, benchmarks, old_data = get_data_from_json()
    print(f"从本地JSON获取到 {len(df)} 条数据")
    print(f"数据范围: {df['date'].min()} 至 {df['date'].max()}")
    
    # 2. 执行所有策略回测
    all_results = {}
    primary_strategy = None  # 主策略 (66/81)
    primary_trades = None
    
    for strategy in STRATEGIES:
        buy = strategy['buy']
        sell = strategy['sell']
        name = strategy['name']
        label = strategy['label']
        
        print(f"\n执行 {label} 策略...")
        trades, daily_values = run_backtest(df, buy, sell)
        stats = calculate_statistics(daily_values, trades)
        
        all_results[name] = {
            'trades': trades,
            'daily_values': daily_values,
            'stats': stats,
            'label': label,
            'buy': buy,
            'sell': sell
        }
        
        # 保存主策略 (34/78 - 最优参数)
        if strategy.get('primary'):
            primary_strategy = all_results[name]
            primary_trades = trades
        
        print(f"  总收益率: {stats['total_return']:.2f}%")
        print(f"  年化收益: {stats['annual_return']:.2f}%")
        print(f"  最大回撤: {stats['max_drawdown']:.2f}%")
        print(f"  交易次数: {stats['trade_count']} 次")
    
    # 3. 执行理想化策略 RSI(15) EMA 32/77
    print(f"\n执行 {IDEAL_STRATEGY['label']} 策略...")
    ideal_trades, ideal_daily_values = run_backtest_ideal(
        df, 
        IDEAL_STRATEGY['rsi_period'], 
        IDEAL_STRATEGY['buy'], 
        IDEAL_STRATEGY['sell']
    )
    ideal_stats = calculate_statistics(ideal_daily_values, ideal_trades)
    
    all_results[IDEAL_STRATEGY['name']] = {
        'trades': ideal_trades,
        'daily_values': ideal_daily_values,
        'stats': ideal_stats,
        'label': IDEAL_STRATEGY['label'],
        'buy': IDEAL_STRATEGY['buy'],
        'sell': IDEAL_STRATEGY['sell'],
        'rsi_period': IDEAL_STRATEGY['rsi_period']
    }
    
    print(f"  总收益率: {ideal_stats['total_return']:.2f}%")
    print(f"  年化收益: {ideal_stats['annual_return']:.2f}%")
    print(f"  最大回撤: {ideal_stats['max_drawdown']:.2f}%")
    print(f"  交易次数: {ideal_stats['trade_count']} 次")
    
    # 4. 计算买入持有收益（无需分红处理）
    print("\n计算买入持有收益...")
    buyhold_values = calculate_buy_and_hold(df)
    buyhold_stats = calculate_statistics(buyhold_values, [])
    print(f"  总收益率: {buyhold_stats['total_return']:.2f}%")
    print(f"  年化收益: {buyhold_stats['annual_return']:.2f}%")
    
    # 5. 保留原有基准数据的统计
    old_stats = old_data['statistics']
    backtest_days = primary_strategy['stats']['days']
    
    # 5. 准备导出数据
    export_data = {
        'meta': {
            'etf_code': ETF_CODE,
            'etf_name': ETF_NAME,
            'strategy': 'RSI(14) < 34 买入, > 78 卖出 (最优参数)',
            'strategies': [{'buy': s['buy'], 'sell': s['sell'], 'label': s['label']} for s in STRATEGIES],
            'initial_capital': INITIAL_CAPITAL,
            'start_date': primary_strategy['stats']['start_date'],
            'end_date': primary_strategy['stats']['end_date'],
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'statistics': {
            'strategy': primary_strategy['stats'],
            # 添加其他策略统计
            'strategy_34_78': all_results['strategy_34_78']['stats'],
            'strategy_36_78': all_results['strategy_36_78']['stats'],
            'strategy_66_81': all_results['strategy_66_81']['stats'],
            'strategy_ideal': all_results[IDEAL_STRATEGY['name']]['stats'],
            'buyhold': buyhold_stats,
            'hs300_return': old_stats.get('hs300_return'),
            'hs300_annual': old_stats.get('hs300_annual'),
            'gold_return': old_stats.get('gold_return'),
            'gold_annual': old_stats.get('gold_annual'),
            'nasdaq_return': old_stats.get('nasdaq_return'),
            'nasdaq_annual': old_stats.get('nasdaq_annual'),
            'sp500_return': old_stats.get('sp500_return'),
            'sp500_annual': old_stats.get('sp500_annual'),
            'backtest_days': backtest_days,
        },
        'trades': ideal_trades,  # 使用理想化策略的交易记录（ETF联结基金）
        'trades_34_78': primary_trades,  # 保留原整手交易记录
        'daily_values': {
            'strategy': primary_strategy['daily_values'],
            'strategy_34_78': all_results['strategy_34_78']['daily_values'],
            'strategy_36_78': all_results['strategy_36_78']['daily_values'],
            'strategy_66_81': all_results['strategy_66_81']['daily_values'],
            'strategy_ideal': all_results[IDEAL_STRATEGY['name']]['daily_values'],
            'buyhold': buyhold_values,
            'hs300': benchmarks.get('hs300', []),
            'gold': benchmarks.get('gold', []),
            'nasdaq': benchmarks.get('nasdaq', []),
            'sp500': benchmarks.get('sp500', []),
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
    print("完成！包含以下策略曲线:")
    for name, result in all_results.items():
        print(f"  - {result['label']}: {result['stats']['total_return']:.2f}%")


if __name__ == "__main__":
    main()
