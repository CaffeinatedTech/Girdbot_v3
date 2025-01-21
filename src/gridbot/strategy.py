from decimal import Decimal
from typing import Optional
from .models import BotConfig, OrderPair, Trade
from .exchange import ExchangeInterface
from .websocket import WebSocketManager
import json
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
            await self._load_order_pairs()
            print("Initializing grid...")
            if fresh_start:
                print("Fresh start: Cancelling existing orders and positions...")
                # Cancel existing orders and positions
                open_orders = await self.exchange.fetch_open_orders()
                print(f"Open orders to cancel: {[order['id'] for order in open_orders]}")
                for order in open_orders:
                    await self.exchange.cancel_order(order['id'])
                    print(f"Cancelled order {order['id']}")

                # Reset order tracking
                self.order_pairs = []
                self.completed_trades = []
                print("Order tracking reset.")

                # Fetch current market price
                ticker = await self.exchange.fetch_ticker()
                current_price = Decimal(str(ticker['last']))
                print(f"Current market price: {current_price}")

                # Calculate grid prices
                grid_size = self.calculate_grid_size(current_price)
                self.grid_size = grid_size
                print(f"Grid size calculated: {grid_size}")

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
                    buy_type="market",
                    amount=amount,
                    timestamp=int(time.time() * 1000),
                    buy_order_status="closed"
                )

                # Place initial sell order
                sell_price = current_price + grid_size
                sell_order = await self.exchange.create_limit_sell_order(amount, sell_price)
                initial_pair.sell_order_id = sell_order['id']
                initial_pair.sell_price = Decimal(str(sell_order['price']))

                self.order_pairs.append(initial_pair)

                print(f"Initial sell order {sell_order['id']}: Amount {amount}, Price {sell_price}")

                # Place buy orders below current price
                for i in range(1, self.config.grids):
                    buy_price = current_price - (i * grid_size)
                    buy_amount = self.config.quote_per_trade * (1 / (current_price - (i * grid_size)))
                    buy_order = await self.exchange.create_limit_buy_order(buy_amount, buy_price)

                    print(f"Buy order {buy_order['id']}: Amount {buy_amount}, Price {buy_price}")

                    # Create order pair for the buy order
                    pair = OrderPair(
                        buy_order_id=buy_order['id'],
                        buy_price=Decimal(str(buy_order['price'])),
                        buy_type="limit",
                        amount=buy_amount,
                        timestamp=int(time.time() * 1000),
                        buy_order_status="open"
                    )
                    self.order_pairs.append(pair)

                time.sleep(1)
                await self._save_order_pairs()

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

    def _last_sell_order(self, order_id: str) -> bool:
        # Check if this is the only sell order in the grid
        for pair in self.order_pairs:
            if pair.sell_order_id != order_id and pair.sell_order_id is not None:
                return False
        # print("Last sell order")
        return True

    async def _trail_up(self):
        # print("Trailing up the grid...")
        # Fetch current market price
        ticker = await self.exchange.fetch_ticker()
        current_price = Decimal(str(ticker['last']))
        lowest_buy_order = None
        lowest_buy_index = -1
        for index, pair in enumerate(self.order_pairs):
            if pair.buy_order_id is not None \
                    and (lowest_buy_order is None or pair.buy_price < lowest_buy_order.buy_price):
                lowest_buy_order = pair
                lowest_buy_index = index

        if lowest_buy_order is None:
            print("No buy orders found to trail up.")
            return

        # Cancel the buy order
        await self.exchange.cancel_order(lowest_buy_order.buy_order_id)

        # Buy in again
        buy_amount = self.config.quote_per_trade / current_price
        buy_order = await self.exchange.create_market_buy_order(buy_amount)
        # Create new sell order
        sell_price = current_price + self.grid_size
        sell_order = await self.exchange.create_limit_sell_order(buy_amount, sell_price)

        # Create a new OrderPair object
        new_pair = OrderPair(
            buy_order_id=buy_order['id'],
            buy_price=Decimal(str(buy_order['price'])),
            sell_order_id=sell_order['id'],
            sell_price=Decimal(str(sell_order['price'])),
            amount=buy_amount,
            timestamp=int(time.time() * 1000),
            buy_order_status="closed"
        )

        # Replace the old pair with the new pair in the list
        self.order_pairs[lowest_buy_index] = new_pair

        await self._save_order_pairs()

        print(f"Trailed up: Cancelled order {lowest_buy_order.buy_order_id}, "
              f"new sell order {sell_order['id']}")

    async def handle_filled_order(self, trade: Trade):
        """Handle a filled order and maintain the grid."""
        try:
            # Check order status before processing
            # if trade.status not in ['closed', 'filled']:
            #     print(f"Ignoring order {trade.order_id} with status {trade.status}")
            #     return

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
                print(f"Filled BUY order {trade.order_id} at price {trade.price}")
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
                print(f"Created sell order {sell_order['id']} at price {sell_price}")

                # Update pair with sell order details
                pair.sell_order_id = sell_order['id']
                pair.sell_price = Decimal(str(sell_order['price']))
                pair.buy_order_status = "closed"

            else:  # sell order
                print(f"Filled SELL order {trade.order_id} at price {trade.price}")
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
                    print(f"Created buy order {buy_order['id']} at price {buy_price}")

                    # Create new pair for the buy order
                    new_pair = OrderPair(
                        buy_order_id=buy_order['id'],
                        buy_price=Decimal(str(buy_order['price'])),
                        amount=trade.amount,
                        timestamp=trade.timestamp,
                        buy_order_status="open"
                    )
                    self.order_pairs.append(new_pair)

                    # Check if this was the last sell order
                    if self._last_sell_order(trade.order_id):
                        # Trail up the grid
                        await self._trail_up()

            await self._save_order_pairs()

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
            print(f"Error handling filled order: {e}")
            if self.websocket:
                await self.websocket.send_update({
                    'type': 'error',
                    'data': {
                        'message': str(e),
                        'timestamp': int(time.time() * 1000)
                    }
                })
            raise

    async def check_order_health(self):
        """Check and repair grid orders."""
        # print("Checking order health...")
        open_orders = await self.exchange.fetch_open_orders()
        open_order_ids = {order['id'] for order in open_orders}
        new_order_ids = []

        # Print order IDs and sides
        # for order in open_orders:
        #     print(f"Open {order['side']} order {order['id']} at price {order['price']}")

        # Print saved order IDS and sides for limit orders only.  Remember that both buy and sell orders are in the same object
        # for pair in self.order_pairs:
        #     if pair.buy_type == "limit":
        #         if pair.buy_order_status == "open":
        #             print(f"Saved buy order {pair.buy_order_id} at price {pair.buy_price}")
        #     if pair.buy_order_status == "open":
        #         print(f"Saved sell order {pair.sell_order_id} at price {pair.sell_price}")

        # Fetch current market price
        ticker = await self.exchange.fetch_ticker()
        current_price = Decimal(str(ticker['last']))
        # print(f"Current market price: {current_price}")

        orders_updated = False

        for pair in self.order_pairs[:]:  # Create a copy of the list to iterate over
            if pair.buy_order_id in new_order_ids:
                continue
            # Check buy order
            if pair.buy_order_status == "open" and pair.buy_order_id and pair.buy_order_id not in open_order_ids and pair.buy_type == "limit":
                print(f"Buy order {pair.buy_order_id} not found in open orders. Checking status...")
                try:
                    order_status = await self.exchange.fetch_order(pair.buy_order_id)
                    if order_status['status'] == 'closed':
                        pair.buy_order_status = "closed"
                        # Create corresponding sell order at current price + grid_size
                        sell_price = max(current_price + self.grid_size, pair.buy_price + self.grid_size)
                        sell_order = await self.exchange.create_limit_sell_order(pair.amount, sell_price)
                        pair.sell_order_id = sell_order['id']
                        pair.sell_price = Decimal(str(sell_order['price']))
                        orders_updated = True
                        new_order_ids.append(pair.sell_order_id)
                        print(
                            f"Buy order {pair.buy_order_id} was filled. Updated state and created sell order {pair.sell_order_id}...")
                    elif order_status['status'] == 'canceled':
                        print(f"Buy order {pair.buy_order_id} was cancelled. Recreating...")
                        # Recreate buy order at current price or original price, whichever is lower
                        new_buy_price = min(current_price, pair.buy_price)
                        buy_order = await self.exchange.create_limit_buy_order(pair.amount, new_buy_price)
                        pair.buy_order_id = buy_order['id']
                        pair.buy_price = Decimal(str(buy_order['price']))
                        orders_updated = True
                        new_order_ids.append(pair.buy_order_id)
                except Exception as e:
                    print(f"Error checking buy order {pair.buy_order_id} status: {e}")

            if pair.sell_order_id in new_order_ids:
                continue

            # Check sell order
            if pair.sell_order_id and pair.sell_order_id not in open_order_ids:
                print(f"Sell order {pair.sell_order_id} not found in open orders. Checking status...")
                try:
                    order_status = await self.exchange.fetch_order(pair.sell_order_id)
                    if order_status['status'] == 'closed':
                        # Move this completed pair to completed_trades
                        self.completed_trades.append(pair)
                        self.order_pairs.remove(pair)
                        # Create a new buy order to replace the completed pair
                        buy_price = min(current_price - self.grid_size, pair.sell_price - self.grid_size)
                        buy_order = await self.exchange.create_limit_buy_order(pair.amount, buy_price)
                        new_pair = OrderPair(
                            buy_order_id=buy_order['id'],
                            buy_price=Decimal(str(buy_order['price'])),
                            amount=pair.amount,
                            buy_order_status="open",
                            timestamp=int(time.time() * 1000)
                        )
                        self.order_pairs.append(new_pair)
                        orders_updated = True
                        new_order_ids.append(pair.buy_order_id)
                        print(
                            f"Sell order {pair.sell_order_id} was filled. Updated state and created buy order {pair.buy_order_id}...")
                    elif order_status['status'] == 'canceled':
                        print(f"Sell order {pair.sell_order_id} was cancelled. Recreating...")
                        # Recreate sell order at current price or original price, whichever is higher
                        new_sell_price = max(current_price, pair.sell_price)
                        sell_order = await self.exchange.create_limit_sell_order(pair.amount, new_sell_price)
                        pair.sell_order_id = sell_order['id']
                        pair.sell_price = Decimal(str(sell_order['price']))
                        orders_updated = True
                        new_order_ids.append(pair.sell_order_id)
                except Exception as e:
                    print(f"Error checking sell order {pair.sell_order_id} status: {e}")

        # Ensure we don't have more order pairs than grids
        while len(self.order_pairs) > self.config.grids:
            excess_pair = self.order_pairs.pop()
            print(f"Removing excess order pair: {excess_pair}")
            if excess_pair.buy_order_id:
                await self.exchange.cancel_order(excess_pair.buy_order_id)
            if excess_pair.sell_order_id:
                await self.exchange.cancel_order(excess_pair.sell_order_id)

        if orders_updated:
            await self._save_order_pairs()

        # print(f"Order health check complete. Current order pairs: {len(self.order_pairs)}")

    async def _save_order_pairs(self):
        """Save order pairs to file."""
        # print(f"Saving order pairs to file... {len(self.order_pairs)}")
        with open(f'order_pairs_{self.config.coin}.json', 'w') as f:
            json.dump([pair.to_dict() for pair in self.order_pairs], f)

    async def _load_order_pairs(self):
        """Load order pairs from file."""
        try:
            with open(f'order_pairs_{self.config.coin}.json', 'r') as f:
                pairs_data = json.load(f)
                self.order_pairs = [OrderPair.from_dict(data) for data in pairs_data]
        except FileNotFoundError:
            print("Order pairs file not found. Starting with an empty list.")
            self.order_pairs = []

