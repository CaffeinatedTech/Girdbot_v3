import asyncio
import json
import signal
from pathlib import Path
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

from .models import BotConfig, Trade
from .exchange import ExchangeInterface
from .strategy import GridStrategy
from .websocket import WebSocketManager


class GridBot:
    def __init__(self, config_path: str, fresh_start: bool = False):
        self.config = self._load_config(config_path)
        self.fresh_start = fresh_start
        self.exchange = ExchangeInterface(self.config)
        self.strategy = GridStrategy(self.config, self.exchange)
        self.ws_manager = WebSocketManager(self.config)
        self.running = True
        self._setup_signal_handlers()

    @staticmethod
    def _load_config(config_path: str) -> BotConfig:
        """Load and validate configuration from JSON file."""
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return BotConfig(**config_data)

    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown."""
        def handle_signal(signum, frame):
            print("\nReceived shutdown signal. Cleaning up...")
            self.running = False
        
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    async def initialize(self):
        """Initialize bot components."""
        # Initialize exchange
        await self.exchange.initialize()
        
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
                    amount = (self.config.fee_coin.repurchase_amount / 
                            fee_coin_price)
                    
                    await self.exchange.create_market_buy_order(amount)
                    print(f"Topped up {self.config.fee_coin.coin}")
                    
            except Exception as e:
                print(f"Fee coin management error: {e}")
            
            # Random delay to avoid multiple bots buying simultaneously
            await asyncio.sleep(60 + (hash(self.config.name) % 180))

    async def _watch_trades(self):
        """Monitor and handle trades."""
        while self.running:
            try:
                trade = await self.exchange.watch_trades()
                if trade:
                    await self.strategy.handle_filled_order(trade)
                    self._update_stats(trade)
            except Exception as e:
                print(f"Trade watching error: {e}")

    async def _monitor_health(self):
        """Periodic health check of orders."""
        while self.running:
            try:
                await self.strategy.check_order_health()
            except Exception as e:
                print(f"Health check error: {e}")
            await asyncio.sleep(60)

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
            if trade.side == 'sell':
                # Find matching buy order
                for pair in self.strategy.order_pairs:
                    if pair.sell_order_id == trade.order_id:
                        profit = (trade.price - pair.buy_price) * trade.amount
                        total_profit += profit
                        break
        return float(total_profit)

    def _calculate_period_profit(self, hours: int) -> float:
        """Calculate profit for a specific time period."""
        period_start = datetime.now() - timedelta(hours=hours)
        period_profit = Decimal('0')
        
        for trade in self.strategy.completed_trades:
            if trade.timestamp >= period_start.timestamp() * 1000:
                if trade.side == 'sell':
                    for pair in self.strategy.order_pairs:
                        if pair.sell_order_id == trade.order_id:
                            profit = (trade.price - pair.buy_price) * trade.amount
                            period_profit += profit
                            break
        
        return float(period_profit)

    async def run(self):
        """Main bot execution loop."""
        try:
            await self.initialize()
            
            tasks = [
                asyncio.create_task(self._watch_trades()),
                asyncio.create_task(self._monitor_health()),
            ]

            if self.config.fee_coin and self.config.fee_coin.enabled:
                tasks.append(asyncio.create_task(self._handle_fee_coin()))

            if self.config.frontend:
                tasks.extend([
                    asyncio.create_task(self.ws_manager.keep_alive()),
                    asyncio.create_task(self.ws_manager.process_messages()),
                ])

            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

        except Exception as e:
            print(f"Bot execution error: {e}")
        finally:
            self.running = False
            await self._cleanup()

    async def _cleanup(self):
        """Cleanup resources on shutdown."""
        if self.config.frontend:
            await self.ws_manager.close()
        await self.exchange.close()


def main():
    """Entry point for the bot."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Grid Trading Bot")
    parser.add_argument('--config', type=str, required=True,
                       help='Path to configuration file')
    parser.add_argument('--fresh', action='store_true',
                       help='Start fresh by closing current position')
    
    args = parser.parse_args()
    
    bot = GridBot(args.config, args.fresh)
    asyncio.run(bot.run())


if __name__ == '__main__':
    main()
