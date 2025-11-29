"""
RSI策略理想化参数优化测试
- 允许小数份额（全仓买入）
- 忽略100手整手限制
- 使用EMA平滑（更敏感）

目标: 找到理论最优参数，与实际整手交易对比
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
# ============ 配置参数 ============
INITIAL_CAPITAL = 100000

# 测试范围（更细粒度）
RSI_PERIODS = range(3, 25)          # RSI周期: 3-24日
BUY_THRESHOLDS = range(15, 51)      # 买入阈值: 15-50 (步长1)
SELL_THRESHOLDS = range(55, 91)     # 卖出阈值: 55-90 (步长1)


def calculate_rsi_ema(prices, period):
    """计算RSI指标（使用EMA平滑，更敏感）"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    # 使用EMA而非SMA（更敏感）
    alpha = 1 / period  # EMA平滑因子
    avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def run_backtest_ideal(df, rsi_period, buy_threshold, sell_threshold):
    """执行理想化RSI策略回测（允许小数份额）"""
    df = df.copy()
    df['rsi'] = calculate_rsi_ema(df['close'], rsi_period)
    
    cash = float(INITIAL_CAPITAL)
    shares = 0.0  # 允许小数
    position = 0
    trade_count = 0
    wins = 0
    buy_price = 0.0
    
    # 记录每日价值用于计算回撤
    daily_values = []
    
    for idx, row in df.iterrows():
        price = row['close']
        rsi = row['rsi']
        
        if pd.notna(rsi):
            if rsi < buy_threshold and position == 0:
                # 全仓买入（允许小数份额）
                shares = cash / price
                cash = 0.0
                position = 1
                buy_price = price
                    
            elif rsi > sell_threshold and position == 1:
                # 全仓卖出
                cash = shares * price
                shares = 0.0
                position = 0
                trade_count += 1
                if price > buy_price:
                    wins += 1
        
        current_value = cash + shares * price
        daily_values.append(current_value)
    
    # 计算最终收益
    final_value = cash + shares * df.iloc[-1]['close']
    total_return = (final_value / INITIAL_CAPITAL - 1) * 100
    
    # 计算最大回撤
    peak = INITIAL_CAPITAL
    max_drawdown = 0.0
    for value in daily_values:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak * 100
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
        'final_position': '持仓中' if position == 1 else '空仓',
        'final_value': round(final_value, 2)
    }


