from pydantic import BaseModel, Field
from typing import Optional, Literal
from decimal import Decimal


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
