import os
from pydantic import BaseModel, Field
from typing import Optional, Literal
from decimal import Decimal, InvalidOperation


class FeeCoinConfig(BaseModel):
    enabled: bool = Field(alias="manage_fee_coin")
    coin: str = Field(alias="fee_coin")
    repurchase_balance: Decimal = Field(alias="fee_coin_repurchase_balance_USDT", gt=0)
    repurchase_amount: Decimal = Field(alias="fee_coin_repurchase_amount_USDT", gt=0)


class BotConfig(BaseModel):
    name: str
    exchange: str
    api_key: str
    api_secret: str
    pair: str
    coin: str
    investment: Decimal = Field(gt=0)
    grids: int = Field(gt=0)
    gridsize: Decimal = Field(gt=0)
    sandbox_mode: bool
    frontend: bool
    frontend_host: str
    fee_coin: Optional[FeeCoinConfig] = None

    @classmethod
    def from_env(cls):
        pair = os.getenv("GRIDBOT_PAIR", "BTC/USDT")
        coin = pair.split("/")[0]
        # Helper function to safely convert to Decimal
        def safe_decimal(value, default):
            try:
                return Decimal(value) if value is not None else Decimal(default)
            except InvalidOperation:
                return Decimal(default)

        return cls(
            name=os.getenv("GRIDBOT_NAME", "MyGridBot"),
            exchange=os.getenv("GRIDBOT_EXCHANGE", "binance"),
            api_key=os.getenv("GRIDBOT_API_KEY", "my_api_key"),
            api_secret=os.getenv("GRIDBOT_API_SECRET", "my_api_secret"),
            pair=pair,
            coin=coin,
            investment=safe_decimal(os.getenv("GRIDBOT_INVESTMENT"), "1000"),
            grids=int(os.getenv("GRIDBOT_GRIDS", "10")),
            gridsize=safe_decimal(os.getenv("GRIDBOT_GRIDSIZE"), "1.0"),
            sandbox_mode=os.getenv("GRIDBOT_SANDBOX_MODE", "true").lower() == "true",
            frontend=os.getenv("GRIDBOT_FRONTEND", "true").lower() == "true",
            frontend_host=os.getenv("GRIDBOT_FRONTEND_HOST", "localhost:8080"),
            fee_coin=FeeCoinConfig(
                manage_fee_coin=os.getenv("GRIDBOT_MANAGE_FEE_COIN", "true").lower() == "true",
                fee_coin=os.getenv("GRIDBOT_FEE_COIN", "BNB"),
                fee_coin_repurchase_balance_USDT=safe_decimal(os.getenv("GRIDBOT_FEE_COIN_REPURCHASE_BALANCE"), "10"),
                fee_coin_repurchase_amount_USDT=safe_decimal(os.getenv("GRIDBOT_FEE_COIN_REPURCHASE_AMOUNT"), "20")
            )
        )

    @property
    def quote_per_trade(self) -> Decimal:
        """Calculate the quote currency amount per trade."""
        return self.investment / self.grids

    @property
    def grid_size_percent(self) -> Decimal:
        """Convert grid size to percentage."""
        return self.gridsize / 100


class OrderPair(BaseModel):
    """Represents a pair of buy and sell orders."""
    buy_order_id: Optional[str] = None
    sell_order_id: Optional[str] = None
    buy_price: Optional[Decimal] = None
    sell_price: Optional[Decimal] = None
    buy_type: Optional[Literal["limit", "market"]] = None
    amount: Decimal = Field(gt=0)
    timestamp: int = Field(gt=0)
    buy_order_status: Optional[Literal["open", "closed"]] = None

    def to_dict(self):
        return {
            "buy_order_id": self.buy_order_id,
            "sell_order_id": self.sell_order_id,
            "buy_price": str(self.buy_price) if self.buy_price else None,
            "sell_price": str(self.sell_price) if self.sell_price else None,
            "buy_type": self.buy_type,
            "amount": str(self.amount),
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            buy_order_id=data["buy_order_id"],
            sell_order_id=data["sell_order_id"],
            buy_price=Decimal(data["buy_price"]) if data["buy_price"] else None,
            sell_price=Decimal(data["sell_price"]) if data["sell_price"] else None,
            buy_type=data["buy_type"],
            amount=Decimal(data["amount"]),
            timestamp=data["timestamp"]
        )


class Trade(BaseModel):
    """Represents a completed trade."""
    order_id: str
    side: Literal["buy", "sell"]
    symbol: str
    amount: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    cost: Decimal = Field(gt=0)
    timestamp: int = Field(gt=0)
