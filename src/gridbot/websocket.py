import json
import asyncio
import websockets
from typing import Dict, Any, Optional
from decimal import Decimal
from collections import deque
from .models import BotConfig


class WebSocketManager:
    def __init__(self, config: BotConfig):
        self.config = config
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.message_queue: deque = deque()
        self.prices: deque = deque(maxlen=10)

    async def connect(self):
        """Establish WebSocket connection."""
        if not self.config.frontend:
            return
        
        try:
            self.ws = await websockets.connect(f"wss://{self.config.frontend_host}")
            self.connected = True
            print("WebSocket connected")
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            self.connected = False

    async def keep_alive(self):
        """Maintain WebSocket connection."""
        while True:
            if self.config.frontend:
                if self.connected and self.ws:
                    try:
                        await self.ws.ping()
                    except websockets.ConnectionClosed:
                        print("WebSocket connection closed")
                        self.connected = False
                        self.ws = None
                else:
                    await self.connect()
            await asyncio.sleep(30)

    async def process_messages(self):
        """Process and send queued messages."""
        while True:
            if self.connected and self.ws and self.message_queue:
                message = self.message_queue.popleft()
                try:
                    await self.ws.send(json.dumps(message))
                except Exception as e:
                    print(f"Failed to send message: {e}")
                    self.message_queue.appendleft(message)
            await asyncio.sleep(0.5)

    def add_price(self, price: Decimal):
        """Add price to the price history."""
        self.prices.append(float(price))

    def send_update(self, message_type: str, message: Dict[str, Any], stats: Dict[str, Any]):
        """Queue a message to be sent to the frontend."""
        if not self.config.frontend:
            return

        self.message_queue.append({
            'bot': self.config.name,
            'type': message_type,
            'message': message,
            'stats': {
                **stats,
                'prices': list(self.prices)
            }
        })

    async def close(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
