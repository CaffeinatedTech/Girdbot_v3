from decimal import Decimal
from typing import List, Optional, Dict
from .models import BotConfig, OrderPair, Trade
from .exchange import ExchangeInterface
from .websocket import WebSocketManager
import asyncio
import time


class GridStrategy:
    """Grid trading strategy implementation."""
    def __init__(self, config: BotConfig, exchange: ExchangeInterface, websocket: Optional[WebSocketManager] = None):
        """Initialize strategy with configuration."""
        self.config = config
        self.exchange = exchange
        self.websocket = websocket
        self.order_pairs = []
        self.completed_trades = []
        self.current_timestamp = 0
        self.grid_size = Decimal("0")
        
        # Parse trading pair
        self.base_currency, self.quote_currency = self.config.pair.split('/')
        
    def calculate_grid_size(self, current_price: Decimal) -> Decimal:
        """Calculate the size of each grid level."""
        return (current_price * self.config.gridsize) / Decimal("100")

    async def initialize_grid(self, fresh_start: bool = False):
        """Initialize the grid with orders."""
        try:
            if fresh_start:
                # Cancel existing orders and positions
                open_orders = await self.exchange.fetch_open_orders()
                for order in open_orders:
                    await self.exchange.cancel_order(order['id'])

                # Reset order tracking
                self.order_pairs = []
                self.completed_trades = []
                
                # Get current market price
                current_price = self.exchange.current_price
                
                # Calculate grid prices
                grid_size = self.calculate_grid_size(current_price)
                self.grid_size = grid_size
                
                # Send initial grid status before any orders are created
                if self.websocket:
                    await self.websocket.send_update({
                        'type': 'grid_status',
                        'data': {
                            'total_pairs': 0,
                            'active_pairs': 0,
                            'completed_trades': 0
                        }
                    })
                
                # Initial market buy to establish position
                amount = self.config.quote_per_trade / current_price
                initial_buy = await self.exchange.create_market_buy_order(amount)
                print(f"Initial market buy: Amount {amount}, Price {current_price}")

                # Create initial order pair
                initial_pair = OrderPair(
                    buy_order_id=initial_buy['id'],
                    buy_price=current_price,
                    amount=amount,
                    timestamp=int(time.time() * 1000)
                )
                self.order_pairs.append(initial_pair)

                # Place initial sell order
                sell_price = current_price + grid_size
                sell_order = await self.exchange.create_limit_sell_order(amount, sell_price)
                initial_pair.sell_order_id = sell_order['id']
                initial_pair.sell_price = Decimal(str(sell_order['price']))

                # Place buy orders below current price
                for i in range(self.config.grids - 1):
                    buy_price = current_price - (grid_size * (i + 1))
                    buy_amount = self.config.quote_per_trade / buy_price
                    buy_order = await self.exchange.create_limit_buy_order(buy_amount, buy_price)
                    
                    # Create order pair for the buy order
                    pair = OrderPair(
                        buy_order_id=buy_order['id'],
                        buy_price=Decimal(str(buy_order['price'])),
                        amount=buy_amount,
                        timestamp=int(time.time() * 1000)
                    )
                    self.order_pairs.append(pair)
                    
                    # Create corresponding sell order
                    sell_price = buy_price + grid_size
                    sell_order = await self.exchange.create_limit_sell_order(buy_amount, sell_price)
                    pair.sell_order_id = sell_order['id']
                    pair.sell_price = Decimal(str(sell_order['price']))

            # Send initial grid status
            if self.websocket:
                await self.websocket.send_update({
                    'type': 'grid_status',
                    'data': {
                        'total_pairs': len(self.order_pairs),
                        'active_pairs': len([p for p in self.order_pairs if p.sell_order_id is not None]),
                        'completed_trades': len(self.completed_trades)
                    }
                })
        except Exception as e:
            if self.websocket:
                await self.websocket.send_update({
                    'type': 'error',
                    'data': {
                        'message': str(e),
                        'timestamp': int(time.time() * 1000)
                    }
                })
            raise

    async def _perform_fresh_start(self):
        """Cancel existing orders and sell current position."""
        # Cancel all existing orders
        open_orders = await self.exchange.fetch_open_orders()
        for order in open_orders:
            await self.exchange.cancel_order(order['id'])

        # Sell current position
        balance = await self.exchange.fetch_balance()
        btc_balance = Decimal(str(balance['free']['BTC']))
        if btc_balance > 0:
            await self.exchange.create_market_sell_order(btc_balance)

    async def _create_grid_orders(self, current_price: Decimal):
        """Create a grid of buy and sell orders."""
        base_price = current_price
        quote_per_trade = self.config.quote_per_trade

        # Create sell orders above current price
        for i in range(1, self.config.grids):
            sell_price = base_price + (self.grid_size * i)
            amount = quote_per_trade / sell_price
            sell_order = await self.exchange.create_limit_sell_order(amount, sell_price)
            self.order_pairs.append(OrderPair(
                buy_order_id=None,
                buy_price=None,
                sell_order_id=sell_order['id'],
                sell_price=Decimal(str(sell_order['price'])),
                amount=Decimal(str(sell_order['amount'])),
                timestamp=sell_order['timestamp']
            ))

        # Create buy orders below current price
        for i in range(1, self.config.grids):
            buy_price = base_price - (self.grid_size * i)
            amount = quote_per_trade / buy_price
            buy_order = await self.exchange.create_limit_buy_order(amount, buy_price)
            self.order_pairs.append(OrderPair(
                buy_order_id=buy_order['id'],
                buy_price=Decimal(str(buy_order['price'])),
                sell_order_id=None,
                sell_price=None,
                amount=Decimal(str(buy_order['amount'])),
                timestamp=buy_order['timestamp']
            ))

    async def handle_filled_order(self, trade: Trade):
        """Handle a filled order and maintain the grid."""
        try:
            # Send trade update to websocket first
            if self.websocket:
                await self.websocket.send_update({
                    'type': 'trade',
                    'data': {
                        'side': trade.side,
                        'amount': str(trade.amount),
                        'price': str(trade.price),
                        'timestamp': trade.timestamp
                    }
                })

            if trade.side == "buy":
                # Find or create order pair for this buy
                pair = None
                for p in self.order_pairs:
                    if p.buy_order_id == trade.order_id:
                        pair = p
                        break
                
                if pair is None:
                    pair = OrderPair(
                        buy_order_id=trade.order_id,
                        buy_price=trade.price,
                        amount=trade.amount,
                        timestamp=trade.timestamp
                    )
                    self.order_pairs.append(pair)

                # Create sell order at next grid level up
                sell_price = trade.price + self.grid_size
                sell_order = await self.exchange.create_limit_sell_order(trade.amount, sell_price)
                
                # Update pair with sell order details
                pair.sell_order_id = sell_order['id']
                pair.sell_price = Decimal(str(sell_order['price']))

            else:  # sell order
                # Find the completed pair
                completed_pair = None
                for pair in self.order_pairs:
                    if pair.sell_order_id == trade.order_id:
                        completed_pair = pair
                        self.order_pairs.remove(pair)
                        self.completed_trades.append(pair)
                        break

                if completed_pair:
                    # Create new buy order at the original buy price
                    buy_price = completed_pair.buy_price
                    buy_order = await self.exchange.create_limit_buy_order(completed_pair.amount, buy_price)

                    # Create new pair for the buy order
                    new_pair = OrderPair(
                        buy_order_id=buy_order['id'],
                        buy_price=Decimal(str(buy_order['price'])),
                        amount=trade.amount,
                        timestamp=trade.timestamp
                    )
                    self.order_pairs.append(new_pair)

            # Send grid status update to websocket
            if self.websocket:
                await self.websocket.send_update({
                    'type': 'grid_status',
                    'data': {
                        'total_pairs': len(self.order_pairs),
                        'active_pairs': len([p for p in self.order_pairs if p.sell_order_id is not None]),
                        'completed_trades': len(self.completed_trades)
                    }
                })
        except Exception as e:
            if self.websocket:
                await self.websocket.send_update({
                    'type': 'error',
                    'data': {
                        'message': str(e),
                        'timestamp': int(time.time() * 1000)
                    }
                })
            raise

    async def _place_buy_order(self, amount: Decimal, price: Decimal) -> Dict:
        """Place a new buy order and track it."""
        order = await self.exchange.create_limit_buy_order(amount, price)
        self.order_pairs.append(OrderPair(
            buy_order_id=order['id'],
            buy_price=Decimal(str(order['price'])),
            sell_order_id=None,
            sell_price=None,
            amount=Decimal(str(order['amount'])),
            timestamp=order['timestamp']
        ))
        return order

    async def _place_sell_order(self, amount: Decimal, price: Decimal) -> Dict:
        """Place a new sell order and track it."""
        order = await self.exchange.create_limit_sell_order(amount, price)
        self.order_pairs.append(OrderPair(
            buy_order_id=None,
            buy_price=None,
            sell_order_id=order['id'],
            sell_price=Decimal(str(order['price'])),
            amount=Decimal(str(order['amount'])),
            timestamp=order['timestamp']
        ))
        return order

    async def check_order_health(self):
        """Check and repair grid orders."""
        open_orders = await self.exchange.fetch_open_orders()
        open_order_ids = {order['id'] for order in open_orders}
        
        for pair in self.order_pairs:
            # Check buy order
            if pair.buy_order_id and pair.buy_order_id not in open_order_ids:
                # Recreate missing buy order
                buy_order = await self.exchange.create_limit_buy_order(pair.amount, pair.buy_price)
                pair.buy_order_id = buy_order['id']
                
                # Create corresponding sell order if needed
                if not pair.sell_order_id:
                    sell_price = pair.buy_price + self.grid_size
                    sell_order = await self.exchange.create_limit_sell_order(pair.amount, sell_price)
                    pair.sell_order_id = sell_order['id']
                    pair.sell_price = Decimal(str(sell_order['price']))
            
            # Check sell order (only if it's a sell-only order)
            elif pair.sell_order_id and pair.sell_order_id not in open_order_ids:
                # Recreate missing sell order with original price
                sell_order = await self.exchange.create_limit_sell_order(pair.amount, pair.sell_price)
                pair.sell_order_id = sell_order['id']

        # Send updated grid status
        if self.websocket:
            await self.websocket.send_update({
                'type': 'grid_status',
                'data': {
                    'total_pairs': len(self.order_pairs),
                    'active_pairs': len([p for p in self.order_pairs if p.sell_order_id is not None]),
                    'completed_trades': len(self.completed_trades)
                }
            })

    async def update_price(self):
        """Update current price and notify websocket."""
        ticker = await self.exchange.fetch_ticker()
        current_price = Decimal(str(ticker['last']))
        
        if self.websocket:
            await self.websocket.add_price(current_price)
