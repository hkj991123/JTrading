"""
分红处理方式对比测试
1. 分红立即再投资（当前策略）
2. 分红累积到现金，等RSI信号再投
3. 分红不投资，单独记录
"""

import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime

# ============ 配置参数 ============
ETF_CODE = "512890"
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 40
RSI_SELL_THRESHOLD = 70
INITIAL_CAPITAL = 100000


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


def get_etf_data(code):
    """获取ETF日线数据"""
    print(f"正在获取 {code} 历史数据...")
    df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="qfq")
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.rename(columns={'日期': 'date', '收盘': 'close'})
    df = df.sort_values('date').reset_index(drop=True)
    print(f"获取到 {len(df)} 条数据")
    return df


def get_dividend_data():
    """获取分红数据"""
    dividend_data = [
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
    df = pd.DataFrame(dividend_data)
    df['date'] = pd.to_datetime(df['date'])
    return df


def run_backtest_reinvest_immediate(df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """
    策略1: 分红立即再投资（当前策略）
    收到分红当天按收盘价买入
    """
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
    
    cash = initial_capital
    shares = 0
    position = 0
    trades = []
    dividend_total = 0
    
    dividend_dict = {row['date'].strftime('%Y-%m-%d'): row['dividend'] 
                     for _, row in dividend_df.iterrows()}
    
    for i, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        rsi = row['rsi']
        
        # 处理分红：立即再投资
        if date_str in dividend_dict and shares > 0:
            dividend_amount = shares * dividend_dict[date_str]
            dividend_total += dividend_amount
            new_shares = dividend_amount / price
            shares += new_shares
        
        if pd.notna(rsi):
            if rsi < RSI_BUY_THRESHOLD and position == 0:
                shares_to_buy = int(cash / price / 100) * 100
                if shares_to_buy > 0:
                    cash -= shares_to_buy * price
                    shares += shares_to_buy
                    position = 1
                    trades.append({'date': date_str, 'action': '买入', 'rsi': round(rsi, 2)})
                    
            elif rsi > RSI_SELL_THRESHOLD and position == 1:
                if shares > 0:
                    sell_shares = int(shares / 100) * 100
                    cash += sell_shares * price
                    shares -= sell_shares
                    if shares < 100:
                        cash += shares * price
                        shares = 0
                    position = 0
                    trades.append({'date': date_str, 'action': '卖出', 'rsi': round(rsi, 2)})
    
    final_value = cash + shares * df.iloc[-1]['close']
    return {
        'name': '分红立即再投资',
        'final_value': final_value,
        'total_return': round((final_value / initial_capital - 1) * 100, 2),
        'dividend_total': round(dividend_total, 2),
        'trade_count': len([t for t in trades if t['action'] == '买入']),
        'final_position': '持仓' if position == 1 else '空仓'
    }


def run_backtest_reinvest_on_signal(df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """
    策略2: 分红累积到现金，等RSI买入信号时一起投入
    """
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
    
    cash = initial_capital
    shares = 0
    position = 0
    trades = []
    dividend_total = 0
    
    dividend_dict = {row['date'].strftime('%Y-%m-%d'): row['dividend'] 
                     for _, row in dividend_df.iterrows()}
    
    for i, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        rsi = row['rsi']
        
        # 处理分红：累积到现金
        if date_str in dividend_dict and shares > 0:
            dividend_amount = shares * dividend_dict[date_str]
            dividend_total += dividend_amount
            cash += dividend_amount  # 分红加到现金
        
        if pd.notna(rsi):
            if rsi < RSI_BUY_THRESHOLD and position == 0:
                # 用全部现金（含累积分红）买入
                shares_to_buy = int(cash / price / 100) * 100
                if shares_to_buy > 0:
                    cash -= shares_to_buy * price
                    shares += shares_to_buy
                    position = 1
                    trades.append({'date': date_str, 'action': '买入', 'rsi': round(rsi, 2)})
                    
            elif rsi > RSI_SELL_THRESHOLD and position == 1:
                if shares > 0:
                    sell_shares = int(shares / 100) * 100
                    cash += sell_shares * price
                    shares -= sell_shares
                    if shares < 100:
                        cash += shares * price
                        shares = 0
                    position = 0
                    trades.append({'date': date_str, 'action': '卖出', 'rsi': round(rsi, 2)})
    
    final_value = cash + shares * df.iloc[-1]['close']
    return {
        'name': '分红等信号再投',
        'final_value': final_value,
        'total_return': round((final_value / initial_capital - 1) * 100, 2),
        'dividend_total': round(dividend_total, 2),
        'trade_count': len([t for t in trades if t['action'] == '买入']),
        'final_position': '持仓' if position == 1 else '空仓'
    }


def run_backtest_no_reinvest(df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """
    策略3: 分红不投资，单独记录（只计算价格收益）
    """
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
    
    cash = initial_capital
    shares = 0
    position = 0
    trades = []
    dividend_total = 0
    dividend_cash = 0  # 分红单独存放，不参与交易
    
    dividend_dict = {row['date'].strftime('%Y-%m-%d'): row['dividend'] 
                     for _, row in dividend_df.iterrows()}
    
    for i, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        rsi = row['rsi']
        
        # 处理分红：单独记录，不投资
        if date_str in dividend_dict and shares > 0:
            dividend_amount = shares * dividend_dict[date_str]
            dividend_total += dividend_amount
            dividend_cash += dividend_amount  # 分红单独存放
        
        if pd.notna(rsi):
            if rsi < RSI_BUY_THRESHOLD and position == 0:
                # 只用交易资金买入，不含分红
                shares_to_buy = int(cash / price / 100) * 100
                if shares_to_buy > 0:
                    cash -= shares_to_buy * price
                    shares += shares_to_buy
                    position = 1
                    trades.append({'date': date_str, 'action': '买入', 'rsi': round(rsi, 2)})
                    
            elif rsi > RSI_SELL_THRESHOLD and position == 1:
                if shares > 0:
                    sell_shares = int(shares / 100) * 100
                    cash += sell_shares * price
                    shares -= sell_shares
                    if shares < 100:
                        cash += shares * price
                        shares = 0
                    position = 0
                    trades.append({'date': date_str, 'action': '卖出', 'rsi': round(rsi, 2)})
    
    # 最终价值 = 交易账户 + 分红账户
    trading_value = cash + shares * df.iloc[-1]['close']
    final_value = trading_value + dividend_cash
    
    return {
        'name': '分红不投资',
        'final_value': final_value,
        'total_return': round((final_value / initial_capital - 1) * 100, 2),
        'dividend_total': round(dividend_total, 2),
        'dividend_cash': round(dividend_cash, 2),
        'trading_value': round(trading_value, 2),
        'trade_count': len([t for t in trades if t['action'] == '买入']),
        'final_position': '持仓' if position == 1 else '空仓'
    }


def calculate_buy_hold_reinvest(df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """买入持有 - 分红再投资"""
    start_price = df.iloc[0]['close']
    shares = int(initial_capital / start_price / 100) * 100
    cash = initial_capital - shares * start_price
    dividend_total = 0
    
    dividend_dict = {row['date'].strftime('%Y-%m-%d'): row['dividend'] 
                     for _, row in dividend_df.iterrows()}
    
    for _, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        if date_str in dividend_dict and shares > 0:
            dividend_amount = shares * dividend_dict[date_str]
            dividend_total += dividend_amount
            new_shares = dividend_amount / price
            shares += new_shares
    
    final_value = cash + shares * df.iloc[-1]['close']
    return {
        'name': '买入持有(分红再投)',
        'final_value': final_value,
        'total_return': round((final_value / initial_capital - 1) * 100, 2),
        'dividend_total': round(dividend_total, 2)
    }


def calculate_buy_hold_no_reinvest(df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """买入持有 - 分红不投资"""
    start_price = df.iloc[0]['close']
    shares = int(initial_capital / start_price / 100) * 100
    cash = initial_capital - shares * start_price
    dividend_cash = 0
    
    dividend_dict = {row['date'].strftime('%Y-%m-%d'): row['dividend'] 
                     for _, row in dividend_df.iterrows()}
    
    for _, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        if date_str in dividend_dict and shares > 0:
            dividend_cash += shares * dividend_dict[date_str]
    
    trading_value = cash + shares * df.iloc[-1]['close']
    final_value = trading_value + dividend_cash
    
    return {
        'name': '买入持有(分红不投)',
        'final_value': final_value,
        'total_return': round((final_value / initial_capital - 1) * 100, 2),
        'dividend_cash': round(dividend_cash, 2)
    }


def main():
    print("=" * 70)
    print("红利低波ETF (512890) RSI策略 - 分红处理方式对比")
    print("=" * 70)
    
    # 获取数据
    df = get_etf_data(ETF_CODE)
    dividend_df = get_dividend_data()
    
    # 筛选时间范围
    start_date = df['date'].min()
    end_date = df['date'].max()
    dividend_df = dividend_df[(dividend_df['date'] >= start_date) & (dividend_df['date'] <= end_date)]
    
    print(f"\n回测区间: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    print(f"区间内分红次数: {len(dividend_df)} 次")
    
    # 执行各策略
    results = []
    
    # RSI策略 - 三种分红处理
    results.append(run_backtest_reinvest_immediate(df, dividend_df))
    results.append(run_backtest_reinvest_on_signal(df, dividend_df))
    results.append(run_backtest_no_reinvest(df, dividend_df))
    
    # 买入持有对比
    bh_reinvest = calculate_buy_hold_reinvest(df, dividend_df)
    bh_no_reinvest = calculate_buy_hold_no_reinvest(df, dividend_df)
    
    # 计算年化
    days = len(df)
    def calc_annual(total_ret):
        return round(((1 + total_ret / 100) ** (365 / days) - 1) * 100, 2)
    
    # 输出结果
    print("\n" + "=" * 70)
    print("RSI策略 - 分红处理方式对比")
    print("=" * 70)
    print(f"\n{'策略':<20} {'总收益率':<12} {'年化收益':<12} {'累计分红':<12} {'交易次数':<10}")
    print("-" * 70)
    
    for r in results:
        annual = calc_annual(r['total_return'])
        print(f"{r['name']:<18} {r['total_return']:>8.2f}% {annual:>10.2f}% {r['dividend_total']:>10.2f} {r['trade_count']:>10}")
    
    print("\n" + "=" * 70)
    print("买入持有策略对比")
    print("=" * 70)
    print(f"\n{'策略':<20} {'总收益率':<12} {'年化收益':<12}")
    print("-" * 50)
    
    bh_annual1 = calc_annual(bh_reinvest['total_return'])
    bh_annual2 = calc_annual(bh_no_reinvest['total_return'])
    print(f"{bh_reinvest['name']:<18} {bh_reinvest['total_return']:>8.2f}% {bh_annual1:>10.2f}%")
    print(f"{bh_no_reinvest['name']:<18} {bh_no_reinvest['total_return']:>8.2f}% {bh_annual2:>10.2f}%")
    
    # 分析
    print("\n" + "=" * 70)
    print("分析总结")
    print("=" * 70)
    
    r1, r2, r3 = results
    print(f"""
【分红处理方式影响】

RSI策略:
  • 分红立即再投资: {r1['total_return']:.2f}% (年化 {calc_annual(r1['total_return']):.2f}%)
  • 分红等信号再投: {r2['total_return']:.2f}% (年化 {calc_annual(r2['total_return']):.2f}%)
  • 分红不投资:     {r3['total_return']:.2f}% (年化 {calc_annual(r3['total_return']):.2f}%)

买入持有:
  • 分红再投资:     {bh_reinvest['total_return']:.2f}% (年化 {bh_annual1:.2f}%)
  • 分红不投资:     {bh_no_reinvest['total_return']:.2f}% (年化 {bh_annual2:.2f}%)

【差异分析】
  • RSI策略分红再投 vs 不投: 差异 {r1['total_return'] - r3['total_return']:.2f}%
  • 买入持有分红再投 vs 不投: 差异 {bh_reinvest['total_return'] - bh_no_reinvest['total_return']:.2f}%

【结论】
  分红再投资能带来约 {r1['total_return'] - r3['total_return']:.1f}% 的额外收益（复利效应）
  RSI策略因为会卖出持仓，实际享受到的分红次数更少
""")


if __name__ == "__main__":
    main()
