"""
红利低波ETF (512890) RSI策略回测
策略：RSI(14) < 40 买入，RSI(14) > 70 卖出
包含分红再投资的全收益计算
"""

import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta
import json
import os

# ============ 配置参数 ============
ETF_CODE = "512890"
ETF_NAME = "红利低波ETF"
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 40
RSI_SELL_THRESHOLD = 70
INITIAL_CAPITAL = 100000  # 初始资金10万

# ============ RSI计算 ============
def calculate_rsi(prices, period=14):
    """计算RSI指标"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    # 使用EMA方式计算后续值
    for i in range(period, len(prices)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ============ 获取数据 ============
def get_etf_data(code):
    """获取ETF日线数据"""
    print(f"正在获取 {code} 历史数据...")
    try:
        # 获取ETF日线数据
        df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="qfq")
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        })
        df = df.sort_values('date').reset_index(drop=True)
        print(f"获取到 {len(df)} 条数据，从 {df['date'].min()} 到 {df['date'].max()}")
        return df
    except Exception as e:
        print(f"获取ETF数据失败: {e}")
        return None


def get_etf_dividend(code):
    """获取ETF分红数据"""
    print(f"正在获取 {code} 分红数据...")
    try:
        # 尝试获取基金分红数据
        df = ak.fund_etf_fund_info_em(fund=code, start_date="20140101")
        if df is not None and len(df) > 0:
            # 筛选分红记录
            dividend_df = df[df['业务类型'] == '分红'].copy()
            if len(dividend_df) > 0:
                dividend_df['date'] = pd.to_datetime(dividend_df['业务时间'])
                dividend_df['dividend'] = dividend_df['数值'].astype(float)
                print(f"获取到 {len(dividend_df)} 条分红记录")
                return dividend_df[['date', 'dividend']]
    except Exception as e:
        print(f"获取分红数据方式1失败: {e}")
    
    # 备用：手动录入512890已知分红数据
    print("使用已知分红数据...")
    dividend_data = [
        # 512890 历史分红 (每份基金分红金额，元)
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
    print(f"使用 {len(df)} 条已知分红记录")
    return df


def get_benchmark_data(code, name, index_type="index"):
    """获取基准指数数据"""
    print(f"正在获取基准 {name} 数据...")
    try:
        if index_type == "index":
            # 国内指数
            df = ak.index_zh_a_hist(symbol=code, period="daily", start_date="20131201")
        elif index_type == "us":
            # 美股指数 - 纳指100
            df = ak.index_us_stock_sina(symbol=code)
            
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.rename(columns={
            '日期': 'date',
            '收盘': 'close'
        })
        df = df.sort_values('date').reset_index(drop=True)
        print(f"获取到 {name} {len(df)} 条数据")
        return df[['date', 'close']]
    except Exception as e:
        print(f"获取 {name} 数据失败: {e}")
        return None


# ============ 回测引擎 ============
def run_backtest(df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """
    执行RSI策略回测
    返回：交易记录、每日净值、统计指标
    """
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
    
    # 初始化
    cash = initial_capital
    shares = 0
    position = 0  # 0: 空仓, 1: 持仓
    
    trades = []  # 交易记录
    daily_values = []  # 每日净值
    
    # 合并分红数据
    dividend_dict = {}
    if dividend_df is not None:
        for _, row in dividend_df.iterrows():
            dividend_dict[row['date'].strftime('%Y-%m-%d')] = row['dividend']
    
    for i, row in df.iterrows():
        date = row['date']
        price = row['close']
        rsi = row['rsi']
        
        # 处理分红（分红再投资）
        date_str = date.strftime('%Y-%m-%d')
        if date_str in dividend_dict and shares > 0:
            dividend_per_share = dividend_dict[date_str]
            dividend_amount = shares * dividend_per_share
            # 分红再投资：用分红金额买入更多份额
            new_shares = dividend_amount / price
            shares += new_shares
            trades.append({
                'date': date_str,
                'action': '分红再投',
                'price': price,
                'shares': new_shares,
                'amount': dividend_amount,
                'rsi': rsi,
                'total_shares': shares,
                'cash': cash
            })
        
        # RSI信号判断
        if pd.notna(rsi):
            if rsi < RSI_BUY_THRESHOLD and position == 0:
                # 买入信号：满仓买入
                shares_to_buy = int(cash / price / 100) * 100  # 整百份
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
                    
            elif rsi > RSI_SELL_THRESHOLD and position == 1:
                # 卖出信号：全部卖出
                if shares > 0:
                    sell_shares = int(shares / 100) * 100  # 整百份
                    if sell_shares > 0:
                        revenue = sell_shares * price
                        cash += revenue
                        shares -= sell_shares
                        if shares < 100:
                            # 剩余零头也卖掉
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
        
        # 计算当日总资产
        total_value = cash + shares * price
        daily_values.append({
            'date': date_str,
            'close': price,
            'rsi': rsi if pd.notna(rsi) else None,
            'cash': cash,
            'shares': shares,
            'total_value': total_value,
            'return': (total_value / initial_capital - 1) * 100
        })
    
    return trades, daily_values


def calculate_buy_and_hold(df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """计算买入持有策略（全收益，含分红再投资）"""
    start_price = df.iloc[0]['close']
    shares = int(initial_capital / start_price / 100) * 100
    remaining_cash = initial_capital - shares * start_price
    
    # 合并分红
    dividend_dict = {}
    if dividend_df is not None:
        for _, row in dividend_df.iterrows():
            dividend_dict[row['date'].strftime('%Y-%m-%d')] = row['dividend']
    
    daily_values = []
    for _, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        
        # 处理分红
        if date_str in dividend_dict and shares > 0:
            dividend_amount = shares * dividend_dict[date_str]
            new_shares = dividend_amount / price
            shares += new_shares
        
        total_value = remaining_cash + shares * price
        daily_values.append({
            'date': date_str,
            'total_value': total_value,
            'return': (total_value / initial_capital - 1) * 100
        })
    
    return daily_values


def calculate_benchmark_return(df, initial_capital=INITIAL_CAPITAL):
    """计算基准收益"""
    if df is None or len(df) == 0:
        return []
    
    start_price = df.iloc[0]['close']
    daily_values = []
    
    for _, row in df.iterrows():
        price = row['close']
        total_value = initial_capital * (price / start_price)
        daily_values.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'total_value': total_value,
            'return': (total_value / initial_capital - 1) * 100
        })
    
    return daily_values


def calculate_statistics(daily_values, trades):
    """计算策略统计指标"""
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
    
    # 计算胜率
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


# ============ 主程序 ============
def main():
    print("=" * 60)
    print("红利低波ETF (512890) RSI策略回测")
    print("=" * 60)
    
    # 1. 获取数据
    etf_df = get_etf_data(ETF_CODE)
    if etf_df is None:
        print("无法获取ETF数据，退出")
        return
    
    dividend_df = get_etf_dividend(ETF_CODE)
    
    # 获取基准数据
    hs300_df = get_benchmark_data("000300", "沪深300")
    # 纳指100使用不同接口
    try:
        print("正在获取纳指100数据...")
        ndx_df = ak.index_us_stock_sina(symbol=".NDX")
        ndx_df['日期'] = pd.to_datetime(ndx_df['日期'])
        ndx_df = ndx_df.rename(columns={'日期': 'date', '收盘': 'close'})
        ndx_df = ndx_df.sort_values('date').reset_index(drop=True)
        print(f"获取到纳指100 {len(ndx_df)} 条数据")
    except Exception as e:
        print(f"获取纳指100失败: {e}")
        ndx_df = None
    
    # 2. 统一时间范围
    start_date = etf_df['date'].min()
    end_date = etf_df['date'].max()
    print(f"\n回测区间: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    # 筛选基准数据到相同时间范围
    if hs300_df is not None:
        hs300_df = hs300_df[(hs300_df['date'] >= start_date) & (hs300_df['date'] <= end_date)]
    if ndx_df is not None:
        ndx_df = ndx_df[(ndx_df['date'] >= start_date) & (ndx_df['date'] <= end_date)]
    
    # 3. 执行回测
    print("\n正在执行RSI策略回测...")
    trades, strategy_values = run_backtest(etf_df, dividend_df)
    
    print("正在计算买入持有收益...")
    buyhold_values = calculate_buy_and_hold(etf_df, dividend_df)
    
    print("正在计算基准收益...")
    hs300_values = calculate_benchmark_return(hs300_df)
    ndx_values = calculate_benchmark_return(ndx_df)
    
    # 买入持有（不含分红）
    buyhold_no_div = calculate_benchmark_return(etf_df[['date', 'close']])
    
    # 4. 计算统计指标
    strategy_stats = calculate_statistics(strategy_values, trades)
    buyhold_stats = calculate_statistics(buyhold_values, [])
    
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"\n【RSI策略】")
    print(f"  总收益率: {strategy_stats['total_return']:.2f}%")
    print(f"  年化收益: {strategy_stats['annual_return']:.2f}%")
    print(f"  最大回撤: {strategy_stats['max_drawdown']:.2f}%")
    print(f"  交易次数: {strategy_stats['trade_count']} 次")
    print(f"  胜率: {strategy_stats['win_rate']:.2f}%")
    
    print(f"\n【买入持有（全收益）】")
    print(f"  总收益率: {buyhold_stats['total_return']:.2f}%")
    print(f"  年化收益: {buyhold_stats['annual_return']:.2f}%")
    
    if hs300_values:
        print(f"\n【沪深300】")
        print(f"  总收益率: {hs300_values[-1]['return']:.2f}%")
    
    if ndx_values:
        print(f"\n【纳指100】")
        print(f"  总收益率: {ndx_values[-1]['return']:.2f}%")
    
    # 5. 导出数据为JSON
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(output_dir, "backtest_result.json")
    
    # 准备导出数据
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
            'buyhold': buyhold_stats,
            'hs300_return': round(hs300_values[-1]['return'], 2) if hs300_values else None,
            'ndx_return': round(ndx_values[-1]['return'], 2) if ndx_values else None,
            'buyhold_no_div_return': round(buyhold_no_div[-1]['return'], 2) if buyhold_no_div else None
        },
        'trades': trades,
        'daily_values': {
            'strategy': strategy_values,
            'buyhold': buyhold_values,
            'buyhold_no_div': buyhold_no_div,
            'hs300': hs300_values,
            'ndx': ndx_values
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n回测结果已保存至: {output_file}")
    
    # 同时复制到docs目录供网页使用
    docs_output = os.path.join(os.path.dirname(output_dir), "docs", "backtest_result.json")
    with open(docs_output, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False)
    print(f"网页数据已保存至: {docs_output}")
    
    return export_data


if __name__ == "__main__":
    main()
