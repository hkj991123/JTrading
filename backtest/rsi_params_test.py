"""
RSI策略参数优化测试
测试不同买入/卖出阈值组合的效果

注意：512890是累积型ETF，分红已体现在价格中，无需处理分红
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

# ============ 配置参数 ============
ETF_CODE = "512890"
RSI_PERIOD = 14
INITIAL_CAPITAL = 100000

# 测试的阈值组合 - 全面搜索
THRESHOLD_COMBINATIONS = []

# 生成参数组合：买入阈值30-75，卖出阈值60-95
for buy in range(30, 76, 2):  # 30, 32, 34, ..., 74
    for sell in range(max(buy + 5, 60), 96, 2):  # 卖出阈值必须大于买入阈值+5
        THRESHOLD_COMBINATIONS.append((buy, sell))


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


def get_etf_data_from_json():
    """从本地JSON文件获取ETF日线数据"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "backtest_result.json")
    
    print(f"从本地文件加载数据: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 从strategy的daily_values提取数据
    daily_values = data['daily_values']['strategy']
    
    df = pd.DataFrame([{
        'date': pd.to_datetime(d['date']),
        'close': d['close']
    } for d in daily_values])
    
    df = df.sort_values('date').reset_index(drop=True)
    print(f"获取到 {len(df)} 条数据")
    return df


def run_backtest(df, buy_threshold, sell_threshold, initial_capital=INITIAL_CAPITAL):
    """执行RSI策略回测（累积型ETF，分红已体现在价格中）"""
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
    
    cash = initial_capital
    shares = 0
    position = 0
    trades = []
    
    # 计算最大回撤
    peak_value = initial_capital
    max_drawdown = 0
    
    for i, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        rsi = row['rsi']
        
        if pd.notna(rsi):
            if rsi < buy_threshold and position == 0:
                shares_to_buy = int(cash / price / 100) * 100
                if shares_to_buy > 0:
                    cash -= shares_to_buy * price
                    shares += shares_to_buy
                    position = 1
                    trades.append({
                        'date': date_str, 
                        'action': '买入', 
                        'price': price,
                        'rsi': round(rsi, 2)
                    })
                    
            elif rsi > sell_threshold and position == 1:
                if shares > 0:
                    sell_shares = int(shares / 100) * 100
                    cash += sell_shares * price
                    shares -= sell_shares
                    if shares < 100:
                        cash += shares * price
                        shares = 0
                    position = 0
                    trades.append({
                        'date': date_str, 
                        'action': '卖出', 
                        'price': price,
                        'rsi': round(rsi, 2)
                    })
        
        # 更新最大回撤
        current_value = cash + shares * price
        if current_value > peak_value:
            peak_value = current_value
        drawdown = (peak_value - current_value) / peak_value * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    final_value = cash + shares * df.iloc[-1]['close']
    total_return = (final_value / initial_capital - 1) * 100
    
    # 计算胜率
    buy_trades = [t for t in trades if t['action'] == '买入']
    sell_trades = [t for t in trades if t['action'] == '卖出']
    wins = 0
    for i, sell in enumerate(sell_trades):
        if i < len(buy_trades) and sell['price'] > buy_trades[i]['price']:
            wins += 1
    win_rate = (wins / len(sell_trades) * 100) if sell_trades else 0
    
    return {
        'buy_threshold': buy_threshold,
        'sell_threshold': sell_threshold,
        'final_value': round(final_value, 2),
        'total_return': round(total_return, 2),
        'max_drawdown': round(max_drawdown, 2),
        'trade_count': len(buy_trades),
        'win_rate': round(win_rate, 2),
        'final_position': '持仓' if position == 1 else '空仓',
        'trades': trades
    }


def calculate_buy_hold(df, initial_capital=INITIAL_CAPITAL):
    """计算买入持有收益（累积型ETF，分红已体现在价格中）"""
    start_price = df.iloc[0]['close']
    shares = int(initial_capital / start_price / 100) * 100
    cash = initial_capital - shares * start_price
    
    peak_value = initial_capital
    max_drawdown = 0
    
    for _, row in df.iterrows():
        price = row['close']
        
        current_value = cash + shares * price
        if current_value > peak_value:
            peak_value = current_value
        drawdown = (peak_value - current_value) / peak_value * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    final_value = cash + shares * df.iloc[-1]['close']
    return {
        'total_return': round((final_value / initial_capital - 1) * 100, 2),
        'max_drawdown': round(max_drawdown, 2)
    }


def main():
    print("=" * 80)
    print("红利低波ETF (512890) RSI策略参数优化测试")
    print("注意：512890是累积型ETF，分红已体现在前复权价格中，无需单独处理")
    print("=" * 80)
    
    # 获取数据
    df = get_etf_data_from_json()
    
    start_date = df['date'].min()
    end_date = df['date'].max()
    
    print(f"\n回测区间: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    days = len(df)
    def calc_annual(total_ret):
        return round(((1 + total_ret / 100) ** (365 / days) - 1) * 100, 2)
    
    # 买入持有基准
    bh = calculate_buy_hold(df)
    bh_annual = calc_annual(bh['total_return'])
    
    # 测试各阈值组合
    results = []
    total_combinations = len(THRESHOLD_COMBINATIONS)
    for idx, (buy_th, sell_th) in enumerate(THRESHOLD_COMBINATIONS):
        if idx % 50 == 0:
            print(f"测试进度: {idx}/{total_combinations} ({idx*100/total_combinations:.1f}%)")
        result = run_backtest(df, buy_th, sell_th)
        result['annual_return'] = calc_annual(result['total_return'])
        results.append(result)
    
    # 输出结果
    print("\n" + "=" * 90)
    print("参数优化结果对比")
    print("=" * 90)
    
    print(f"\n{'阈值(买/卖)':<12} {'总收益率':<12} {'年化收益':<12} {'最大回撤':<12} {'交易次数':<8} {'胜率':<10} {'状态':<6} {'vs买入持有':<12}")
    print("-" * 90)
    
    # 基准
    print(f"{'买入持有':<11} {bh['total_return']:>8.2f}% {bh_annual:>10.2f}% {bh['max_drawdown']:>10.2f}% {'-':>8} {'-':>10} {'持仓':>6} {'-':>12}")
    print("-" * 90)
    
    # 按收益率排序
    results_sorted = sorted(results, key=lambda x: x['total_return'], reverse=True)
    
    # 各策略结果
    for r in results_sorted:
        label = f"{r['buy_threshold']}/{r['sell_threshold']}"
        is_current = "*" if r['buy_threshold'] == 40 and r['sell_threshold'] == 70 else ""
        vs_bh = r['total_return'] - bh['total_return']
        vs_bh_str = f"{vs_bh:+.2f}%" if vs_bh != 0 else "-"
        beat_marker = "[WIN]" if vs_bh > 0 else ""
        print(f"{label:<6}{is_current:<5} {r['total_return']:>8.2f}% {r['annual_return']:>10.2f}% {r['max_drawdown']:>10.2f}% {r['trade_count']:>8} {r['win_rate']:>8.2f}% {r['final_position']:>6} {vs_bh_str:>10} {beat_marker}")
    
    # 找出最优和超越买入持有的策略
    best = max(results, key=lambda x: x['total_return'])
    worst = min(results, key=lambda x: x['total_return'])
    beat_bh = [r for r in results if r['total_return'] > bh['total_return']]
    
    print("\n" + "=" * 90)
    print("分析总结")
    print("=" * 90)
    
    print(f"""
【最优参数】
  买入阈值: RSI < {best['buy_threshold']}
  卖出阈值: RSI > {best['sell_threshold']}
  总收益率: {best['total_return']:.2f}% (年化 {best['annual_return']:.2f}%)
  最大回撤: {best['max_drawdown']:.2f}%
  交易次数: {best['trade_count']} 次
  胜率: {best['win_rate']:.2f}%
  vs 买入持有: {best['total_return'] - bh['total_return']:+.2f}%

【超越买入持有的策略数量】: {len(beat_bh)} 个
""")
    
    if beat_bh:
        print("【超越买入持有的策略列表】")
        beat_bh_sorted = sorted(beat_bh, key=lambda x: x['total_return'], reverse=True)
        for r in beat_bh_sorted:
            print(f"  {r['buy_threshold']}/{r['sell_threshold']}: {r['total_return']:.2f}% (超额 {r['total_return'] - bh['total_return']:+.2f}%)")
    else:
        print("【没有策略能超越买入持有】")
        print(f"  最接近的策略: {best['buy_threshold']}/{best['sell_threshold']} = {best['total_return']:.2f}%")
        print(f"  差距: {best['total_return'] - bh['total_return']:.2f}%")
    
    print(f"""
【当前策略 (40/70)】
  总收益率: {results[0]['total_return']:.2f}% (年化 {results[0]['annual_return']:.2f}%)
  vs 买入持有: {results[0]['total_return'] - bh['total_return']:+.2f}%
  
【买入持有基准】
  总收益率: {bh['total_return']:.2f}% (年化 {bh_annual:.2f}%)
  最大回撤: {bh['max_drawdown']:.2f}%
""")

    # 只显示超越买入持有的策略交易记录
    print("\n" + "=" * 90)
    if beat_bh:
        print("超越买入持有的策略交易记录（前3名）")
        print("=" * 90)
        
        for r in beat_bh_sorted[:3]:
            label = f"{r['buy_threshold']}/{r['sell_threshold']}"
            print(f"\n【{label}】收益 {r['total_return']:.2f}%, 共 {r['trade_count']} 次买入")
            for t in r['trades']:
                print(f"  {t['date']} {t['action']} @ {t['price']:.3f} (RSI={t['rsi']})")
    else:
        print("最优策略交易记录")
        print("=" * 90)
        print(f"\n【{best['buy_threshold']}/{best['sell_threshold']}】收益 {best['total_return']:.2f}%, 共 {best['trade_count']} 次买入")
        for t in best['trades']:
            print(f"  {t['date']} {t['action']} @ {t['price']:.3f} (RSI={t['rsi']})")


if __name__ == "__main__":
    main()
