#!/usr/bin/env python3
"""
期权价格监测网站 - 数据更新脚本
生成JSON数据供前端网站使用
"""
import requests
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path

def get_deribit_options(currency):
    """获取 Deribit 期权数据"""
    url = f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={currency}&kind=option"
    resp = requests.get(url, timeout=30)
    return resp.json()['result']

def parse_instrument(name):
    """解析期权名称"""
    parts = name.split('-')
    if len(parts) >= 4:
        date_str = parts[1]
        strike = float(parts[2])
        opt_type = parts[3]
        try:
            expiry = datetime.strptime(date_str, '%d%b%y')
        except:
            return None, None, None
        return expiry, strike, opt_type
    return None, None, None

def load_historical_data():
    """加载历史数据"""
    hist_file = '/home/admin/.openclaw/workspace/options_analysis_2023_now.csv'
    data = []
    with open(hist_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append({
                'asset': row['资产'],
                'date': row['周六日期'],
                'type': row['类型'],
                'expiry': row['到期日'],
                'instrument': row['Instrument'],
                'strike': float(row['Strike']),
                'price': float(row['价格']),
                'index': float(row['Index']),
                'iv': float(row['IV'].rstrip('%'))
            })
    return data

def calculate_ratios(hist_data):
    """计算短长期比例"""
    ratios = {'BTC': [], 'ETH': []}
    
    for asset in ['BTC', 'ETH']:
        asset_data = [d for d in hist_data if d['asset'] == asset]
        dates = sorted(set(d['date'] for d in asset_data))
        
        for date in dates:
            day_data = [d for d in asset_data if d['date'] == date]
            weekly = [d for d in day_data if d['type'] == '周期权']
            biweekly = [d for d in day_data if d['type'] == '两周期权']
            
            if weekly and biweekly:
                weekly_price = weekly[0]['price']
                biweekly_price = biweekly[0]['price']
                
                if weekly_price > 0:
                    ratio = biweekly_price / weekly_price
                    ratios[asset].append({
                        'date': date,
                        'ratio': round(ratio, 3),
                        'weekly_price': weekly_price,
                        'biweekly_price': biweekly_price,
                        'iv_weekly': weekly[0]['iv'],
                        'iv_biweekly': biweekly[0]['iv'],
                        'index': weekly[0]['index']
                    })
    
    return ratios

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始更新期权监测数据...")
    
    # 获取实时数据
    now = datetime.now()
    
    try:
        btc_data = get_deribit_options('BTC')
        eth_data = get_deribit_options('ETH')
    except Exception as e:
        print(f"❌ 获取实时数据失败: {e}")
        return
    
    btc_price = None
    btc_puts = []
    eth_price = None
    eth_puts = []
    
    for opt in btc_data:
        expiry, strike, opt_type = parse_instrument(opt['instrument_name'])
        if expiry is None:
            continue
        if btc_price is None and 'underlying_price' in opt:
            btc_price = opt['underlying_price']
        if opt_type != 'P':
            continue
        days = (expiry - now).days
        if days < 1:
            continue
        price = opt.get('mark_price', 0)
        iv = opt.get('mark_iv', 0)
        btc_puts.append({
            'instrument': opt['instrument_name'],
            'expiry': expiry.strftime('%Y-%m-%d'),
            'days': days,
            'strike': strike,
            'price': price,
            'iv': iv,
            'daily_price': price / days if days > 0 else 0
        })
    
    for opt in eth_data:
        expiry, strike, opt_type = parse_instrument(opt['instrument_name'])
        if expiry is None:
            continue
        if eth_price is None and 'underlying_price' in opt:
            eth_price = opt['underlying_price']
        if opt_type != 'P':
            continue
        days = (expiry - now).days
        if days < 1:
            continue
        price = opt.get('mark_price', 0)
        iv = opt.get('mark_iv', 0)
        eth_puts.append({
            'instrument': opt['instrument_name'],
            'expiry': expiry.strftime('%Y-%m-%d'),
            'days': days,
            'strike': strike,
            'price': price,
            'iv': iv,
            'daily_price': price / days if days > 0 else 0
        })
    
    # 筛选目标期权
    btc_target = btc_price * 0.90 if btc_price else 65000
    eth_target = eth_price * 0.85 if eth_price else 1700
    
    btc_short = min([p for p in btc_puts if 3 <= p['days'] <= 7 and abs(p['strike'] - btc_target) / btc_target < 0.1], 
                    key=lambda x: abs(x['strike'] - btc_target), default=None)
    btc_mid = min([p for p in btc_puts if 8 <= p['days'] <= 14 and abs(p['strike'] - btc_target) / btc_target < 0.1], 
                  key=lambda x: abs(x['strike'] - btc_target), default=None)
    btc_long = min([p for p in btc_puts if 20 <= p['days'] <= 35 and abs(p['strike'] - btc_target) / btc_target < 0.1], 
                   key=lambda x: abs(x['strike'] - btc_target), default=None)
    
    eth_short = min([p for p in eth_puts if 3 <= p['days'] <= 7 and abs(p['strike'] - eth_target) / eth_target < 0.1], 
                    key=lambda x: abs(x['strike'] - eth_target), default=None)
    eth_mid = min([p for p in eth_puts if 8 <= p['days'] <= 14 and abs(p['strike'] - eth_target) / eth_target < 0.1], 
                  key=lambda x: abs(x['strike'] - eth_target), default=None)
    eth_long = min([p for p in eth_puts if 20 <= p['days'] <= 35 and abs(p['strike'] - eth_target) / eth_target < 0.1], 
                   key=lambda x: abs(x['strike'] - eth_target), default=None)
    
    # 加载历史数据并计算比率
    hist_data = load_historical_data()
    ratios = calculate_ratios(hist_data)
    
    # 准备输出数据
    output = {
        'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
        'spot_prices': {
            'BTC': btc_price,
            'ETH': eth_price
        },
        'options': {
            'BTC': {
                'short': btc_short,
                'mid': btc_mid,
                'long': btc_long,
                'ratios': {
                    'short_mid': btc_short['daily_price'] / btc_mid['daily_price'] if btc_short and btc_mid else None,
                    'short_long': btc_short['daily_price'] / btc_long['daily_price'] if btc_short and btc_long else None,
                    'mid_long': btc_mid['daily_price'] / btc_long['daily_price'] if btc_mid and btc_long else None
                }
            },
            'ETH': {
                'short': eth_short,
                'mid': eth_mid,
                'long': eth_long,
                'ratios': {
                    'short_mid': eth_short['daily_price'] / eth_mid['daily_price'] if eth_short and eth_mid else None,
                    'short_long': eth_short['daily_price'] / eth_long['daily_price'] if eth_short and eth_long else None,
                    'mid_long': eth_mid['daily_price'] / eth_long['daily_price'] if eth_mid and eth_long else None
                }
            }
        },
        'historical_ratios': ratios
    }
    
    # 保存JSON文件
    output_dir = Path('/home/admin/.openclaw/workspace/options-monitor-web/data')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'options_data.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ 数据已更新并保存到 {output_dir / 'options_data.json'}")
    print(f"\n📊 当前数据摘要:")
    print(f"  BTC: ${btc_price:,.2f} | ETH: ${eth_price:,.2f}")
    if btc_short and btc_mid:
        print(f"  BTC 短/中比率: {output['options']['BTC']['ratios']['short_mid']:.3f}x")
    if eth_short and eth_mid:
        print(f"  ETH 短/中比率: {output['options']['ETH']['ratios']['short_mid']:.3f}x")
    print(f"  历史数据点: BTC {len(ratios['BTC'])} | ETH {len(ratios['ETH'])}")

if __name__ == '__main__':
    main()