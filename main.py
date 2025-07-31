"""
Main Flask application for Zerodha Algo Trading with Support & Resistance Strategy
"""

from flask import Flask, request, jsonify
import logging
import threading
import time
from typing import Dict, Any

from kite_utils import (
    generate_access_token, place_order, load_config, 
    get_positions, get_holdings, get_ltp, get_ohlc, cancel_order, get_orders
)
from s_r_strategy import get_strategy, remove_strategy, strategy_instances

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global variables for monitoring
monitoring_active = False
monitoring_thread = None
monitoring_symbols = set()


def ltp_monitor():
    """
    Background thread to monitor LTP and check exit conditions
    """
    global monitoring_active
    
    while monitoring_active:
        try:
            # Get all active strategies
            active_strategies = []
            for symbol, strategy in strategy_instances.items():
                if strategy.active_trade['is_active']:
                    active_strategies.append((symbol, strategy))
            
            if not active_strategies:
                time.sleep(5)  # Sleep if no active trades
                continue
            
            # Check each active strategy
            for symbol, strategy in active_strategies:
                try:
                    # Get current LTP
                    ltp_result = get_ltp(symbol)
                    
                    if ltp_result['status'] != 'success':
                        logger.error(f"Failed to get LTP for {symbol}: {ltp_result.get('message', 'Unknown error')}")
                        continue
                    
                    current_price = ltp_result['ltp']
                    
                    # Check exit conditions
                    exit_signal = strategy.check_exit_conditions(current_price)
                    
                    if exit_signal:
                        logger.info(f"Exit signal detected for {symbol}: {exit_signal}")
                        
                        # Place exit order
                        trade = strategy.active_trade
                        exit_action = 'sell' if trade['direction'] == 'long' else 'buy'
                        
                        order_result = place_order(symbol, exit_action, trade['quantity'])
                        
                        if order_result['status'] == 'success':
                            # Exit the trade in strategy
                            trade_summary = strategy.exit_trade(
                                exit_price=current_price,
                                exit_reason=exit_signal,
                                exit_order_id=order_result.get('order_id')
                            )
                            
                            logger.info(f"Trade exited successfully: {trade_summary}")
                        else:
                            logger.error(f"Failed to place exit order for {symbol}: {order_result.get('message')}")
                
                except Exception as e:
                    logger.error(f"Error monitoring {symbol}: {str(e)}")
            
            time.sleep(2)  # Check every 2 seconds
            
        except Exception as e:
            logger.error(f"Error in LTP monitor: {str(e)}")
            time.sleep(5)
    
    logger.info("LTP monitoring stopped")


def start_monitoring():
    """Start the LTP monitoring thread"""
    global monitoring_active, monitoring_thread
    
    if not monitoring_active:
        monitoring_active = True
        monitoring_thread = threading.Thread(target=ltp_monitor, daemon=True)
        monitoring_thread.start()
        logger.info("LTP monitoring started")


def stop_monitoring():
    """Stop the LTP monitoring thread"""
    global monitoring_active, monitoring_thread
    
    if monitoring_active:
        monitoring_active = False
        if monitoring_thread:
            monitoring_thread.join(timeout=10)
        logger.info("LTP monitoring stopped")


@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        return jsonify({
            'status': 'success',
            'message': 'Zerodha S&R Strategy Server is running',
            'service': 'support-resistance-strategy',
            'version': '1.0.0',
            'monitoring_active': monitoring_active,
            'active_strategies': len([s for s in strategy_instances.values() if s.active_trade['is_active']])
        }), 200
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Server error during health check'
        }), 500


