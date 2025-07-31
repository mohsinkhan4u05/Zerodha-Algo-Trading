#!/usr/bin/env python3
"""
Test script for Support & Resistance Strategy
This script demonstrates how to use the strategy without actual trading
"""

import json
import time
import requests
from typing import List, Dict

# Test configuration
BASE_URL = "http://localhost:5000"
TEST_SYMBOL = "RELIANCE"

# Sample price data for testing (simulating price movement)
SAMPLE_PRICE_DATA = [
    {"high": 2500, "low": 2480, "close": 2490},  # Initial data
    {"high": 2510, "low": 2485, "close": 2495},
    {"high": 2520, "low": 2490, "close": 2505},
    {"high": 2515, "low": 2495, "close": 2500},  # Swing high
    {"high": 2505, "low": 2485, "close": 2490},
    {"high": 2495, "low": 2475, "close": 2480},  # Swing low
    {"high": 2490, "low": 2470, "close": 2475},
    {"high": 2485, "low": 2465, "close": 2470},
    {"high": 2480, "low": 2460, "close": 2465},
    {"high": 2475, "low": 2455, "close": 2460},
    {"high": 2470, "low": 2450, "close": 2455},
    {"high": 2465, "low": 2445, "close": 2450},  # Build base
    {"high": 2460, "low": 2440, "close": 2445},
    {"high": 2455, "low": 2435, "close": 2440},
    {"high": 2525, "low": 2505, "close": 2520},  # Potential breakout above resistance
]

def test_server_health():
    """Test if the server is running"""
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is running: {data['message']}")
            return True
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on http://localhost:5000")
        return False
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def send_price_data(symbol: str, price_data: Dict):
    """Send price data to the webhook endpoint"""
    try:
        payload = {
            "symbol": symbol,
            "high": price_data["high"],
            "low": price_data["low"],
            "close": price_data["close"],
            "quantity": 1
        }
        
        response = requests.post(f"{BASE_URL}/webhook", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Price data sent: H:{price_data['high']}, L:{price_data['low']}, C:{price_data['close']}")
            
            if data.get('levels_updated'):
                levels = data.get('current_levels', {})
                support = levels.get('support')
                resistance = levels.get('resistance')
                locked = levels.get('locked')
                
                if support and resistance:
                    print(f"📈 S/R Levels - Support: {support}, Resistance: {resistance}, Locked: {locked}")
            
            if data.get('breakout_signal'):
                signal = data.get('breakout_signal')
                trade_entered = data.get('trade_entered')
                print(f"🚀 BREAKOUT SIGNAL: {signal.upper()}")
                
                if trade_entered:
                    print(f"✅ Trade entered successfully!")
                    order_result = data.get('order_result', {})
                    if order_result.get('status') == 'success':
                        print(f"📋 Order ID: {order_result.get('order_id')}")
                else:
                    print(f"❌ Failed to enter trade: {data.get('order_error', 'Unknown error')}")
            
            return data
        else:
            print(f"❌ Failed to send price data: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error sending price data: {str(e)}")
        return None

def get_strategy_status(symbol: str):
    """Get strategy status for a symbol"""
    try:
        response = requests.get(f"{BASE_URL}/strategy/{symbol}")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('strategy_status', {})
            
            print(f"\n📊 Strategy Status for {symbol}:")
            print(f"   Support Level: {status.get('support_level')}")
            print(f"   Resistance Level: {status.get('resistance_level')}")
            print(f"   Levels Locked: {status.get('levels_locked')}")
            print(f"   Data Points: {status.get('data_points')}")
            
            active_trade = status.get('active_trade', {})
            if active_trade.get('is_active'):
                print(f"   🔥 ACTIVE TRADE:")
                print(f"      Direction: {active_trade.get('direction')}")
                print(f"      Entry Price: {active_trade.get('entry_price')}")
                print(f"      Quantity: {active_trade.get('quantity')}")
                print(f"      Target Price: {active_trade.get('target_price')}")
                print(f"      Stop Price: {active_trade.get('stop_price')}")
            else:
                print(f"   No active trade")
            
            return status
        else:
            print(f"❌ Failed to get strategy status: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting strategy status: {str(e)}")
        return None

def get_monitoring_status():
    """Get monitoring status"""
    try:
        response = requests.get(f"{BASE_URL}/monitoring")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n🔍 Monitoring Status:")
            print(f"   Monitoring Active: {data.get('monitoring_active')}")
            print(f"   Active Strategies: {data.get('active_strategies')}")
            print(f"   Total Strategies: {data.get('total_strategies')}")
            return data
        else:
            print(f"❌ Failed to get monitoring status: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting monitoring status: {str(e)}")
        return None

def reset_strategy(symbol: str):
    """Reset strategy for a symbol"""
    try:
        response = requests.post(f"{BASE_URL}/strategy/{symbol}/reset")
        
        if response.status_code == 200:
            data = response.json()
            print(f"🔄 Strategy reset for {symbol}: {data.get('message')}")
            return True
        else:
            print(f"❌ Failed to reset strategy: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error resetting strategy: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting Support & Resistance Strategy Test")
    print("=" * 50)
    
    # Test server health
    if not test_server_health():
        print("\n❌ Server is not running. Please start the server first:")
        print("   python main.py")
        return
    
    # Reset strategy to start fresh
    print(f"\n🔄 Resetting strategy for {TEST_SYMBOL}...")
    reset_strategy(TEST_SYMBOL)
    
    # Get initial monitoring status
    get_monitoring_status()
    
    print(f"\n📊 Sending sample price data for {TEST_SYMBOL}...")
    print("=" * 50)
    
    # Send price data step by step
    for i, price_data in enumerate(SAMPLE_PRICE_DATA):
        print(f"\n📈 Candle {i+1}/{len(SAMPLE_PRICE_DATA)}")
        
        result = send_price_data(TEST_SYMBOL, price_data)
        
        if result and result.get('breakout_signal'):
            print("\n🎯 BREAKOUT DETECTED! Checking strategy status...")
            get_strategy_status(TEST_SYMBOL)
            get_monitoring_status()
            
            # If this is a demo without actual API connection, we'll break here
            print("\n⚠️  Note: This is a demo without actual Zerodha API connection.")
            print("   In a real scenario, the system would:")
            print("   1. Place the breakout order via Kite Connect API")
            print("   2. Monitor LTP continuously")
            print("   3. Exit at 3% profit or 1% loss automatically")
            break
        
        # Small delay between price updates
        time.sleep(0.5)
    
    # Final strategy status
    print("\n📊 Final Strategy Status:")
    print("=" * 30)
    get_strategy_status(TEST_SYMBOL)
    
    print("\n✅ Test completed!")
    print("\nTo test with real trading:")
    print("1. Configure your Zerodha API credentials in config.json")
    print("2. Generate access token using /generate_token endpoint")
    print("3. Send real price data or connect TradingView alerts")

if __name__ == "__main__":
    main()