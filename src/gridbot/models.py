from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal


class FeeCoinConfig(BaseModel):
    enabled: bool = Field(alias="manage_fee_coin")
    coin: str = Field(alias="fee_coin")
    repurchase_balance: Decimal = Field(alias="fee_coin_repurchase_balance_USDT")
    repurchase_amount: Decimal = Field(alias="fee_coin_repurchase_amount_USDT")


class BotConfig(BaseModel):
    name: str
    exchange: str
    api_key: str
    api_secret: str
    pair: str
    investment: Decimal
    grids: int
    gridsize: Decimal
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
    buy_order_id: str
    sell_order_id: Optional[str] = None
    buy_price: Decimal
    sell_price: Optional[Decimal] = None
    amount: Decimal
    timestamp: int


class Trade(BaseModel):
    """Represents a completed trade."""
    order_id: str
    side: str
    price: Decimal
    amount: Decimal
    cost: Decimal
    timestamp: int
    fee: Optional[dict] = None
