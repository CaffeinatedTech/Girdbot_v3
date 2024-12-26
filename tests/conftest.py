import pytest
from decimal import Decimal
from typing import Dict, Any
from gridbot.models import BotConfig, FeeCoinConfig

@pytest.fixture
def mock_config() -> BotConfig:
    """Provides a basic bot configuration for testing."""
    fee_coin_config = FeeCoinConfig(
        manage_fee_coin=True,
        fee_coin="BNB",
        fee_coin_repurchase_balance_USDT=Decimal("10"),
        fee_coin_repurchase_amount_USDT=Decimal("20")
    )
    
    return BotConfig(
        name="TestBot",
        exchange="binance",
        api_key="test_key",
        api_secret="test_secret",
        pair="BTC/USDT",
        investment=Decimal("1000"),
        grids=10,
        gridsize=Decimal("1.0"),
        sandbox_mode=True,
        frontend=False,
        frontend_host="localhost:8080",
        fee_coin=fee_coin_config
    )

@pytest.fixture
def mock_market_data() -> Dict[str, Any]:
    """Provides mock market data for testing."""
    return {
        "symbol": "BTC/USDT",
        "timestamp": 1640995200000,  # 2022-01-01 00:00:00
        "datetime": "2022-01-01T00:00:00.000Z",
        "high": 47000.0,
        "low": 45000.0,
        "bid": 46000.0,
        "bidVolume": 1.5,
        "ask": 46100.0,
        "askVolume": 2.1,
        "vwap": 46050.0,
        "open": 46500.0,
        "close": 46000.0,
        "last": 46000.0,
        "previousClose": 46500.0,
        "change": -500.0,
        "percentage": -1.075,
        "average": 46250.0,
        "baseVolume": 100.0,
        "quoteVolume": 4605000.0,
    }

@pytest.fixture
def mock_order() -> Dict[str, Any]:
    """Provides mock order data for testing."""
    return {
        "id": "123456789",
        "clientOrderId": "test_order_1",
        "datetime": "2022-01-01T00:00:00.000Z",
        "timestamp": 1640995200000,
        "status": "closed",
        "symbol": "BTC/USDT",
        "type": "limit",
        "timeInForce": "GTC",
        "side": "buy",
        "price": 46000.0,
        "amount": 0.1,
        "filled": 0.1,
        "remaining": 0.0,
        "cost": 4600.0,
        "trades": [],
        "fee": {
            "cost": 0.001,
            "currency": "BNB"
        }
    }
