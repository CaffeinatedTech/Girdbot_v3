# GridBot v3

A cryptocurrency grid trading bot built with Python and CCXT Pro.

## Features

- Grid trading strategy with configurable parameters
- Real-time trade monitoring and execution
- WebSocket-based status updates
- Comprehensive profit tracking
- Automatic fee coin management
- Configuration via JSON files
- Error handling and recovery
- Detailed logging

## Project Structure

```
gridbot_v3/
├── config/
│   └── config.example.json
├── src/
│   └── gridbot/
│       ├── __init__.py
│       ├── bot.py           # Main bot class
│       ├── config.py        # Configuration management
│       ├── exchange.py      # Exchange interface
│       ├── models.py        # Data models
│       ├── strategy.py      # Trading strategy
│       └── websocket.py     # WebSocket communication
├── tests/
├── requirements.txt
└── README.md
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `config/config.example.json` to `config/config.json` and update with your settings

## Configuration

Create a JSON configuration file with the following structure:

```json
{
    "name": "MyGridBot",
    "exchange": "binance",
    "api_key": "your-api-key",
    "api_secret": "your-api-secret",
    "pair": "BTC/USDT",
    "investment": 1000,
    "grids": 10,
    "gridsize": 1.0,
    "sandbox_mode": true,
    "frontend": true,
    "frontend_host": "localhost:8080",
    "manage_fee_coin": true,
    "fee_coin": "BNB",
    "fee_coin_repurchase_balance_USDT": 10,
    "fee_coin_repurchase_amount_USDT": 20
}
```

## Usage

Run the bot with:

```bash
python -m gridbot.bot --config config/config.json [--fresh]
```

Options:
- `--config`: Path to configuration file (required)
- `--fresh`: Start fresh by closing current position and canceling all orders

## Development

The codebase follows these principles:
- Clear separation of concerns
- Type hints and data validation
- Comprehensive error handling
- Asynchronous operations
- Unit testing
- Clean code practices