@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Webhook endpoint to receive price data and signals
    
    Expected JSON payload for price data:
    {
        "symbol": "RELIANCE",
        "high": 2500.0,
        "low": 2480.0,
        "close": 2495.0,
        "timestamp": "2023-01-01T10:00:00"  // optional
    }
    
    Expected JSON payload for manual signal:
    {
        "symbol": "RELIANCE",
        "action": "buy" or "sell",
        "quantity": 1,
        "signal_type": "manual"  // optional
    }
    """
    try:
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'message': 'Request must contain JSON data'
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Empty JSON payload'
            }), 400
        
        symbol = data.get('symbol')
        if not symbol:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: symbol'
            }), 400
        
        # Get or create strategy instance
        strategy = get_strategy(symbol)
        
        # Check if this is price data or manual signal
        if 'high' in data and 'low' in data and 'close' in data:
            # This is price data - add to strategy and check for signals
            high = float(data['high'])
            low = float(data['low'])
            close = float(data['close'])
            timestamp = data.get('timestamp')
            
            # Add price data to strategy
            strategy.add_price_data(high, low, close, timestamp)
            
            # Update S/R levels if not locked
            levels_updated = strategy.update_levels()
            
            # Check for breakout signal
            breakout_signal = strategy.check_breakout_signal(close)
            
            response = {
                'status': 'success',
                'symbol': symbol,
                'price_data_added': True,
                'levels_updated': levels_updated,
                'current_levels': {
                    'support': strategy.support_level,
                    'resistance': strategy.resistance_level,
                    'locked': strategy.levels_locked
                }
            }
            
            if breakout_signal:
                # Execute the breakout trade
                quantity = data.get('quantity', 1)
                
                order_result = place_order(symbol, breakout_signal, quantity)
                
                if order_result['status'] == 'success':
                    # Enter trade in strategy
                    trade_entered = strategy.enter_trade(
                        direction=breakout_signal,
                        entry_price=close,
                        quantity=quantity,
                        order_id=order_result.get('order_id')
                    )
                    
                    if trade_entered:
                        response['breakout_signal'] = breakout_signal
                        response['trade_entered'] = True
                        response['order_result'] = order_result
                        
                        # Start monitoring if not already active
                        start_monitoring()
                    else:
                        response['breakout_signal'] = breakout_signal
                        response['trade_entered'] = False
                        response['message'] = 'Failed to enter trade in strategy'
                else:
                    response['breakout_signal'] = breakout_signal
                    response['trade_entered'] = False
                    response['order_error'] = order_result.get('message')
            
            return jsonify(response), 200
        
        elif 'action' in data:
            # This is a manual trading signal
            action = data.get('action')
            quantity = data.get('quantity', 1)
            
            if action.lower() not in ['buy', 'sell']:
                return jsonify({
                    'status': 'error',
                    'message': 'Action must be "buy" or "sell"'
                }), 400
            
            # Place manual order
            order_result = place_order(symbol, action, quantity)
            
            return jsonify({
                'status': 'success',
                'symbol': symbol,
                'manual_order': True,
                'order_result': order_result
            }), 200
        
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid payload: must contain either price data (high, low, close) or manual signal (action)'
            }), 400
        
    except Exception as e:
        error_msg = f"Webhook error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/generate_token', methods=['POST'])
def generate_token():
    """Generate access token using request token"""
    try:
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'message': 'Request must contain JSON data'
            }), 400
        
        data = request.get_json()
        request_token = data.get('request_token')
        
        if not request_token:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: request_token'
            }), 400
        
        access_token = generate_access_token(request_token)
        
        return jsonify({
            'status': 'success',
            'message': 'Access token generated and saved successfully',
            'access_token': access_token[:10] + '...'
        }), 200
        
    except Exception as e:
        error_msg = f"Token generation error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 400


@app.route('/strategy/<symbol>', methods=['GET'])
def get_strategy_status(symbol):
    """Get strategy status for a symbol"""
    try:
        if symbol.upper() not in strategy_instances:
            return jsonify({
                'status': 'error',
                'message': f'No strategy found for {symbol}'
            }), 404
        
        strategy = strategy_instances[symbol.upper()]
        status = strategy.get_status()
        
        return jsonify({
            'status': 'success',
            'strategy_status': status
        }), 200
        
    except Exception as e:
        error_msg = f"Error getting strategy status: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/strategy/<symbol>/reset', methods=['POST'])
def reset_strategy(symbol):
    """Reset strategy for a symbol"""
    try:
        if symbol.upper() not in strategy_instances:
            return jsonify({
                'status': 'error',
                'message': f'No strategy found for {symbol}'
            }), 404
        
        strategy = strategy_instances[symbol.upper()]
        strategy.reset_strategy()
        
        return jsonify({
            'status': 'success',
            'message': f'Strategy reset for {symbol}'
        }), 200
        
    except Exception as e:
        error_msg = f"Error resetting strategy: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/strategy/<symbol>/exit', methods=['POST'])
def manual_exit(symbol):
    """Manually exit active trade for a symbol"""
    try:
        if symbol.upper() not in strategy_instances:
            return jsonify({
                'status': 'error',
                'message': f'No strategy found for {symbol}'
            }), 404
        
        strategy = strategy_instances[symbol.upper()]
        
        if not strategy.active_trade['is_active']:
            return jsonify({
                'status': 'error',
                'message': f'No active trade for {symbol}'
            }), 400
        
        # Get current LTP
        ltp_result = get_ltp(symbol)
        if ltp_result['status'] != 'success':
            return jsonify({
                'status': 'error',
                'message': f"Failed to get LTP: {ltp_result.get('message')}"
            }), 400
        
        current_price = ltp_result['ltp']
        trade = strategy.active_trade
        exit_action = 'sell' if trade['direction'] == 'long' else 'buy'
        
        # Place exit order
        order_result = place_order(symbol, exit_action, trade['quantity'])
        
        if order_result['status'] == 'success':
            # Exit the trade in strategy
            trade_summary = strategy.exit_trade(
                exit_price=current_price,
                exit_reason='manual',
                exit_order_id=order_result.get('order_id')
            )
            
            return jsonify({
                'status': 'success',
                'message': 'Trade exited manually',
                'trade_summary': trade_summary,
                'order_result': order_result
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f"Failed to place exit order: {order_result.get('message')}",
                'order_result': order_result
            }), 400
        
    except Exception as e:
        error_msg = f"Error in manual exit: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/ltp/<symbol>', methods=['GET'])
def get_symbol_ltp(symbol):
    """Get LTP for a symbol"""
    try:
        result = get_ltp(symbol)
        
        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        error_msg = f"LTP fetch error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/ohlc/<symbol>', methods=['GET'])
def get_symbol_ohlc(symbol):
    """Get OHLC data for a symbol"""
    try:
        result = get_ohlc(symbol)
        
        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        error_msg = f"OHLC fetch error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/positions', methods=['GET'])
def get_current_positions():
    """Get current positions"""
    try:
        result = get_positions()
        
        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        error_msg = f"Positions fetch error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/orders', methods=['GET'])
def get_all_orders():
    """Get all orders for the day"""
    try:
        result = get_orders()
        
        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        error_msg = f"Orders fetch error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/monitoring', methods=['GET'])
def get_monitoring_status():
    """Get monitoring status"""
    try:
        return jsonify({
            'status': 'success',
            'monitoring_active': monitoring_active,
            'active_strategies': len([s for s in strategy_instances.values() if s.active_trade['is_active']]),
            'total_strategies': len(strategy_instances)
        }), 200
        
    except Exception as e:
        error_msg = f"Monitoring status error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/monitoring/start', methods=['POST'])
def start_monitoring_endpoint():
    """Start LTP monitoring"""
    try:
        start_monitoring()
        return jsonify({
            'status': 'success',
            'message': 'Monitoring started'
        }), 200
        
    except Exception as e:
        error_msg = f"Error starting monitoring: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/monitoring/stop', methods=['POST'])
def stop_monitoring_endpoint():
    """Stop LTP monitoring"""
    try:
        stop_monitoring()
        return jsonify({
            'status': 'success',
            'message': 'Monitoring stopped'
        }), 200
        
    except Exception as e:
        error_msg = f"Error stopping monitoring: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Method not allowed'
    }), 405


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500


if __name__ == '__main__':
    logger.info("Starting Zerodha S&R Strategy Server...")
    
    # Check configuration on startup
    try:
        config = load_config()
        logger.info("Configuration loaded successfully")
        
        if config.get('api_key') == 'your_api_key_here' or not config.get('api_key'):
            logger.warning("API key not configured. Please update config.json")
        
        if config.get('api_secret') == 'your_api_secret_here' or not config.get('api_secret'):
            logger.warning("API secret not configured. Please update config.json")
            
    except Exception as e:
        logger.error(f"Configuration error on startup: {str(e)}")
    
    # Start monitoring thread
    start_monitoring()
    
    try:
        # Run Flask app
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    finally:
        # Stop monitoring when app shuts down
        stop_monitoring()