"""
RSI策略参数全面优化测试
基于红利低波ETF (512890) 全收益数据

测试变量:
1. RSI周期: 3-20日
2. RSI买入阈值: 20-50
3. RSI卖出阈值: 60-90

目标: 找到能获得最高收益的最优参数组合
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import itertools

# ============ 配置参数 ============
INITIAL_CAPITAL = 100000

# 测试范围
RSI_PERIODS = range(3, 21)          # RSI周期: 3-20日
BUY_THRESHOLDS = range(20, 51, 2)   # 买入阈值: 20-50 (步长2)
SELL_THRESHOLDS = range(60, 91, 2)  # 卖出阈值: 60-90 (步长2)


def calculate_rsi(prices, period):
    """计算RSI指标"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).copy()
    loss = (-delta).where(delta < 0, 0).copy()
    
    # 使用numpy数组来避免pandas链式赋值问题
    avg_gain_arr = gain.rolling(window=period, min_periods=period).mean().to_numpy()
    avg_loss_arr = loss.rolling(window=period, min_periods=period).mean().to_numpy()
    gain_arr = gain.to_numpy()
    loss_arr = loss.to_numpy()
    
    # EMA平滑
    for i in range(period, len(prices)):
        if not np.isnan(avg_gain_arr[i-1]):
            avg_gain_arr[i] = (avg_gain_arr[i-1] * (period - 1) + gain_arr[i]) / period
            avg_loss_arr[i] = (avg_loss_arr[i-1] * (period - 1) + loss_arr[i]) / period
    
    # 避免除零
    with np.errstate(divide='ignore', invalid='ignore'):
        rs = avg_gain_arr / avg_loss_arr
        rsi = 100 - (100 / (1 + rs))
    
    return pd.Series(rsi, index=prices.index)


def run_backtest(df, rsi_period, buy_threshold, sell_threshold):
    """执行RSI策略回测"""
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], rsi_period)
    
    cash = INITIAL_CAPITAL
    shares = 0
    position = 0
    trade_count = 0
    wins = 0
    buy_price = 0
    
    for i, row in df.iterrows():
        price = row['close']
        rsi = row['rsi']
        
        if pd.notna(rsi):
            if rsi < buy_threshold and position == 0:
                shares_to_buy = int(cash / price / 100) * 100
                if shares_to_buy > 0:
                    cost = shares_to_buy * price
                    cash -= cost
                    shares += shares_to_buy
                    position = 1
                    buy_price = price
                    
            elif rsi > sell_threshold and position == 1:
                if shares > 0:
                    sell_shares = int(shares / 100) * 100
                    if sell_shares > 0:
                        revenue = sell_shares * price
                        cash += revenue
                        if shares - sell_shares < 100:
                            cash += (shares - sell_shares) * price
                            shares = 0
                        else:
                            shares -= sell_shares
                        position = 0
                        trade_count += 1
                        if price > buy_price:
                            wins += 1
    
    # 计算最终收益
    final_value = cash + shares * df.iloc[-1]['close']
    total_return = (final_value / INITIAL_CAPITAL - 1) * 100
    
    # 计算最大回撤
    peak = INITIAL_CAPITAL
    max_drawdown = 0
    running_cash = INITIAL_CAPITAL
    running_shares = 0
    running_position = 0
    
    for i, row in df.iterrows():
        price = row['close']
        rsi = row['rsi']
        
        if pd.notna(rsi):
            if rsi < buy_threshold and running_position == 0:
                shares_to_buy = int(running_cash / price / 100) * 100
                if shares_to_buy > 0:
                    cost = shares_to_buy * price
                    running_cash -= cost
                    running_shares += shares_to_buy
                    running_position = 1
                    
            elif rsi > sell_threshold and running_position == 1:
                if running_shares > 0:
                    sell_shares = int(running_shares / 100) * 100
                    if sell_shares > 0:
                        revenue = sell_shares * price
                        running_cash += revenue
                        if running_shares - sell_shares < 100:
                            running_cash += (running_shares - sell_shares) * price
                            running_shares = 0
                        else:
                            running_shares -= sell_shares
                        running_position = 0
        
        current_value = running_cash + running_shares * price
        if current_value > peak:
            peak = current_value
        drawdown = (peak - current_value) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    win_rate = (wins / trade_count * 100) if trade_count > 0 else 0
    
    return {
        'rsi_period': rsi_period,
        'buy_threshold': buy_threshold,
        'sell_threshold': sell_threshold,
        'total_return': round(total_return, 2),
        'max_drawdown': round(max_drawdown, 2),
        'trade_count': trade_count,
        'win_rate': round(win_rate, 2),
        'final_position': '持仓中' if position == 1 else '空仓'
    }


