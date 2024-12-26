import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
from gridbot.strategy import GridStrategy
from gridbot.models import Trade, OrderPair


@pytest.fixture
def mock_exchange():
    """Create a mock exchange interface."""
    mock = AsyncMock()
    mock.current_price = Decimal("45000")
    mock.fetch_ticker = AsyncMock(return_value={'last': Decimal("45000")})
    
    # Mock market buy order
    mock.create_market_buy_order = AsyncMock()
    mock.create_market_buy_order.return_value = {
        'id': 'market_buy_1',
        'price': Decimal("45000"),
        'amount': Decimal("0.1"),
        'timestamp': 1640995200000
    }
    
    # Mock limit buy order
    mock.create_limit_buy_order = AsyncMock()
    mock.create_limit_buy_order.return_value = {
        'id': 'limit_buy_1',
        'price': Decimal("44000"),
        'amount': Decimal("0.1"),
        'timestamp': 1640995200000
    }
    
    # Mock limit sell order
    mock.create_limit_sell_order = AsyncMock()
    mock.create_limit_sell_order.return_value = {
        'id': 'limit_sell_1',
        'price': Decimal("46000"),
        'amount': Decimal("0.1"),
        'timestamp': 1640995200000
    }
    
    # Mock market sell order
    mock.create_market_sell_order = AsyncMock()
    mock.create_market_sell_order.return_value = {
        'id': 'market_sell_1',
        'price': Decimal("45000"),
        'amount': Decimal("0.1"),
        'timestamp': 1640995200000
    }
    
    # Mock other methods
    mock.fetch_open_orders = AsyncMock(return_value=[
        {
            'id': 'buy_1',
            'side': 'buy',
            'price': Decimal("44000"),
            'amount': Decimal("0.1")
        }
    ])
    mock.fetch_balance = AsyncMock(return_value={
        'free': {'BTC': Decimal("0.1"), 'USDT': Decimal("5000")}
    })
    mock.cancel_order = AsyncMock()
    
    return mock


@pytest.mark.unit
class TestGridStrategy:
    def test_calculate_grid_size(self, mock_config, mock_exchange):
        """Test grid size calculation."""
        strategy = GridStrategy(mock_config, mock_exchange)
        grid_size = strategy.calculate_grid_size(Decimal("45000"))
        
        # Grid size should be current_price * (gridsize / 100)
        expected_size = Decimal("45000") * Decimal("0.01")  # 1% grid size
        assert grid_size == expected_size

    @pytest.mark.asyncio
    async def test_initialize_grid(self, mock_config, mock_exchange):
        """Test grid initialization."""
        strategy = GridStrategy(mock_config, mock_exchange)
        await strategy.initialize_grid()

        # Verify initial market buy
        mock_exchange.create_market_buy_order.assert_called_once()
        
        # Verify initial sell order
        mock_exchange.create_limit_sell_order.assert_called_once()
        
        # Verify grid of buy orders
        assert mock_exchange.create_limit_buy_order.call_count == mock_config.grids - 1

        # Verify order tracking
        assert len(strategy.order_pairs) == mock_config.grids
        for pair in strategy.order_pairs:
            assert pair.buy_order_id is not None
            assert pair.amount > Decimal("0")
            assert pair.timestamp == 1640995200000

    @pytest.mark.asyncio
    async def test_fresh_start(self, mock_config, mock_exchange):
        """Test fresh start functionality."""
        # Set up some existing orders
        mock_exchange.fetch_open_orders.return_value = [
            {'id': 'existing_1'},
            {'id': 'existing_2'}
        ]

        strategy = GridStrategy(mock_config, mock_exchange)
        await strategy.initialize_grid(fresh_start=True)

        # Verify existing orders were cancelled
        assert mock_exchange.cancel_order.call_count == 2
        
        # Verify existing position was sold
        mock_exchange.create_market_sell_order.assert_called_once_with(Decimal("0.1"))

    @pytest.mark.asyncio
    async def test_handle_filled_buy_order(self, mock_config, mock_exchange):
        """Test handling of filled buy orders."""
        strategy = GridStrategy(mock_config, mock_exchange)
        strategy.grid_size = Decimal("450")  # 1% of 45000
        
        # Create a filled buy trade
        trade = Trade(
            order_id="buy_1",
            side="buy",
            symbol="BTC/USDT",
            amount=Decimal("0.1"),
            price=Decimal("45000"),
            cost=Decimal("4500"),
            fee_cost=Decimal("4.5"),
            fee_currency="USDT",
            timestamp=1640995200000
        )
        
        await strategy.handle_filled_order(trade)
        
        # Verify sell order placement
        mock_exchange.create_limit_sell_order.assert_called_once()
        call_args = mock_exchange.create_limit_sell_order.call_args[0]
        assert call_args[0] == Decimal("0.1")  # amount
        assert call_args[1] == Decimal("45450")  # price + grid_size
        
        # Verify new buy order placement
        mock_exchange.create_limit_buy_order.assert_called_once()
        call_args = mock_exchange.create_limit_buy_order.call_args[0]
        assert call_args[1] == Decimal("44550")  # price - grid_size

    @pytest.mark.asyncio
    async def test_handle_filled_sell_order(self, mock_config, mock_exchange):
        """Test handling of filled sell orders."""
        strategy = GridStrategy(mock_config, mock_exchange)
        
        # Add an order pair to track
        pair = OrderPair(
            buy_order_id="buy_1",
            sell_order_id="sell_1",
            buy_price=Decimal("45000"),
            sell_price=Decimal("45450"),
            amount=Decimal("0.1"),
            timestamp=1640995200000
        )
        strategy.order_pairs.append(pair)
        
        # Create a filled sell trade
        trade = Trade(
            order_id="sell_1",
            side="sell",
            symbol="BTC/USDT",
            amount=Decimal("0.1"),
            price=Decimal("45450"),
            cost=Decimal("4545"),
            fee_cost=Decimal("4.5"),
            fee_currency="USDT",
            timestamp=1640995200000
        )
        
        await strategy.handle_filled_order(trade)
        
        # Verify order pair was moved to completed trades
        assert len(strategy.completed_trades) == 1
        assert len(strategy.order_pairs) == 0
        assert strategy.completed_trades[0] == trade

    @pytest.mark.asyncio
    async def test_check_order_health(self, mock_config, mock_exchange):
        """Test order health check and recreation."""
        strategy = GridStrategy(mock_config, mock_exchange)
        strategy.grid_size = Decimal("450")  # 1% of 45000

        # Simulate missing orders
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'buy_1',
                'side': 'buy',
                'price': Decimal("44000"),
                'amount': Decimal("0.1")
            }
        ]
        
        await strategy.check_order_health()
        
        # Should create missing sell order
        mock_exchange.create_limit_sell_order.assert_called_once()
        
        # Should create missing buy orders
        expected_buy_orders = mock_config.grids - 1  # -1 for existing buy order
        assert mock_exchange.create_limit_buy_order.call_count == expected_buy_orders
