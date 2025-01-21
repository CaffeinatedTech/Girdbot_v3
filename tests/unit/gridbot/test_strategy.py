import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
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
        expected_size = (Decimal("45000") * mock_config.gridsize) / Decimal("100")  # 1% grid size
        assert grid_size == expected_size

    @pytest.mark.asyncio
    @patch('gridbot.strategy.time.time')
    async def test_initialize_grid(self, mock_time, mock_config, mock_exchange):
        """Test grid initialization."""
        mock_time.return_value = 1640995200  # This will give us 1640995200000 when multiplied by 1000

        strategy = GridStrategy(mock_config, mock_exchange)
        await strategy.initialize_grid(fresh_start=True)

        # Verify initial market buy
        mock_exchange.create_market_buy_order.assert_called_once()

        # Verify sell order was created
        assert mock_exchange.create_limit_sell_order.call_count == 1
        first_call_args = mock_exchange.create_limit_sell_order.call_args_list[0][0]
        assert isinstance(first_call_args[0], Decimal)  # amount
        assert isinstance(first_call_args[1], Decimal)  # price

        # Verify grid of buy orders
        assert mock_exchange.create_limit_buy_order.call_count == mock_config.grids - 1

        # Verify order tracking
        assert len(strategy.order_pairs) == mock_config.grids
        for pair in strategy.order_pairs:
            if pair.buy_order_id == 'market_buy_1':  # Initial market buy
                assert pair.sell_order_id is not None
                assert pair.buy_price == Decimal("45000")
            else:  # Limit buy orders
                assert pair.buy_order_id is not None
                assert pair.buy_price < Decimal("45000")
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
        mock_exchange.cancel_order.assert_any_call('existing_1')
        mock_exchange.cancel_order.assert_any_call('existing_2')

        # Verify grid was initialized with new orders
        assert mock_exchange.create_market_buy_order.call_count == 1
        assert mock_exchange.create_limit_sell_order.call_count == 1
        assert mock_exchange.create_limit_buy_order.call_count == mock_config.grids - 1

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
        assert call_args[0] == trade.amount  # amount
        assert call_args[1] == Decimal("45450")  # price = price + grid_size

        # Verify order pair tracking
        assert len(strategy.order_pairs) == 1
        pair = strategy.order_pairs[0]
        assert pair.buy_order_id == "buy_1"
        assert pair.buy_price == Decimal("45000")
        assert pair.sell_order_id == "limit_sell_1"
        assert pair.sell_price == Decimal("46000")
        assert pair.amount == Decimal("0.1")

    @pytest.mark.asyncio
    async def test_handle_filled_sell_order(self, mock_config, mock_exchange):
        """Test handling of filled sell orders."""
        strategy = GridStrategy(mock_config, mock_exchange)
        strategy.grid_size = Decimal("450")  # 1% of 45000

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
        assert len(strategy.order_pairs) == 1  # New buy order pair created
        completed_pair = strategy.completed_trades[0]
        assert completed_pair.buy_order_id == "buy_1"
        assert completed_pair.sell_order_id == "sell_1"
        assert completed_pair.buy_price == Decimal("45000")
        assert completed_pair.sell_price == Decimal("45450")

        # Verify new buy order was placed
        mock_exchange.create_limit_buy_order.assert_called_once()
        call_args = mock_exchange.create_limit_buy_order.call_args[0]
        assert call_args[0] == trade.amount  # amount
        assert call_args[1] == Decimal("45000")  # price = original buy price