def test_single_combination(args):
    """测试单个参数组合"""
    df, rsi_period, buy_threshold, sell_threshold = args
    # 确保买入阈值 < 卖出阈值
    if buy_threshold >= sell_threshold:
        return None
    return run_backtest(df, rsi_period, buy_threshold, sell_threshold)


def main():
    print("=" * 70)
    print("RSI策略参数全面优化测试")
    print("=" * 70)
    
    # 获取数据
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
    
    start_date = df['date'].min().strftime('%Y-%m-%d')
    end_date = df['date'].max().strftime('%Y-%m-%d')
    calendar_days = (df['date'].max() - df['date'].min()).days
    
    print(f"数据范围: {start_date} 至 {end_date}")
    print(f"共 {len(df)} 个交易日, {calendar_days} 个自然日")
    
    # 计算买入持有收益作为基准
    buyhold_return = (df.iloc[-1]['close'] / df.iloc[0]['close'] - 1) * 100
    buyhold_annual = ((1 + buyhold_return / 100) ** (365 / calendar_days) - 1) * 100
    print(f"\n基准 - 买入持有: 总收益 {buyhold_return:.2f}%, 年化 {buyhold_annual:.2f}%")
    
    # 生成所有参数组合
    combinations = []
    for rsi_period in RSI_PERIODS:
        for buy_th in BUY_THRESHOLDS:
            for sell_th in SELL_THRESHOLDS:
                if buy_th < sell_th:  # 确保买入阈值 < 卖出阈值
                    combinations.append((rsi_period, buy_th, sell_th))
    
    total_combinations = len(combinations)
    print(f"\n测试参数组合数: {total_combinations}")
    print(f"RSI周期: {min(RSI_PERIODS)}-{max(RSI_PERIODS)}日")
    print(f"买入阈值: {min(BUY_THRESHOLDS)}-{max(BUY_THRESHOLDS)}")
    print(f"卖出阈值: {min(SELL_THRESHOLDS)}-{max(SELL_THRESHOLDS)}")
    
    print("\n正在测试...")
    
    # 运行所有测试
    results = []
    for i, (rsi_period, buy_th, sell_th) in enumerate(combinations):
        if (i + 1) % 500 == 0:
            print(f"  进度: {i+1}/{total_combinations} ({(i+1)/total_combinations*100:.1f}%)")
        
        result = run_backtest(df, rsi_period, buy_th, sell_th)
        results.append(result)
    
    print(f"  进度: {total_combinations}/{total_combinations} (100%)")
    
    # 按总收益排序
    results_sorted = sorted(results, key=lambda x: x['total_return'], reverse=True)
    
    # 筛选超过买入持有的策略
    beating_buyhold = [r for r in results_sorted if r['total_return'] > buyhold_return]
    
    print("\n" + "=" * 70)
    print("测试结果")
    print("=" * 70)
    
    print(f"\n共 {len(beating_buyhold)} 个参数组合超过买入持有收益")
    print(f"占比: {len(beating_buyhold)/total_combinations*100:.1f}%")
    
    # 显示TOP 20
    print("\n" + "-" * 70)
    print("TOP 20 最优参数组合 (按总收益排序)")
    print("-" * 70)
    print(f"{'排名':<4} {'RSI周期':<8} {'买入':<6} {'卖出':<6} {'总收益':>10} {'最大回撤':>10} {'交易次数':>8} {'胜率':>8} {'状态':<8}")
    print("-" * 70)
    
    for i, r in enumerate(results_sorted[:20], 1):
        annual = ((1 + r['total_return'] / 100) ** (365 / calendar_days) - 1) * 100
        print(f"{i:<4} {r['rsi_period']:<8} {r['buy_threshold']:<6} {r['sell_threshold']:<6} "
              f"{r['total_return']:>9.2f}% {r['max_drawdown']:>9.2f}% {r['trade_count']:>8} "
              f"{r['win_rate']:>7.2f}% {r['final_position']:<8}")
    
    # 最优参数详情
    best = results_sorted[0]
    best_annual = ((1 + best['total_return'] / 100) ** (365 / calendar_days) - 1) * 100
    
    print("\n" + "=" * 70)
    print("🏆 最优参数")
    print("=" * 70)
    print(f"  RSI周期: {best['rsi_period']} 日")
    print(f"  买入阈值: RSI < {best['buy_threshold']}")
    print(f"  卖出阈值: RSI > {best['sell_threshold']}")
    print(f"  总收益率: {best['total_return']:.2f}%")
    print(f"  年化收益: {best_annual:.2f}%")
    print(f"  最大回撤: {best['max_drawdown']:.2f}%")
    print(f"  交易次数: {best['trade_count']} 次")
    print(f"  胜率: {best['win_rate']:.2f}%")
    print(f"  当前状态: {best['final_position']}")
    
    # 超额收益
    excess_return = best['total_return'] - buyhold_return
    excess_annual = best_annual - buyhold_annual
    print(f"\n  vs 买入持有:")
    print(f"    超额收益: +{excess_return:.2f}%")
    print(f"    超额年化: +{excess_annual:.2f}%")
    
    # 按RSI周期分组统计最优参数
    print("\n" + "-" * 70)
    print("各RSI周期最优参数")
    print("-" * 70)
    print(f"{'RSI周期':<8} {'最优买入':<8} {'最优卖出':<8} {'总收益':>10} {'交易次数':>8} {'胜率':>8}")
    print("-" * 70)
    
    for period in RSI_PERIODS:
        period_results = [r for r in results_sorted if r['rsi_period'] == period]
        if period_results:
            best_for_period = period_results[0]
            print(f"{period:<8} {best_for_period['buy_threshold']:<8} {best_for_period['sell_threshold']:<8} "
                  f"{best_for_period['total_return']:>9.2f}% {best_for_period['trade_count']:>8} "
                  f"{best_for_period['win_rate']:>7.2f}%")
    
    # 风险调整后收益（收益/回撤比）
    print("\n" + "-" * 70)
    print("TOP 10 风险调整后收益 (收益/回撤比)")
    print("-" * 70)
    
    # 计算收益回撤比
    for r in results:
        r['return_drawdown_ratio'] = r['total_return'] / r['max_drawdown'] if r['max_drawdown'] > 0 else 0
    
    results_by_ratio = sorted(results, key=lambda x: x['return_drawdown_ratio'], reverse=True)
    
    print(f"{'排名':<4} {'RSI周期':<8} {'买入':<6} {'卖出':<6} {'总收益':>10} {'最大回撤':>10} {'收益/回撤':>10}")
    print("-" * 70)
    
    for i, r in enumerate(results_by_ratio[:10], 1):
        print(f"{i:<4} {r['rsi_period']:<8} {r['buy_threshold']:<6} {r['sell_threshold']:<6} "
              f"{r['total_return']:>9.2f}% {r['max_drawdown']:>9.2f}% {r['return_drawdown_ratio']:>9.2f}")
    
    # 保存完整结果
    output_file = os.path.join(script_dir, "rsi_optimization_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'meta': {
                'start_date': start_date,
                'end_date': end_date,
                'trading_days': len(df),
                'calendar_days': calendar_days,
                'buyhold_return': round(buyhold_return, 2),
                'buyhold_annual': round(buyhold_annual, 2),
                'total_combinations': total_combinations,
                'beating_buyhold_count': len(beating_buyhold),
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            'best_params': best,
            'top_20': results_sorted[:20],
            'top_by_period': {
                period: [r for r in results_sorted if r['rsi_period'] == period][0]
                for period in RSI_PERIODS
            }
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n完整结果已保存至: {output_file}")
    
    # 总结建议
    print("\n" + "=" * 70)
    print("📊 优化建议总结")
    print("=" * 70)
    print(f"""
1. 最优参数: RSI({best['rsi_period']}) < {best['buy_threshold']} 买入, > {best['sell_threshold']} 卖出
   - 总收益: {best['total_return']:.2f}% (年化 {best_annual:.2f}%)
   - 超过买入持有: +{excess_return:.2f}%

2. 参数特点:
   - RSI周期较长({best['rsi_period']}日)更适合低波动ETF
   - 买入阈值较低({best['buy_threshold']})确保在真正超卖时入场
   - 卖出阈值较高({best['sell_threshold']})避免过早卖出

3. 交易频率:
   - {best['trade_count']}次交易，{len(df)/best['trade_count']:.0f}天/次
   - 低频交易更适合红利低波ETF

4. 风险控制:
   - 最大回撤: {best['max_drawdown']:.2f}%
   - 胜率: {best['win_rate']:.2f}%
""")


if __name__ == "__main__":
    main()
