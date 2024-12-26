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

## Development Workflow

We follow a test-driven development (TDD) approach. Here's our workflow:

1. Create a feature branch:
```bash
git checkout -b feature/your-feature-name
```

2. Follow the TDD cycle:
   - Write failing tests first
   - Implement the minimal code to make tests pass
   - Refactor while keeping tests green
   - Repeat for next feature/change

3. Before committing:
   - Run all tests: `pytest -v`
   - Update session context if needed
   - Stage changes: `git add .`
   - Create descriptive commit message

4. Push changes and create pull request:
```bash
git push origin feature/your-feature-name
# Create PR on GitHub
```

## Testing

### Directory Structure

```
tests/
├── unit/           # Unit tests for individual components
├── integration/    # Tests for component interactions
└── fixtures/       # Common test data and configurations
```

### Running Tests

Run all tests:
```bash
pytest -v
```

Run specific test categories:
```bash
pytest tests/unit -v                    # Run unit tests
pytest tests/integration -v             # Run integration tests
pytest -v -k "test_exchange"           # Run exchange-related tests
pytest -v -m "websocket"               # Run websocket-marked tests
```

### Writing Tests

1. Follow the test naming convention:
   - Files: `test_{module}.py`
   - Classes: `Test{Component}`
   - Functions: `test_{functionality}`

2. Use appropriate markers:
   - `@pytest.mark.unit`
   - `@pytest.mark.integration`
   - `@pytest.mark.websocket`
   - `@pytest.mark.asyncio` for async tests

3. Structure tests clearly:
   ```python
   def test_something():
       # Arrange
       # Set up test data and conditions
       
       # Act
       # Execute the code being tested
       
       # Assert
       # Verify the results
   ```

4. Use fixtures for common setup:
   ```python
   @pytest.fixture
   def mock_config():
       return BotConfig(...)
   ```

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
