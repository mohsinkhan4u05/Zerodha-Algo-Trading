"""
Kite Connect API utility functions for Zerodha Algo Trading
"""

import json
import logging
from typing import Optional, Dict, Any
from kiteconnect import KiteConnect

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json file
    
    Returns:
        dict: Configuration dictionary
    """
    try:
        with open(CONFIG_FILE, 'r') as file:
            config = json.load(file)
            logger.info("Configuration loaded successfully")
            return config
    except FileNotFoundError:
        logger.error(f"Configuration file {CONFIG_FILE} not found")
        raise Exception(f"Configuration file {CONFIG_FILE} not found")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {CONFIG_FILE}")
        raise Exception(f"Invalid JSON in {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        raise Exception(f"Error loading configuration: {str(e)}")


def save_config(config: Dict[str, Any]) -> None:
    """
    Save configuration to config.json file
    
    Args:
        config (dict): Configuration dictionary to save
    """
    try:
        with open(CONFIG_FILE, 'w') as file:
            json.dump(config, file, indent=4)
            logger.info("Configuration saved successfully")
    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        raise Exception(f"Error saving configuration: {str(e)}")


def generate_access_token(request_token: str) -> str:
    """
    Generate access token using request token
    
    Args:
        request_token (str): Request token from Kite Connect
        
    Returns:
        str: Access token
    """
    try:
        config = load_config()
        
        # Validate required configuration
        if not config.get('api_key') or not config.get('api_secret'):
            raise Exception("API key and secret are required in config.json")
        
        # Initialize KiteConnect
        kite = KiteConnect(api_key=config['api_key'])
        
        # Generate session
        data = kite.generate_session(request_token, api_secret=config['api_secret'])
        access_token = data["access_token"]
        
        # Update config with tokens
        config['request_token'] = request_token
        config['access_token'] = access_token
        save_config(config)
        
        logger.info("Access token generated and saved successfully")
        return access_token
        
    except Exception as e:
        logger.error(f"Error generating access token: {str(e)}")
        raise Exception(f"Error generating access token: {str(e)}")


def get_kite() -> KiteConnect:
    """
    Get configured KiteConnect instance
    
    Returns:
        KiteConnect: Configured KiteConnect instance
    """
    try:
        config = load_config()
        
        # Validate required configuration
        if not config.get('api_key'):
            raise Exception("API key is required in config.json")
        
        if not config.get('access_token'):
            raise Exception("Access token is required. Please generate it first using /generate_token endpoint")
        
        # Initialize KiteConnect with access token
        kite = KiteConnect(api_key=config['api_key'])
        kite.set_access_token(config['access_token'])
        
        logger.info("KiteConnect instance created successfully")
        return kite
        
    except Exception as e:
        logger.error(f"Error creating KiteConnect instance: {str(e)}")
        raise Exception(f"Error creating KiteConnect instance: {str(e)}")


def place_order(symbol: str, action: str, qty: int = 1) -> Dict[str, Any]:
    """
    Place a market order using Kite API
    
    Args:
        symbol (str): Trading symbol (e.g., "RELIANCE")
        action (str): Order action ("buy" or "sell")
        qty (int): Quantity to trade (default: 1)
        
    Returns:
        dict: Order response from Kite API
    """
    try:
        # Validate inputs
        if action.lower() not in ['buy', 'sell']:
            raise Exception("Action must be 'buy' or 'sell'")
        
        if qty <= 0:
            raise Exception("Quantity must be greater than 0")
        
        # Get KiteConnect instance
        kite = get_kite()
        
        # Map action to Kite transaction type
        transaction_type = kite.TRANSACTION_TYPE_BUY if action.lower() == 'buy' else kite.TRANSACTION_TYPE_SELL
        
        # Place order
        order_params = {
            'tradingsymbol': symbol.upper(),
            'exchange': kite.EXCHANGE_NSE,  # Default to NSE
            'transaction_type': transaction_type,
            'quantity': qty,
            'product': kite.PRODUCT_MIS,  # Intraday
            'order_type': kite.ORDER_TYPE_MARKET,
            'validity': kite.VALIDITY_DAY
        }
        
        order_id = kite.place_order(**order_params)
        
        logger.info(f"Order placed successfully: {order_id}")
        
        return {
            'status': 'success',
            'order_id': order_id,
            'symbol': symbol.upper(),
            'action': action.lower(),
            'quantity': qty,
            'message': f'{action.capitalize()} order for {qty} shares of {symbol.upper()} placed successfully'
        }
        
    except Exception as e:
        error_msg = f"Error placing order: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg,
            'symbol': symbol,
            'action': action,
            'quantity': qty
        }


def get_positions() -> Dict[str, Any]:
    """
    Get current positions from Kite API
    
    Returns:
        dict: Positions data
    """
    try:
        kite = get_kite()
        positions = kite.positions()
        logger.info("Positions fetched successfully")
        return {
            'status': 'success',
            'data': positions
        }
    except Exception as e:
        error_msg = f"Error fetching positions: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg
        }


def get_holdings() -> Dict[str, Any]:
    """
    Get current holdings from Kite API
    
    Returns:
        dict: Holdings data
    """
    try:
        kite = get_kite()
        holdings = kite.holdings()
        logger.info("Holdings fetched successfully")
        return {
            'status': 'success',
            'data': holdings
        }
    except Exception as e:
        error_msg = f"Error fetching holdings: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'message': error_msg
        }