import asyncio
import json
import signal
from typing import Optional
from decimal import Decimal
from datetime import datetime, timedelta

from .models import BotConfig, Trade
from .exchange import ExchangeInterface
from .strategy import GridStrategy
from .websocket import WebSocketManager


class GridBot:
    def __init__(self, config_path: Optional[str] = None, fresh_start: bool = False):
        self.config = self._load_config(config_path)
        self.fresh_start = fresh_start
        self.exchange = ExchangeInterface(self.config)
        self.strategy = GridStrategy(self.config, self.exchange)
        self.ws_manager = WebSocketManager(self.config)
        self.current_price = Decimal("0")
        self.last_price = Decimal("0")
        self.running = True
        self.tasks = []
        self._setup_signal_handlers()

    @staticmethod
    def _load_config(config_path: Optional[str] = None) -> BotConfig:
        """Load and validate configuration from JSON file or from environment variables"""
        if config_path:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                config_data['coin'] = config_data['pair'].split('/')[0]
            return BotConfig(**config_data)
        else:
            return BotConfig.from_env()

    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown."""
        def handle_signal(signum, frame):
            print("\nReceived shutdown signal. Cleaning up...")
            self.running = False
            self._cancel_tasks()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    async def initialize(self):
        """Initialize bot components."""
        # Initialize exchange
        await self.exchange.initialize()
        self.exchange.balance = await self.exchange.fetch_balance()
        print(f"Balance: {self.exchange.balance['USDT']} USDT")

        # Initialize WebSocket connection
        if self.config.frontend:
            await self.ws_manager.connect()

        # Initialize grid strategy
        await self.strategy.initialize_grid(self.fresh_start)

    async def _handle_fee_coin(self):
        """Manage fee coin balance."""
        if not self.config.fee_coin or not self.config.fee_coin.enabled:
            return

        while self.running:
            try:
                balance = await self.exchange.fetch_balance()
                ticker = await self.exchange.fetch_ticker(
                    f"{self.config.fee_coin.coin}/USDT"
                )

                fee_coin_balance = Decimal(str(balance['free'][self.config.fee_coin.coin]))
                fee_coin_price = Decimal(str(ticker['last']))
                fee_coin_value = fee_coin_balance * fee_coin_price

                if fee_coin_value < self.config.fee_coin.repurchase_balance:
                    amount = (self.config.fee_coin.repurchase_amount / fee_coin_price)

                    await self.exchange.create_market_buy_order(amount)
                    print(f"Topped up {self.config.fee_coin.coin}")

            except Exception as e:
                print(f"Fee coin management error: {e}")

            # Random delay to avoid multiple bots buying simultaneously
            await asyncio.sleep(60 + (hash(self.config.name) % 180))

    async def _watch_orders(self):
        """Monitor and handle completed orders."""
        while self.running:
            try:
                orders = await self.exchange.watch_orders()
                if orders is None or len(orders) == 0:
                    print("No orders returned")
                    await asyncio.sleep(0.01)
                    continue
                for order in orders:
                    # Check if the order is limit, and closed
                    print(f"Order {order['id']} status: {order['status']}, filled: {order['filled']}")
                    if order['status'] == 'closed' and order['type'] == 'limit':
                        this_trade = Trade(
                            order_id=order['id'],
                            side=order['side'],
                            symbol=self.config.pair,
                            price=Decimal(str(order['price'])),
                            amount=Decimal(str(order['amount'])),
                            cost=Decimal(str(order['cost'])),
                            timestamp=int(order['timestamp'])
                        )
                        await self.strategy.handle_filled_order(this_trade)
                        self._update_stats()
            except Exception as e:
                print(f"Order watching error: {e}")
                await asyncio.sleep(5)  # Add a delay before retrying

    async def _watch_ticker(self):
        """Monitor and handle ticker updates."""
        while self.running:
            try:
                ticker = await self.exchange.watch_ticker()
                self.current_price = Decimal(str(ticker['last']))
                if self.current_price != self.last_price:
                    # print(f"Current price: {self.current_price}")
                    self.last_price = self.current_price
                    self.ws_manager.add_price(self.current_price)
                    self._update_stats()
            except Exception as e:
                print(f"Ticker watching error: {e}")

    async def _monitor_health(self):
        """Periodic health check of orders."""
        while self.running:
            await asyncio.sleep(60)
            try:
                await self.strategy.check_order_health()
            except Exception as e:
                print(f"Health check error: {e}")

    def _update_stats(self, trade: Optional[Trade] = None):
        """Update and send statistics to frontend."""
        if not self.config.frontend:
            return

        stats = {
            'total_profit': self._calculate_total_profit(),
            'daily_profit': self._calculate_period_profit(hours=24),
            'weekly_profit': self._calculate_period_profit(hours=168),
            'monthly_profit': self._calculate_period_profit(hours=720),
        }

        if trade:
            self.ws_manager.add_price(trade.price)
            self.ws_manager.send_update('trade', trade.dict(), stats)
        else:
            self.ws_manager.send_update('stats', {}, stats)

    def _calculate_total_profit(self) -> float:
        """Calculate total profit from completed trades."""
        total_profit = Decimal('0')
        for trade in self.strategy.completed_trades:
            profit = (trade.sell_price - trade.buy_price) * trade.amount
            total_profit += profit
        return float(total_profit)

    def _calculate_period_profit(self, hours: int) -> float:
        """Calculate profit for a specific time period."""
        period_start = datetime.now() - timedelta(hours=hours)
        period_profit = Decimal('0')

        for trade in self.strategy.completed_trades:
            if trade.timestamp >= period_start.timestamp() * 1000:
                profit = (trade.sell_price - trade.buy_price) * trade.amount
                period_profit += profit

        return float(period_profit)

    async def run(self):
        """Main bot execution loop."""
        try:
            await self.initialize()

            self.tasks = [
                asyncio.create_task(self._watch_ticker()),
                asyncio.create_task(self._watch_orders()),
                asyncio.create_task(self._monitor_health()),
            ]

            if self.config.fee_coin and self.config.fee_coin.enabled:
                self.tasks.append(asyncio.create_task(self._handle_fee_coin()))

            if self.config.frontend:
                self.tasks.extend([
                    asyncio.create_task(self.ws_manager.keep_alive()),
                    asyncio.create_task(self.ws_manager.process_messages()),
                ])

            try:
                # Wait for all tasks to complete or be cancelled
                await asyncio.gather(*self.tasks)
            except asyncio.CancelledError:
                print("Tasks were cancelled.")
        except Exception as e:
            print(f"Bot execution error: {e}")
        finally:
            self.running = False
            await self._cleanup()

    def _cancel_tasks(self):
        """Cancel all running tasks."""
        for task in self.tasks:
            task.cancel()

    async def _cleanup(self):
        """Cleanup resources on shutdown."""
        if self.config.frontend:
            await self.ws_manager.close()
        await self.exchange.close()


def main():
    """Entry point for the bot."""
    import argparse

    parser = argparse.ArgumentParser(description="Grid Trading Bot")
    parser.add_argument('--config', type=str, required=False,
                        help='Path to configuration file')
    parser.add_argument('--fresh', action='store_true',
                        help='Start fresh by closing current position')

    args = parser.parse_args()

    bot = GridBot(args.config, args.fresh)
    asyncio.run(bot.run())


if __name__ == '__main__':
    main()
