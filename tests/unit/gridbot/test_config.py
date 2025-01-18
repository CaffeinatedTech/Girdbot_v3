import pytest
from decimal import Decimal
import os
from gridbot.models import BotConfig, FeeCoinConfig

class TestBotConfigFromEnv:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        # Save original environment
        self.original_env = os.environ.copy()
        yield
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_default_values(self):
        config = BotConfig.from_env()
        assert config.name == "MyGridBot"
        assert config.exchange == "binance"
        assert config.pair == "BTC/USDT"
        assert config.investment == Decimal("1000")
        assert config.grids == 10
        assert config.gridsize == Decimal("1.0")
        assert config.sandbox_mode == True
        assert config.frontend == True
        assert config.frontend_host == "localhost:8080"
        assert config.fee_coin.enabled == True
        assert config.fee_coin.coin == "BNB"
        assert config.fee_coin.repurchase_balance == Decimal("10")
        assert config.fee_coin.repurchase_amount == Decimal("20")

    def test_custom_values(self):
        os.environ.update({
            "GRIDBOT_NAME": "CustomBot",
            "GRIDBOT_EXCHANGE": "kraken",
            "GRIDBOT_API_KEY": "custom_api_key",
            "GRIDBOT_API_SECRET": "custom_api_secret",
            "GRIDBOT_PAIR": "ETH/USD",
            "GRIDBOT_INVESTMENT": "2000",
            "GRIDBOT_GRIDS": "20",
            "GRIDBOT_GRIDSIZE": "0.5",
            "GRIDBOT_SANDBOX_MODE": "false",
            "GRIDBOT_FRONTEND": "false",
            "GRIDBOT_FRONTEND_HOST": "custom:8080",
            "GRIDBOT_MANAGE_FEE_COIN": "false",
            "GRIDBOT_FEE_COIN": "ETH",
            "GRIDBOT_FEE_COIN_REPURCHASE_BALANCE": "15",
            "GRIDBOT_FEE_COIN_REPURCHASE_AMOUNT": "25"
        })
        config = BotConfig.from_env()
        assert config.name == "CustomBot"
        assert config.exchange == "kraken"
        assert config.api_key == "custom_api_key"
        assert config.api_secret == "custom_api_secret"
        assert config.pair == "ETH/USD"
        assert config.coin == "ETH"
        assert config.investment == Decimal("2000")
        assert config.grids == 20
        assert config.gridsize == Decimal("0.5")
        assert config.sandbox_mode == False
        assert config.frontend == False
        assert config.frontend_host == "custom:8080"
        assert config.fee_coin.enabled == False
        assert config.fee_coin.coin == "ETH"
        assert config.fee_coin.repurchase_balance == Decimal("15")
        assert config.fee_coin.repurchase_amount == Decimal("25")

    def test_partial_env_vars(self):
        os.environ.update({
            "GRIDBOT_NAME": "PartialBot",
            "GRIDBOT_INVESTMENT": "3000",
        })
        config = BotConfig.from_env()
        assert config.name == "PartialBot"
        assert config.investment == Decimal("3000")
        # Other values should be default
        assert config.exchange == "binance"
        assert config.grids == 10

    def test_invalid_values(self):
        os.environ.update({
            "GRIDBOT_GRIDS": "-5",
        })
        with pytest.raises(ValueError):
            BotConfig.from_env()

    def test_invalid_decimal_values(self):
        os.environ.update({
            "GRIDBOT_INVESTMENT": "invalid",
            "GRIDBOT_GRIDSIZE": "not_a_number",
            "GRIDBOT_FEE_COIN_REPURCHASE_BALANCE": "also_invalid",
            "GRIDBOT_FEE_COIN_REPURCHASE_AMOUNT": "still_invalid"
        })
        config = BotConfig.from_env()
        assert config.investment == Decimal("1000")  # default value
        assert config.gridsize == Decimal("1.0")  # default value
        assert config.fee_coin.repurchase_balance == Decimal("10")  # default value
        assert config.fee_coin.repurchase_amount == Decimal("20")  # default value
