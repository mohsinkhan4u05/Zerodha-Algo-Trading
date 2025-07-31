# Zerodha Support & Resistance Breakout Strategy

A complete Python-based algorithmic trading system for Zerodha Kite Connect API that implements Support and Resistance breakout strategy with automated profit/loss exits.

## Features

- **Support & Resistance Detection**: Automatically detects support and resistance levels using swing highs/lows
- **Breakout Trading**: Enters long positions on resistance breakouts and short positions on support breakouts
- **Automated Exit Management**: 3% profit target and 1% stop loss with real-time LTP monitoring
- **Level Locking**: S/R levels are locked during active trades and reset only after trade completion
- **Real-time Monitoring**: Background thread monitors LTP and executes exit orders automatically
- **Multiple Symbol Support**: Handle multiple symbols simultaneously with separate strategy instances
- **REST API**: Complete Flask-based REST API for integration with external systems
- **TradingView Integration**: Webhook endpoint for receiving TradingView alerts

## Project Structure

```
├── main.py              # Flask application with all endpoints
├── s_r_strategy.py      # Support & Resistance strategy implementation
├── kite_utils.py        # Kite Connect API utilities
├── config.json          # Configuration file for API keys
├── requirements.txt     # Python dependencies
├── app.py              # Legacy Flask app (use main.py instead)
└── README.md           # This file
```

## Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API credentials**:
   - Edit `config.json` and add your Zerodha API credentials:
   ```json
   {
       "api_key": "your_actual_api_key",
       "api_secret": "your_actual_api_secret",
       "request_token": null,
       "access_token": null
   }
   ```

4. **Generate access token**:
   - Get request token from Zerodha Kite Connect login flow
   - Use the `/generate_token` endpoint to generate access token

## Usage

### 1. Start the Server

```bash
python main.py
```

The server will start on `http://localhost:5000`

### 2. Generate Access Token

First, obtain a request token from Zerodha Kite Connect, then:

```bash
curl -X POST http://localhost:5000/generate_token \
  -H "Content-Type: application/json" \
  -d '{"request_token": "your_request_token_here"}'
```

### 3. Send Price Data

Send OHLC data to build support/resistance levels and trigger breakout signals:

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "RELIANCE",
    "high": 2500.0,
    "low": 2480.0,
    "close": 2495.0,
    "quantity": 1
  }'
```

### 4. Monitor Strategy Status

Check the current strategy status for a symbol:

```bash
curl http://localhost:5000/strategy/RELIANCE
```

## API Endpoints

### Core Endpoints

- `GET /` - Health check
- `POST /generate_token` - Generate access token from request token
- `POST /webhook` - Receive price data or manual trading signals

### Strategy Management

- `GET /strategy/<symbol>` - Get strategy status for a symbol
- `POST /strategy/<symbol>/reset` - Reset strategy for a symbol
- `POST /strategy/<symbol>/exit` - Manually exit active trade

### Market Data

- `GET /ltp/<symbol>` - Get Last Traded Price
- `GET /ohlc/<symbol>` - Get OHLC data
- `GET /positions` - Get current positions
- `GET /orders` - Get all orders

### Monitoring

- `GET /monitoring` - Get monitoring status
- `POST /monitoring/start` - Start LTP monitoring
- `POST /monitoring/stop` - Stop LTP monitoring

## Strategy Logic

### Support & Resistance Detection

1. **Swing High/Low Identification**: Uses 10-candle lookback to identify swing highs and lows
2. **Level Calculation**: 
   - Support = Minimum of swing lows
   - Resistance = Maximum of swing highs
3. **Level Validation**: Ensures support < resistance before setting levels

### Entry Conditions

- **Long Entry**: Price closes above resistance level
- **Short Entry**: Price closes below support level
- **One Trade Rule**: Only one trade per breakout (levels locked during active trade)

### Exit Conditions

- **Profit Target**: 3% profit from entry price
- **Stop Loss**: 1% loss from entry price
- **Real-time Monitoring**: Background thread checks LTP every 2 seconds

### Level Management

- **Lock on Entry**: S/R levels are locked when a trade is entered
- **Reset on Exit**: Levels are cleared and detection restarts after trade completion
- **Fresh Detection**: New levels are calculated from fresh price data after reset

## Example Usage Scenarios

### 1. TradingView Integration

Set up TradingView alerts to send webhook data:

```javascript
// TradingView Alert Message
{
  "symbol": "{{ticker}}",
  "high": {{high}},
  "low": {{low}},
  "close": {{close}},
  "quantity": 1
}
```

### 2. Manual Trading

Send manual buy/sell signals:

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "RELIANCE",
    "action": "buy",
    "quantity": 10
  }'
```

### 3. Strategy Monitoring

Monitor all active strategies:

```bash
# Check monitoring status
curl http://localhost:5000/monitoring

# Get strategy status
curl http://localhost:5000/strategy/RELIANCE

# Manual exit if needed
curl -X POST http://localhost:5000/strategy/RELIANCE/exit
```

## Configuration Parameters

The strategy can be customized by modifying the parameters in `s_r_strategy.py`:

```python
strategy = SupportResistanceStrategy(
    symbol="RELIANCE",
    lookback_period=10,      # Candles for S/R detection
    profit_target=0.03,      # 3% profit target
    stop_loss=0.01          # 1% stop loss
)
```

## Error Handling

- **API Errors**: All Kite Connect API errors are caught and logged
- **Strategy Errors**: Invalid price data or strategy states are handled gracefully
- **Network Errors**: Retry logic for critical operations
- **Monitoring Errors**: Continuous monitoring with error recovery

## Logging

All operations are logged with appropriate levels:
- **INFO**: Normal operations, trade entries/exits
- **WARNING**: Configuration issues, invalid data
- **ERROR**: API failures, critical errors

## Security Notes

1. **API Credentials**: Keep your `config.json` file secure and never commit it to version control
2. **Access Tokens**: Tokens are displayed partially in API responses for security
3. **Network Security**: Consider using HTTPS in production environments
4. **Rate Limits**: Respect Zerodha API rate limits (3 requests per second)

## Troubleshooting

### Common Issues

1. **"Access token required"**: Generate access token using `/generate_token` endpoint
2. **"Insufficient data points"**: Send at least 12 price data points before expecting S/R levels
3. **"Invalid levels"**: Ensure your price data has proper high/low/close values
4. **"Order placement failed"**: Check your Zerodha account balance and trading permissions

### Debug Mode

Enable debug logging by modifying the logging level in the Python files:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Production Deployment

For production use:

1. **Use WSGI Server**: Deploy with Gunicorn or uWSGI instead of Flask dev server
2. **Environment Variables**: Store sensitive data in environment variables
3. **Database**: Consider using Redis or database for strategy state persistence
4. **Monitoring**: Set up proper application monitoring and alerting
5. **SSL/TLS**: Use HTTPS for all API communications

## License

This project is for educational purposes. Please ensure compliance with your broker's terms of service and local regulations when using for live trading.

## Disclaimer

This software is provided for educational purposes only. Trading in financial markets involves substantial risk of loss. The authors are not responsible for any trading losses incurred through the use of this software. Always test thoroughly with paper trading before using real money.