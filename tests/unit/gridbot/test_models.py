import pytest
from decimal import Decimal
from pydantic import ValidationError
from gridbot.models import BotConfig, FeeCoinConfig, OrderPair, Trade


@pytest.mark.unit
class TestFeeCoinConfig:
    def test_valid_fee_coin_config(self):
        """Test creating a valid fee coin configuration."""
        config = FeeCoinConfig(
            manage_fee_coin=True,
            fee_coin="BNB",
            fee_coin_repurchase_balance_USDT=Decimal("10"),
            fee_coin_repurchase_amount_USDT=Decimal("20")
        )
        assert config.enabled is True
        assert config.coin == "BNB"
        assert config.repurchase_balance == Decimal("10")
        assert config.repurchase_amount == Decimal("20")

    def test_invalid_repurchase_amounts(self):
        """Test validation of negative repurchase amounts."""
        with pytest.raises(ValidationError) as exc_info:
            FeeCoinConfig(
                manage_fee_coin=True,
                fee_coin="BNB",
                fee_coin_repurchase_balance_USDT=Decimal("-10"),
                fee_coin_repurchase_amount_USDT=Decimal("20")
            )
        assert "repurchase_balance" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            FeeCoinConfig(
                manage_fee_coin=True,
                fee_coin="BNB",
                fee_coin_repurchase_balance_USDT=Decimal("10"),
                fee_coin_repurchase_amount_USDT=Decimal("-20")
            )
        assert "repurchase_amount" in str(exc_info.value)


@pytest.mark.unit
class TestBotConfig:
    def test_valid_bot_config(self, mock_config):
        """Test creating a valid bot configuration."""
        assert mock_config.name == "TestBot"
        assert mock_config.exchange == "binance"
        assert mock_config.pair == "BTC/USDT"
        assert mock_config.investment == Decimal("1000")
        assert mock_config.grids == 10
        assert mock_config.gridsize == Decimal("1.0")
        assert mock_config.sandbox_mode is True
        assert mock_config.frontend is False
        assert mock_config.frontend_host == "localhost:8080"
        assert mock_config.fee_coin is not None
        assert mock_config.fee_coin.coin == "BNB"

    def test_quote_per_trade_calculation(self):
        """Test the quote_per_trade property calculation."""
        config = BotConfig(
            name="TestBot",
            exchange="binance",
            api_key="test_key",
            api_secret="test_secret",
            pair="BTC/USDT",
            investment=Decimal("1000"),
            grids=5,
            gridsize=Decimal("1.0"),
            sandbox_mode=True,
            frontend=False,
            frontend_host="localhost:8080"
        )
        assert config.quote_per_trade == Decimal("200")  # 1000 / 5

    def test_grid_size_percent_calculation(self):
        """Test the grid_size_percent property calculation."""
        config = BotConfig(
            name="TestBot",
            exchange="binance",
            api_key="test_key",
            api_secret="test_secret",
            pair="BTC/USDT",
            investment=Decimal("1000"),
            grids=10,
            gridsize=Decimal("2.5"),
            sandbox_mode=True,
            frontend=False,
            frontend_host="localhost:8080"
        )
        assert config.grid_size_percent == Decimal("0.025")  # 2.5 / 100

    def test_invalid_investment_amount(self):
        """Test validation of negative investment amount."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                name="TestBot",
                exchange="binance",
                api_key="test_key",
                api_secret="test_secret",
                pair="BTC/USDT",
                investment=Decimal("-1000"),
                grids=10,
                gridsize=Decimal("1.0"),
                sandbox_mode=True,
                frontend=False,
                frontend_host="localhost:8080"
            )
        assert "investment" in str(exc_info.value)

    def test_invalid_grid_count(self):
        """Test validation of invalid grid count."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                name="TestBot",
                exchange="binance",
                api_key="test_key",
                api_secret="test_secret",
                pair="BTC/USDT",
                investment=Decimal("1000"),
                grids=0,
                gridsize=Decimal("1.0"),
                sandbox_mode=True,
                frontend=False,
                frontend_host="localhost:8080"
            )
        assert "grids" in str(exc_info.value)


@pytest.mark.unit
class TestOrderPair:
    def test_valid_order_pair(self):
        """Test creating a valid order pair."""
        order_pair = OrderPair(
            buy_order_id="123",
            sell_order_id="456",
            buy_price=Decimal("45000"),
            sell_price=Decimal("46000"),
            amount=Decimal("0.1"),
            timestamp=1640995200000
        )
        assert order_pair.buy_order_id == "123"
        assert order_pair.sell_order_id == "456"
        assert order_pair.buy_price == Decimal("45000")
        assert order_pair.sell_price == Decimal("46000")
        assert order_pair.amount == Decimal("0.1")
        assert order_pair.timestamp == 1640995200000

    def test_optional_sell_fields(self):
        """Test creating an order pair without sell information."""
        order_pair = OrderPair(
            buy_order_id="123",
            buy_price=Decimal("45000"),
            amount=Decimal("0.1"),
            timestamp=1640995200000
        )
        assert order_pair.sell_order_id is None
        assert order_pair.sell_price is None


@pytest.mark.unit
class TestTrade:
    def test_valid_trade(self):
        """Test creating a valid trade."""
        trade = Trade(
            order_id="123",
            side="buy",
            symbol="BTC/USDT",
            amount=Decimal("0.1"),
            price=Decimal("45000"),
            cost=Decimal("4500"),
            timestamp=1640995200000
        )
        assert trade.order_id == "123"
        assert trade.side == "buy"
        assert trade.symbol == "BTC/USDT"
        assert trade.amount == Decimal("0.1")
        assert trade.price == Decimal("45000")
        assert trade.cost == Decimal("4500")
        assert trade.timestamp == 1640995200000

    def test_invalid_trade_side(self):
        """Test validation of invalid trade side."""
        with pytest.raises(ValidationError) as exc_info:
            Trade(
                order_id="123",
                side="invalid",
                symbol="BTC/USDT",
                amount=Decimal("0.1"),
                price=Decimal("45000"),
                cost=Decimal("4500"),
                timestamp=1640995200000
            )
        assert "side" in str(exc_info.value)
