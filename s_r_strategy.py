"""
Support and Resistance Breakout Strategy for Zerodha Algo Trading
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SupportResistanceStrategy:
    """
    Support and Resistance Breakout Strategy
    
    Strategy Logic:
    1. Detect S/R levels using swing highs/lows with 10-candle lookback
    2. Lock levels once identified
    3. Wait for breakout (close above resistance = long, close below support = short)
    4. Exit at 3% profit target or 1% stop loss
    5. Reset levels only after trade completion
    """
    
    def __init__(self, symbol: str, lookback_period: int = 10, profit_target: float = 0.03, stop_loss: float = 0.01):
        """
        Initialize strategy parameters
        
        Args:
            symbol (str): Trading symbol
            lookback_period (int): Number of candles to look back for S/R levels
            profit_target (float): Profit target as percentage (0.03 = 3%)
            stop_loss (float): Stop loss as percentage (0.01 = 1%)
        """
        self.symbol = symbol.upper()
        self.lookback_period = lookback_period
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        
        # Strategy state
        self.support_level: Optional[float] = None
        self.resistance_level: Optional[float] = None
        self.levels_locked: bool = False
        
        # Trade state
        self.active_trade: Dict[str, Any] = {
            'is_active': False,
            'direction': None,  # 'long' or 'short'
            'entry_price': None,
            'entry_time': None,
            'quantity': 0,
            'order_id': None,
            'target_price': None,
            'stop_price': None
        }
        
        # Price data storage
        self.price_data: List[Dict[str, float]] = []
        self.max_data_points = 50  # Keep last 50 price points
        
        # Thread lock for thread safety
        self.lock = threading.Lock()
        
        logger.info(f"S/R Strategy initialized for {self.symbol}")
    
    def add_price_data(self, high: float, low: float, close: float, timestamp: Optional[str] = None) -> None:
        """
        Add new price data point
        
        Args:
            high (float): High price
            low (float): Low price
            close (float): Close price
            timestamp (str, optional): Timestamp of the data point
        """
        with self.lock:
            if timestamp is None:
                timestamp = datetime.now().isoformat()
            
            price_point = {
                'high': high,
                'low': low,
                'close': close,
                'timestamp': timestamp
            }
            
            self.price_data.append(price_point)
            
            # Keep only the last max_data_points
            if len(self.price_data) > self.max_data_points:
                self.price_data = self.price_data[-self.max_data_points:]
            
            logger.info(f"Added price data: H:{high}, L:{low}, C:{close}")
    
    def detect_support_resistance(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Detect support and resistance levels using swing highs and lows
        
        Returns:
            Tuple[Optional[float], Optional[float]]: (support_level, resistance_level)
        """
        if len(self.price_data) < self.lookback_period + 2:
            logger.warning(f"Insufficient data points: {len(self.price_data)}, need at least {self.lookback_period + 2}")
            return None, None
        
        # Get recent data for analysis
        recent_data = self.price_data[-self.lookback_period-2:]
        
        swing_highs = []
        swing_lows = []
        
        # Identify swing highs and lows
        for i in range(1, len(recent_data) - 1):
            current = recent_data[i]
            prev_candle = recent_data[i-1]
            next_candle = recent_data[i+1]
            
            # Swing high: current high > previous high and current high > next high
            if current['high'] > prev_candle['high'] and current['high'] > next_candle['high']:
                swing_highs.append(current['high'])
            
            # Swing low: current low < previous low and current low < next low
            if current['low'] < prev_candle['low'] and current['low'] < next_candle['low']:
                swing_lows.append(current['low'])
        
        # Calculate support and resistance levels
        support = min(swing_lows) if swing_lows else None
        resistance = max(swing_highs) if swing_highs else None
        
        logger.info(f"Detected levels - Support: {support}, Resistance: {resistance}")
        return support, resistance
    
    def update_levels(self) -> bool:
        """
        Update support and resistance levels if not locked
        
        Returns:
            bool: True if levels were updated, False if locked
        """
        with self.lock:
            if self.levels_locked:
                logger.info("Levels are locked, skipping update")
                return False
            
            support, resistance = self.detect_support_resistance()
            
            if support is not None and resistance is not None:
                # Ensure support < resistance
                if support >= resistance:
                    logger.warning(f"Invalid levels: Support ({support}) >= Resistance ({resistance})")
                    return False
                
                self.support_level = support
                self.resistance_level = resistance
                logger.info(f"Updated levels - Support: {support}, Resistance: {resistance}")
                return True
            
            return False
    
    def check_breakout_signal(self, current_price: float) -> Optional[str]:
        """
        Check for breakout signal
        
        Args:
            current_price (float): Current market price
            
        Returns:
            Optional[str]: 'long' for bullish breakout, 'short' for bearish breakout, None for no signal
        """
        with self.lock:
            # Skip if trade is already active
            if self.active_trade['is_active']:
                return None
            
            # Skip if levels are not set
            if self.support_level is None or self.resistance_level is None:
                return None
            
            # Check for bullish breakout (close above resistance)
            if current_price > self.resistance_level:
                logger.info(f"Bullish breakout detected: {current_price} > {self.resistance_level}")
                return 'long'
            
            # Check for bearish breakout (close below support)
            if current_price < self.support_level:
                logger.info(f"Bearish breakout detected: {current_price} < {self.support_level}")
                return 'short'
            
            return None
    
    def enter_trade(self, direction: str, entry_price: float, quantity: int, order_id: str = None) -> bool:
        """
        Enter a new trade
        
        Args:
            direction (str): 'long' or 'short'
            entry_price (float): Entry price
            quantity (int): Trade quantity
            order_id (str, optional): Order ID from broker
            
        Returns:
            bool: True if trade entered successfully
        """
        with self.lock:
            if self.active_trade['is_active']:
                logger.warning("Cannot enter trade: Another trade is already active")
                return False
            
            # Calculate target and stop prices
            if direction == 'long':
                target_price = entry_price * (1 + self.profit_target)
                stop_price = entry_price * (1 - self.stop_loss)
            else:  # short
                target_price = entry_price * (1 - self.profit_target)
                stop_price = entry_price * (1 + self.stop_loss)
            
            # Update trade state
            self.active_trade = {
                'is_active': True,
                'direction': direction,
                'entry_price': entry_price,
                'entry_time': datetime.now().isoformat(),
                'quantity': quantity,
                'order_id': order_id,
                'target_price': target_price,
                'stop_price': stop_price
            }
            
            # Lock the levels
            self.levels_locked = True
            
            logger.info(f"Trade entered: {direction} {quantity} shares at {entry_price}")
            logger.info(f"Target: {target_price:.2f}, Stop: {stop_price:.2f}")
            
            return True
    
    def check_exit_conditions(self, current_price: float) -> Optional[str]:
        """
        Check if exit conditions are met
        
        Args:
            current_price (float): Current market price
            
        Returns:
            Optional[str]: 'profit' if target hit, 'loss' if stop hit, None if no exit
        """
        with self.lock:
            if not self.active_trade['is_active']:
                return None
            
            direction = self.active_trade['direction']
            target_price = self.active_trade['target_price']
            stop_price = self.active_trade['stop_price']
            
            if direction == 'long':
                # Long position: exit if price >= target or price <= stop
                if current_price >= target_price:
                    logger.info(f"Profit target hit: {current_price} >= {target_price}")
                    return 'profit'
                elif current_price <= stop_price:
                    logger.info(f"Stop loss hit: {current_price} <= {stop_price}")
                    return 'loss'
            
            else:  # short position
                # Short position: exit if price <= target or price >= stop
                if current_price <= target_price:
                    logger.info(f"Profit target hit: {current_price} <= {target_price}")
                    return 'profit'
                elif current_price >= stop_price:
                    logger.info(f"Stop loss hit: {current_price} >= {stop_price}")
                    return 'loss'
            
            return None
    
    def exit_trade(self, exit_price: float, exit_reason: str, exit_order_id: str = None) -> Dict[str, Any]:
        """
        Exit the current trade
        
        Args:
            exit_price (float): Exit price
            exit_reason (str): Reason for exit ('profit', 'loss', 'manual')
            exit_order_id (str, optional): Exit order ID
            
        Returns:
            Dict[str, Any]: Trade summary
        """
        with self.lock:
            if not self.active_trade['is_active']:
                logger.warning("No active trade to exit")
                return {}
            
            # Calculate P&L
            entry_price = self.active_trade['entry_price']
            quantity = self.active_trade['quantity']
            direction = self.active_trade['direction']
            
            if direction == 'long':
                pnl = (exit_price - entry_price) * quantity
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            else:  # short
                pnl = (entry_price - exit_price) * quantity
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100
            
            # Create trade summary
            trade_summary = {
                'symbol': self.symbol,
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': quantity,
                'entry_time': self.active_trade['entry_time'],
                'exit_time': datetime.now().isoformat(),
                'exit_reason': exit_reason,
                'pnl': round(pnl, 2),
                'pnl_percent': round(pnl_percent, 2),
                'entry_order_id': self.active_trade.get('order_id'),
                'exit_order_id': exit_order_id
            }
            
            # Reset trade state
            self.active_trade = {
                'is_active': False,
                'direction': None,
                'entry_price': None,
                'entry_time': None,
                'quantity': 0,
                'order_id': None,
                'target_price': None,
                'stop_price': None
            }
            
            # Unlock levels for new detection
            self.levels_locked = False
            self.support_level = None
            self.resistance_level = None
            
            logger.info(f"Trade exited: {exit_reason}, P&L: {pnl:.2f} ({pnl_percent:.2f}%)")
            
            return trade_summary
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current strategy status
        
        Returns:
            Dict[str, Any]: Strategy status
        """
        with self.lock:
            return {
                'symbol': self.symbol,
                'support_level': self.support_level,
                'resistance_level': self.resistance_level,
                'levels_locked': self.levels_locked,
                'active_trade': self.active_trade.copy(),
                'data_points': len(self.price_data),
                'strategy_params': {
                    'lookback_period': self.lookback_period,
                    'profit_target_percent': self.profit_target * 100,
                    'stop_loss_percent': self.stop_loss * 100
                }
            }
    
    def reset_strategy(self) -> None:
        """
        Reset the entire strategy state
        """
        with self.lock:
            self.support_level = None
            self.resistance_level = None
            self.levels_locked = False
            self.active_trade = {
                'is_active': False,
                'direction': None,
                'entry_price': None,
                'entry_time': None,
                'quantity': 0,
                'order_id': None,
                'target_price': None,
                'stop_price': None
            }
            self.price_data = []
            
            logger.info(f"Strategy reset for {self.symbol}")


# Global strategy instances (can be extended to support multiple symbols)
strategy_instances: Dict[str, SupportResistanceStrategy] = {}

def get_strategy(symbol: str, **kwargs) -> SupportResistanceStrategy:
    """
    Get or create strategy instance for a symbol
    
    Args:
        symbol (str): Trading symbol
        **kwargs: Strategy parameters
        
    Returns:
        SupportResistanceStrategy: Strategy instance
    """
    symbol = symbol.upper()
    
    if symbol not in strategy_instances:
        strategy_instances[symbol] = SupportResistanceStrategy(symbol, **kwargs)
        logger.info(f"Created new strategy instance for {symbol}")
    
    return strategy_instances[symbol]

def remove_strategy(symbol: str) -> bool:
    """
    Remove strategy instance for a symbol
    
    Args:
        symbol (str): Trading symbol
        
    Returns:
        bool: True if removed, False if not found
    """
    symbol = symbol.upper()
    
    if symbol in strategy_instances:
        del strategy_instances[symbol]
        logger.info(f"Removed strategy instance for {symbol}")
        return True
    
    return False