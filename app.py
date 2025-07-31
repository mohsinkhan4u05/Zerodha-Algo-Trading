"""
Flask server for Zerodha Algo Trading with Kite Connect API
"""

from flask import Flask, request, jsonify
import logging
from typing import Dict, Any
from kite_utils import generate_access_token, place_order, load_config, get_positions, get_holdings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure Flask
app.config['JSON_SORT_KEYS'] = False


@app.route('/', methods=['GET'])
def health_check():
    """
    Health check endpoint
    
    Returns:
        JSON response with server status
    """
    try:
        return jsonify({
            'status': 'success',
            'message': 'Zerodha Algo Trading Server is running',
            'service': 'kite-connect-api',
            'version': '1.0.0'
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
    Webhook endpoint to receive TradingView alerts
    
    Expected JSON payload:
    {
        "symbol": "RELIANCE",
        "order": "buy",
        "quantity": 1  // optional, defaults to 1
    }
    
    Returns:
        JSON response with order status
    """
    try:
        # Check if request contains JSON data
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'message': 'Request must contain JSON data'
            }), 400
        
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Empty JSON payload'
            }), 400
        
        symbol = data.get('symbol')
        order = data.get('order')
        quantity = data.get('quantity', 1)  # Default to 1 if not provided
        
        # Validate required fields
        if not symbol:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: symbol'
            }), 400
        
        if not order:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: order'
            }), 400
        
        # Validate order type
        if order.lower() not in ['buy', 'sell']:
            return jsonify({
                'status': 'error',
                'message': 'Order must be "buy" or "sell"'
            }), 400
        
        # Validate quantity
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return jsonify({
                    'status': 'error',
                    'message': 'Quantity must be a positive integer'
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                'status': 'error',
                'message': 'Quantity must be a valid integer'
            }), 400
        
        logger.info(f"Received webhook: {symbol} {order} {quantity}")
        
        # Place order using Kite API
        result = place_order(symbol, order, quantity)
        
        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 400
        
    except Exception as e:
        error_msg = f"Webhook error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/generate_token', methods=['POST'])
def generate_token():
    """
    Generate access token using request token
    
    Expected JSON payload:
    {
        "request_token": "your_request_token_here"
    }
    
    Returns:
        JSON response with access token generation status
    """
    try:
        # Check if request contains JSON data
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'message': 'Request must contain JSON data'
            }), 400
        
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Empty JSON payload'
            }), 400
        
        request_token = data.get('request_token')
        
        if not request_token:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: request_token'
            }), 400
        
        logger.info(f"Generating access token for request token: {request_token[:10]}...")
        
        # Generate access token
        access_token = generate_access_token(request_token)
        
        return jsonify({
            'status': 'success',
            'message': 'Access token generated and saved successfully',
            'access_token': access_token[:10] + '...',  # Show only first 10 characters for security
            'request_token': request_token[:10] + '...'
        }), 200
        
    except Exception as e:
        error_msg = f"Token generation error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 400


@app.route('/positions', methods=['GET'])
def get_current_positions():
    """
    Get current positions from Kite API
    
    Returns:
        JSON response with positions data
    """
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


@app.route('/holdings', methods=['GET'])
def get_current_holdings():
    """
    Get current holdings from Kite API
    
    Returns:
        JSON response with holdings data
    """
    try:
        result = get_holdings()
        
        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        error_msg = f"Holdings fetch error: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500


@app.route('/config', methods=['GET'])
def get_config_status():
    """
    Get configuration status (without exposing sensitive data)
    
    Returns:
        JSON response with config status
    """
    try:
        config = load_config()
        
        return jsonify({
            'status': 'success',
            'config_status': {
                'api_key_configured': bool(config.get('api_key') and config['api_key'] != 'your_api_key_here'),
                'api_secret_configured': bool(config.get('api_secret') and config['api_secret'] != 'your_api_secret_here'),
                'request_token_available': bool(config.get('request_token')),
                'access_token_available': bool(config.get('access_token'))
            }
        }), 200
        
    except Exception as e:
        error_msg = f"Config status error: {str(e)}"
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
    logger.info("Starting Zerodha Algo Trading Server...")
    
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
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)