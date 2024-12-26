from decimal import Decimal
import ccxt.pro as ccxtpro
from typing import Optional, List, Dict, Any
from .models import BotConfig, Trade

class ExchangeInterface:
    def __init__(self, config: BotConfig):
        self.config = config
        self.exchange = self._initialize_exchange()
        self.markets = {}
        self.current_price: Optional[Decimal] = None

    def _initialize_exchange(self) -> ccxtpro.Exchange:
        """Initialize the exchange with configuration settings."""
        exchange_class = getattr(ccxtpro, self.config.exchange)
        exchange = exchange_class({
            'apiKey': self.config.api_key,
            'secret': self.config.api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        if self.config.sandbox_mode:
            exchange.set_sandbox_mode(True)
        
        return exchange

    async def initialize(self):
        """Load markets and other initialization tasks."""
        self.markets = await self.exchange.load_markets()

    async def fetch_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Fetch current ticker information."""
        symbol = symbol or self.config.pair
        ticker = await self.exchange.fetch_ticker(symbol)
        self.current_price = Decimal(str(ticker['last']))
        return ticker

    async def create_limit_buy_order(self, amount: Decimal, price: Decimal) -> Dict[str, Any]:
        """Create a limit buy order."""
        return await self.exchange.create_limit_buy_order(
            self.config.pair,
            float(amount),
            float(price)
        )

    async def create_limit_sell_order(self, amount: Decimal, price: Decimal) -> Dict[str, Any]:
        """Create a limit sell order."""
        return await self.exchange.create_limit_sell_order(
            self.config.pair,
            float(amount),
            float(price)
        )

    async def create_market_buy_order(self, amount: Decimal) -> Dict[str, Any]:
        """Create a market buy order."""
        return await self.exchange.create_market_buy_order(
            self.config.pair,
            float(amount)
        )

    async def create_market_sell_order(self, amount: Decimal) -> Dict[str, Any]:
        """Create a market sell order."""
        return await self.exchange.create_market_sell_order(
            self.config.pair,
            float(amount)
        )

    async def fetch_open_orders(self) -> List[Dict[str, Any]]:
        """Fetch all open orders."""
        return await self.exchange.fetch_open_orders(self.config.pair)

    async def fetch_order(self, order_id: str) -> Dict[str, Any]:
        """Fetch a specific order by ID."""
        return await self.exchange.fetch_order(order_id, self.config.pair)

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel a specific order by ID."""
        return await self.exchange.cancel_order(order_id, self.config.pair)

    async def fetch_balance(self) -> Dict[str, Any]:
        """Fetch account balance."""
        return await self.exchange.fetch_balance()

    async def watch_trades(self) -> Trade:
        """Watch for new trades."""
        while True:
            trade = await self.exchange.watch_trades(self.config.pair)
            if trade:
                return Trade(
                    order_id=trade['id'],
                    side=trade['side'],
                    price=Decimal(str(trade['price'])),
                    amount=Decimal(str(trade['amount'])),
                    cost=Decimal(str(trade['cost'])),
                    timestamp=trade['timestamp'],
                    fee=trade.get('fee')
                )

    async def close(self):
        """Close exchange connection."""
        await self.exchange.close()
