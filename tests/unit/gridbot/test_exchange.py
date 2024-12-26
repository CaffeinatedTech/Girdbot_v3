import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from gridbot.exchange import ExchangeInterface

@pytest.mark.unit
@pytest.mark.exchange
class TestExchangeInterface:
    @pytest.mark.asyncio
    async def test_initialize_exchange(self, mock_config):
        """Test exchange initialization with config."""
        exchange = ExchangeInterface(mock_config)
        assert exchange.config == mock_config
        assert exchange.config.sandbox_mode is True
        assert exchange.current_price is None

    @pytest.mark.asyncio
    async def test_fetch_ticker(self, mock_config, mock_market_data):
        """Test fetching ticker data."""
        exchange = ExchangeInterface(mock_config)
        exchange.exchange.fetch_ticker = AsyncMock(return_value=mock_market_data)
        
        ticker = await exchange.fetch_ticker()
        
        assert ticker == mock_market_data
        assert exchange.current_price == Decimal(str(mock_market_data['last']))
        exchange.exchange.fetch_ticker.assert_called_once_with(mock_config.pair)

    @pytest.mark.asyncio
    async def test_create_limit_buy_order(self, mock_config, mock_order):
        """Test creating a limit buy order."""
        exchange = ExchangeInterface(mock_config)
        exchange.exchange.create_limit_buy_order = AsyncMock(return_value=mock_order)
        
        amount = Decimal("0.1")
        price = Decimal("46000.0")
        
        order = await exchange.create_limit_buy_order(amount, price)
        
        assert order == mock_order
        exchange.exchange.create_limit_buy_order.assert_called_once_with(
            mock_config.pair,
            float(amount),
            float(price)
        )

    @pytest.mark.asyncio
    async def test_create_limit_sell_order(self, mock_config, mock_order):
        """Test creating a limit sell order."""
        exchange = ExchangeInterface(mock_config)
        mock_order['side'] = 'sell'
        exchange.exchange.create_limit_sell_order = AsyncMock(return_value=mock_order)
        
        amount = Decimal("0.1")
        price = Decimal("46000.0")
        
        order = await exchange.create_limit_sell_order(amount, price)
        
        assert order == mock_order
        assert order['side'] == 'sell'
        exchange.exchange.create_limit_sell_order.assert_called_once_with(
            mock_config.pair,
            float(amount),
            float(price)
        )