def main():
    print("=" * 70)
    print("RSI策略理想化参数优化测试")
    print("（小数份额 + EMA平滑 + 全仓交易）")
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
    
    # 加载整手交易的最优结果对比
    opt_path = os.path.join(script_dir, "rsi_optimization_results.json")
    if os.path.exists(opt_path):
        with open(opt_path, 'r', encoding='utf-8') as f:
            prev_results = json.load(f)
        prev_best = prev_results['best_params']
        print(f"\n整手交易最优: RSI({prev_best['rsi_period']}) {prev_best['buy_threshold']}/{prev_best['sell_threshold']}")
        print(f"  总收益: {prev_best['total_return']:.2f}%")
    else:
        prev_best = None
    
    # 生成所有参数组合
    combinations = []
    for rsi_period in RSI_PERIODS:
        for buy_th in BUY_THRESHOLDS:
            for sell_th in SELL_THRESHOLDS:
                if buy_th < sell_th - 10:  # 确保买卖阈值有足够间隔
                    combinations.append((rsi_period, buy_th, sell_th))
    
    total_combinations = len(combinations)
    print(f"\n测试参数组合数: {total_combinations}")
    print(f"RSI周期: {min(RSI_PERIODS)}-{max(RSI_PERIODS)}日")
    print(f"买入阈值: {min(BUY_THRESHOLDS)}-{max(BUY_THRESHOLDS)}")
    print(f"卖出阈值: {min(SELL_THRESHOLDS)}-{max(SELL_THRESHOLDS)}")
    
    print("\n正在测试（理想化模式）...")
    
    # 运行所有测试
    results = []
    for i, (rsi_period, buy_th, sell_th) in enumerate(combinations):
        if (i + 1) % 2000 == 0:
            print(f"  进度: {i+1}/{total_combinations} ({(i+1)/total_combinations*100:.1f}%)")
        
        result = run_backtest_ideal(df, rsi_period, buy_th, sell_th)
        results.append(result)
    
    print(f"  进度: {total_combinations}/{total_combinations} (100%)")
    
    # 按总收益排序
    results_sorted = sorted(results, key=lambda x: x['total_return'], reverse=True)
    
    # 筛选超过买入持有的策略
    beating_buyhold = [r for r in results_sorted if r['total_return'] > buyhold_return]
    
    print("\n" + "=" * 70)
    print("测试结果（理想化模式）")
    print("=" * 70)
    
    print(f"\n共 {len(beating_buyhold)} 个参数组合超过买入持有收益")
    print(f"占比: {len(beating_buyhold)/total_combinations*100:.1f}%")
    
    # 显示TOP 20
    print("\n" + "-" * 70)
    print("TOP 20 最优参数组合（理想化，按总收益排序）")
    print("-" * 70)
    print(f"{'排名':<4} {'RSI周期':<8} {'买入':<6} {'卖出':<6} {'总收益':>10} {'年化':>8} {'回撤':>8} {'交易':>6} {'胜率':>8}")
    print("-" * 70)
    
    for i, r in enumerate(results_sorted[:20], 1):
        annual = ((1 + r['total_return'] / 100) ** (365 / calendar_days) - 1) * 100
        print(f"{i:<4} {r['rsi_period']:<8} {r['buy_threshold']:<6} {r['sell_threshold']:<6} "
              f"{r['total_return']:>9.2f}% {annual:>7.2f}% {r['max_drawdown']:>7.2f}% "
              f"{r['trade_count']:>6} {r['win_rate']:>7.2f}%")
    
    # 最优参数详情
    best = results_sorted[0]
    best_annual = ((1 + best['total_return'] / 100) ** (365 / calendar_days) - 1) * 100
    
    print("\n" + "=" * 70)
    print("🏆 理想化最优参数")
    print("=" * 70)
    print(f"  RSI周期: {best['rsi_period']} 日 (EMA平滑)")
    print(f"  买入阈值: RSI < {best['buy_threshold']}")
    print(f"  卖出阈值: RSI > {best['sell_threshold']}")
    print(f"  总收益率: {best['total_return']:.2f}%")
    print(f"  年化收益: {best_annual:.2f}%")
    print(f"  最大回撤: {best['max_drawdown']:.2f}%")
    print(f"  交易次数: {best['trade_count']} 次")
    print(f"  胜率: {best['win_rate']:.2f}%")
    print(f"  当前状态: {best['final_position']}")
    print(f"  最终资产: ¥{best['final_value']:,.2f}")
    
    # 与买入持有对比
    excess_return = best['total_return'] - buyhold_return
    excess_annual = best_annual - buyhold_annual
    print(f"\n  vs 买入持有:")
    print(f"    超额收益: +{excess_return:.2f}%")
    print(f"    超额年化: +{excess_annual:.2f}%")
    
    # 与整手交易对比
    if prev_best:
        diff = best['total_return'] - prev_best['total_return']
        print(f"\n  vs 整手交易最优 RSI({prev_best['rsi_period']}) {prev_best['buy_threshold']}/{prev_best['sell_threshold']}:")
        print(f"    整手交易收益: {prev_best['total_return']:.2f}%")
        print(f"    理想化收益:   {best['total_return']:.2f}%")
        print(f"    差异: {'+' if diff > 0 else ''}{diff:.2f}%")
    
    # 按RSI周期分组统计
    print("\n" + "-" * 70)
    print("各RSI周期最优参数（理想化）")
    print("-" * 70)
    print(f"{'RSI':<6} {'买入':<6} {'卖出':<6} {'总收益':>10} {'年化':>8} {'交易':>6} {'胜率':>8}")
    print("-" * 70)
    
    for period in RSI_PERIODS:
        period_results = [r for r in results_sorted if r['rsi_period'] == period]
        if period_results:
            best_for_period = period_results[0]
            annual = ((1 + best_for_period['total_return'] / 100) ** (365 / calendar_days) - 1) * 100
            print(f"{period:<6} {best_for_period['buy_threshold']:<6} {best_for_period['sell_threshold']:<6} "
                  f"{best_for_period['total_return']:>9.2f}% {annual:>7.2f}% "
                  f"{best_for_period['trade_count']:>6} {best_for_period['win_rate']:>7.2f}%")
    
    # 风险调整后收益
    print("\n" + "-" * 70)
    print("TOP 10 风险调整后收益（收益/回撤比）")
    print("-" * 70)
    
    for r in results:
        r['sharpe_like'] = r['total_return'] / r['max_drawdown'] if r['max_drawdown'] > 0 else 0
    
    results_by_sharpe = sorted(results, key=lambda x: x['sharpe_like'], reverse=True)
    
    print(f"{'排名':<4} {'RSI':<6} {'买入':<6} {'卖出':<6} {'总收益':>10} {'回撤':>8} {'比值':>8}")
    print("-" * 70)
    
    for i, r in enumerate(results_by_sharpe[:10], 1):
        print(f"{i:<4} {r['rsi_period']:<6} {r['buy_threshold']:<6} {r['sell_threshold']:<6} "
              f"{r['total_return']:>9.2f}% {r['max_drawdown']:>7.2f}% {r['sharpe_like']:>7.2f}")
    
    # 热力图数据：固定RSI周期，看买卖阈值的影响
    print("\n" + "-" * 70)
    print(f"热力图：RSI({best['rsi_period']})周期下，不同买卖阈值的收益")
    print("-" * 70)
    
    best_period = best['rsi_period']
    period_results = [r for r in results if r['rsi_period'] == best_period]
    
    # 获取唯一的买入和卖出阈值
    buy_vals = sorted(set(r['buy_threshold'] for r in period_results))
    sell_vals = sorted(set(r['sell_threshold'] for r in period_results))
    
    # 只显示部分（每隔5）
    buy_display = [b for b in buy_vals if b % 5 == 0][:8]
    sell_display = [s for s in sell_vals if s % 5 == 0][:8]
    
    print(f"{'买\\卖':<6}", end='')
    for s in sell_display:
        print(f"{s:>8}", end='')
    print()
    
    for b in buy_display:
        print(f"{b:<6}", end='')
        for s in sell_display:
            match = [r for r in period_results if r['buy_threshold'] == b and r['sell_threshold'] == s]
            if match:
                ret = match[0]['total_return']
                print(f"{ret:>7.0f}%", end='')
            else:
                print(f"{'--':>8}", end='')
        print()
    
    # 保存结果
    output_file = os.path.join(script_dir, "rsi_optimization_ideal_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'meta': {
                'mode': '理想化（小数份额+EMA）',
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
            'best_annual': round(best_annual, 2),
            'top_20': results_sorted[:20],
            'top_by_period': {
                str(period): [r for r in results_sorted if r['rsi_period'] == period][0]
                for period in RSI_PERIODS
            },
            'comparison_with_lot_trading': {
                'lot_trading_best': prev_best if prev_best else None,
                'ideal_best': best,
                'difference': round(best['total_return'] - prev_best['total_return'], 2) if prev_best else None
            }
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n完整结果已保存至: {output_file}")
    
    # 总结
    print("\n" + "=" * 70)
    print("📊 理想化 vs 整手交易 对比总结")
    print("=" * 70)
    
    if prev_best:
        print(f"""
┌─────────────────────────────────────────────────────────────────┐
│                    整手交易（实际）    理想化（理论）            │
├─────────────────────────────────────────────────────────────────┤
│ RSI周期              {prev_best['rsi_period']:>8}日          {best['rsi_period']:>8}日              │
│ 买入阈值             RSI < {prev_best['buy_threshold']:<3}         RSI < {best['buy_threshold']:<3}             │
│ 卖出阈值             RSI > {prev_best['sell_threshold']:<3}         RSI > {best['sell_threshold']:<3}             │
│ 总收益率             {prev_best['total_return']:>8.2f}%         {best['total_return']:>8.2f}%            │
│ 年化收益             {((1 + prev_best['total_return'] / 100) ** (365 / calendar_days) - 1) * 100:>8.2f}%         {best_annual:>8.2f}%            │
│ 最大回撤             {prev_best['max_drawdown']:>8.2f}%         {best['max_drawdown']:>8.2f}%            │
│ 交易次数             {prev_best['trade_count']:>8}次          {best['trade_count']:>8}次              │
│ 胜率                 {prev_best['win_rate']:>8.2f}%         {best['win_rate']:>8.2f}%            │
└─────────────────────────────────────────────────────────────────┘

结论:
1. 理想化模式收益: {best['total_return']:.2f}% vs 整手交易: {prev_best['total_return']:.2f}%
2. 差异: {best['total_return'] - prev_best['total_return']:+.2f}%（{'理想化更优' if best['total_return'] > prev_best['total_return'] else '整手交易更优'}）
3. 整手限制对收益影响: {abs(best['total_return'] - prev_best['total_return']) / prev_best['total_return'] * 100:.1f}%
""")
    else:
        print(f"""
理想化最优参数:
- RSI({best['rsi_period']}) < {best['buy_threshold']} 买入, > {best['sell_threshold']} 卖出
- 总收益: {best['total_return']:.2f}% (年化 {best_annual:.2f}%)
- 最大回撤: {best['max_drawdown']:.2f}%
- 交易次数: {best['trade_count']}次, 胜率: {best['win_rate']:.2f}%
""")


if __name__ == "__main__":
    main()
