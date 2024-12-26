from decimal import Decimal
from typing import List, Optional, Dict
from .models import BotConfig, OrderPair, Trade
from .exchange import ExchangeInterface


class GridStrategy:
    def __init__(self, config: BotConfig, exchange: ExchangeInterface):
        self.config = config
        self.exchange = exchange
        self.order_pairs: List[OrderPair] = []
        self.completed_trades: List[Trade] = []
        self.grid_size: Optional[Decimal] = None

    def calculate_grid_size(self, current_price: Decimal) -> Decimal:
        """Calculate the grid size in quote currency."""
        return current_price * self.config.grid_size_percent

    async def initialize_grid(self, fresh_start: bool = False):
        """Initialize the grid trading strategy."""
        if fresh_start:
            await self._perform_fresh_start()
        
        # Calculate grid size based on current price
        ticker = await self.exchange.fetch_ticker()
        current_price = Decimal(str(ticker['last']))
        self.grid_size = self.calculate_grid_size(current_price)

        # Place initial market buy order
        amount = self.config.quote_per_trade / current_price
        market_order = await self.exchange.create_market_buy_order(amount)
        print(f"Initial market buy: Amount {amount}, Price {market_order['price']}")

        # Track the market order
        self.order_pairs.append(OrderPair(
            buy_order_id=market_order['id'],
            buy_price=Decimal(str(market_order['price'])),
            amount=Decimal(str(market_order['amount'])),
            timestamp=market_order['timestamp']
        ))

        # Place initial sell order
        sell_price = current_price + self.grid_size
        await self._place_sell_order(amount, sell_price)

        # Place grid of buy orders
        for i in range(1, self.config.grids):
            buy_price = current_price - (i * self.grid_size)
            buy_amount = self.config.quote_per_trade / buy_price
            await self._place_buy_order(buy_amount, buy_price)

    async def _perform_fresh_start(self):
        """Cancel all orders and sell existing position."""
        orders = await self.exchange.fetch_open_orders()
        for order in orders:
            await self.exchange.cancel_order(order['id'])

        balance = await self.exchange.fetch_balance()
        base_currency = self.config.pair.split('/')[0]
        position = Decimal(str(balance['free'][base_currency]))
        if position > Decimal('0'):
            await self.exchange.create_market_sell_order(position)

    async def _place_buy_order(self, amount: Decimal, price: Decimal) -> Dict:
        """Place a new buy order and track it."""
        order = await self.exchange.create_limit_buy_order(amount, price)
        self.order_pairs.append(OrderPair(
            buy_order_id=order['id'],
            buy_price=Decimal(str(order['price'])),
            amount=Decimal(str(order['amount'])),
            timestamp=order['timestamp']
        ))
        return order

    async def _place_sell_order(self, amount: Decimal, price: Decimal) -> Dict:
        """Place a new sell order and update order tracking."""
        order = await self.exchange.create_limit_sell_order(amount, price)
        # Find the corresponding buy order and update the pair
        for pair in self.order_pairs:
            if pair.sell_order_id is None:
                pair.sell_order_id = order['id']
                pair.sell_price = Decimal(str(order['price']))
                break
        return order

    async def handle_filled_order(self, trade: Trade):
        """Handle a filled order and create corresponding orders."""
        if trade.side == 'buy':
            # Place a sell order one grid size above
            sell_price = trade.price + self.grid_size
            await self._place_sell_order(trade.amount, sell_price)
            
            # Place a new buy order one grid size below
            buy_price = trade.price - self.grid_size
            buy_amount = self.config.quote_per_trade / buy_price
            await self._place_buy_order(buy_amount, buy_price)
        
        elif trade.side == 'sell':
            # Update order pair tracking
            for pair in self.order_pairs:
                if pair.sell_order_id == trade.order_id:
                    self.completed_trades.append(trade)
                    self.order_pairs.remove(pair)
                    break

    async def check_order_health(self):
        """Verify grid health and recreate missing orders."""
        open_orders = await self.exchange.fetch_open_orders()
        
        # Count buy and sell orders
        buy_orders = [o for o in open_orders if o['side'] == 'buy']
        sell_orders = [o for o in open_orders if o['side'] == 'sell']

        # Ensure we have at least one sell order
        if not sell_orders:
            balance = await self.exchange.fetch_balance()
            base_currency = self.config.pair.split('/')[0]
            if Decimal(str(balance['free'][base_currency])) > Decimal('0'):
                current_price = self.exchange.current_price
                sell_price = current_price + self.grid_size
                await self._place_sell_order(
                    balance['free'][base_currency],
                    sell_price
                )

        # Ensure we have enough buy orders
        missing_buys = self.config.grids - len(buy_orders)
        if missing_buys > 0:
            lowest_buy = min(buy_orders, key=lambda x: x['price']) if buy_orders else None
            base_price = (lowest_buy['price'] if lowest_buy 
                         else self.exchange.current_price - self.grid_size)
            
            for i in range(missing_buys):
                buy_price = Decimal(str(base_price)) - (i * self.grid_size)
                buy_amount = self.config.quote_per_trade / buy_price
                await self._place_buy_order(buy_amount, buy_price)
