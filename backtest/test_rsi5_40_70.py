"""
测试 5日RSI 40/70 策略回测
RSI周期: 5日（更敏感）
买入阈值: RSI < 40
卖出阈值: RSI > 70
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

# ============ 配置参数 ============
RSI_PERIOD = 5  # 5日RSI
RSI_BUY = 40    # 买入阈值
RSI_SELL = 70   # 卖出阈值
INITIAL_CAPITAL = 100000


def calculate_rsi(prices, period=5):
    """计算RSI指标（使用EMA平滑）"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    # 初始平均值
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    # 使用指数移动平均（EMA）平滑
    for i in range(period, len(prices)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def run_backtest(df, rsi_period, buy_threshold, sell_threshold):
    """执行RSI策略回测"""
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], rsi_period)
    
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
                        'rsi': rsi
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
                            'rsi': rsi
                        })
        
        total_value = cash + shares * price
        daily_values.append({
            'date': date_str,
            'close': price,
            'rsi': rsi if pd.notna(rsi) else None,
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
    
    # 计算年化收益（使用自然日天数）
    trading_days = len(daily_values)
    total_return = returns[-1]
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
        'calendar_days': calendar_days
    }


def main():
    print("=" * 60)
    print(f"5日RSI {RSI_BUY}/{RSI_SELL} 策略回测")
    print("=" * 60)
    
    # 从现有JSON获取价格数据
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "backtest_result.json")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    strategy_values = data['daily_values']['strategy']
    
    df = pd.DataFrame([{
        'date': pd.to_datetime(d['date']),
        'close': d['close']
    } for d in strategy_values])
    
    df = df.sort_values('date').reset_index(drop=True)
    print(f"数据范围: {df['date'].min().strftime('%Y-%m-%d')} 至 {df['date'].max().strftime('%Y-%m-%d')}")
    print(f"共 {len(df)} 个交易日")
    
    # 运行回测
    print(f"\n执行 RSI({RSI_PERIOD}) {RSI_BUY}/{RSI_SELL} 策略...")
    trades, daily_values = run_backtest(df, RSI_PERIOD, RSI_BUY, RSI_SELL)
    stats = calculate_statistics(daily_values, trades)
    
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"  总收益率: {stats['total_return']:.2f}%")
    print(f"  年化收益: {stats['annual_return']:.2f}%")
    print(f"  最大回撤: {stats['max_drawdown']:.2f}%")
    print(f"  交易次数: {stats['trade_count']} 次")
    print(f"  胜率: {stats['win_rate']:.2f}%")
    
    # 显示交易记录
    print("\n" + "-" * 60)
    print("交易记录:")
    print("-" * 60)
    for t in trades:
        action_emoji = "🟢" if t['action'] == '买入' else "🔴"
        print(f"  {action_emoji} {t['date']} {t['action']} | 价格: ¥{t['price']:.3f} | RSI: {t['rsi']:.1f} | 金额: ¥{t['amount']:.0f}")
    
    # 与其他策略对比
    print("\n" + "=" * 60)
    print("策略对比")
    print("=" * 60)
    
    old_stats = data['statistics']
    
    comparisons = [
        (f"RSI(5) {RSI_BUY}/{RSI_SELL}", stats['total_return'], stats['annual_return'], stats['trade_count'], stats['max_drawdown'], stats['win_rate']),
        ("RSI(14) 34/78", old_stats['strategy_34_78']['total_return'], old_stats['strategy_34_78']['annual_return'], old_stats['strategy_34_78']['trade_count'], old_stats['strategy_34_78']['max_drawdown'], old_stats['strategy_34_78']['win_rate']),
        ("RSI(14) 66/81", old_stats['strategy_66_81']['total_return'], old_stats['strategy_66_81']['annual_return'], old_stats['strategy_66_81']['trade_count'], old_stats['strategy_66_81']['max_drawdown'], old_stats['strategy_66_81']['win_rate']),
        ("买入持有", old_stats['buyhold']['total_return'], old_stats['buyhold']['annual_return'], 0, old_stats['buyhold']['max_drawdown'], 0),
    ]
    
    print(f"{'策略':<20} {'总收益':>10} {'年化':>8} {'交易次数':>8} {'最大回撤':>10} {'胜率':>8}")
    print("-" * 70)
    for name, ret, ann, cnt, dd, wr in comparisons:
        print(f"{name:<20} {ret:>9.2f}% {ann:>7.2f}% {cnt:>8} {dd:>9.2f}% {wr:>7.2f}%")


if __name__ == "__main__":
    main()
