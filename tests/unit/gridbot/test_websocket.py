import pytest
import json
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
from websockets.exceptions import ConnectionClosed
from gridbot.websocket import WebSocketManager


@pytest.fixture
def mock_websocket():
    """Create a mock websocket connection."""
    mock_ws = AsyncMock()
    mock_ws.ping = AsyncMock()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()
    return mock_ws


@pytest.mark.unit
@pytest.mark.websocket
class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_connect_success(self, mock_config, mock_websocket):
        """Test successful websocket connection."""
        mock_config.frontend = True
        mock_config.frontend_host = "localhost:8080"
        
        with patch('websockets.connect', new=AsyncMock(return_value=mock_websocket)):
            manager = WebSocketManager(mock_config)
            await manager.connect()
            
            assert manager.connected is True
            assert manager.ws == mock_websocket

    @pytest.mark.asyncio
    async def test_connect_disabled(self, mock_config):
        """Test websocket connection when frontend is disabled."""
        mock_config.frontend = False
        
        manager = WebSocketManager(mock_config)
        await manager.connect()
        
        assert manager.connected is False
        assert manager.ws is None

    @pytest.mark.asyncio
    async def test_connect_failure(self, mock_config):
        """Test websocket connection failure."""
        mock_config.frontend = True
        mock_config.frontend_host = "localhost:8080"
        
        with patch('websockets.connect', side_effect=Exception("Connection failed")):
            manager = WebSocketManager(mock_config)
            await manager.connect()
            
            assert manager.connected is False
            assert manager.ws is None

    @pytest.mark.asyncio
    async def test_keep_alive_success(self, mock_config, mock_websocket):
        """Test keep-alive functionality."""
        mock_config.frontend = True
        manager = WebSocketManager(mock_config)
        manager.ws = mock_websocket
        manager.connected = True

        # Run keep_alive for a short time
        keep_alive_task = asyncio.create_task(manager.keep_alive())
        await asyncio.sleep(0.1)  # Let it run briefly
        keep_alive_task.cancel()  # Stop the task
        
        try:
            await keep_alive_task
        except asyncio.CancelledError:
            pass

        assert mock_websocket.ping.called

    @pytest.mark.asyncio
    async def test_keep_alive_reconnect(self, mock_config, mock_websocket):
        """Test keep-alive reconnection on failure."""
        mock_config.frontend = True
        manager = WebSocketManager(mock_config)
        manager.ws = mock_websocket
        manager.connected = True

        # Make ping fail with ConnectionClosed
        mock_websocket.ping.side_effect = ConnectionClosed(None, None)

        # Run keep_alive for a short time
        keep_alive_task = asyncio.create_task(manager.keep_alive())
        await asyncio.sleep(0.1)  # Let it run briefly
        keep_alive_task.cancel()  # Stop the task
        
        try:
            await keep_alive_task
        except asyncio.CancelledError:
            pass

        assert manager.connected is False
        assert manager.ws is None

    @pytest.mark.asyncio
    async def test_process_messages(self, mock_config, mock_websocket):
        """Test message processing and sending."""
        mock_config.frontend = True
        manager = WebSocketManager(mock_config)
        manager.ws = mock_websocket
        manager.connected = True

        # Add a test message to the queue
        test_message = {
            'bot': mock_config.name,
            'type': 'test',
            'message': {'key': 'value'},
            'stats': {'test_stat': 123}
        }
        manager.message_queue.append(test_message)

        # Run process_messages for a short time
        process_task = asyncio.create_task(manager.process_messages())
        await asyncio.sleep(0.1)  # Let it run briefly
        process_task.cancel()  # Stop the task
        
        try:
            await process_task
        except asyncio.CancelledError:
            pass

        mock_websocket.send.assert_called_once_with(json.dumps(test_message))
        assert len(manager.message_queue) == 0

    @pytest.mark.asyncio
    async def test_process_messages_failure(self, mock_config, mock_websocket):
        """Test message processing when send fails."""
        mock_config.frontend = True
        manager = WebSocketManager(mock_config)
        manager.ws = mock_websocket
        manager.connected = True

        # Make send fail
        mock_websocket.send.side_effect = Exception("Send failed")

        # Add a test message to the queue
        test_message = {
            'bot': mock_config.name,
            'type': 'test',
            'message': {'key': 'value'},
            'stats': {'test_stat': 123}
        }
        manager.message_queue.append(test_message)

        # Run process_messages for a short time
        process_task = asyncio.create_task(manager.process_messages())
        await asyncio.sleep(0.1)  # Let it run briefly
        process_task.cancel()  # Stop the task
        
        try:
            await process_task
        except asyncio.CancelledError:
            pass

        assert len(manager.message_queue) == 1  # Message should be back in queue
        assert manager.message_queue[0] == test_message

    def test_add_price(self, mock_config):
        """Test price history management."""
        manager = WebSocketManager(mock_config)
        
        # Add more than maxlen prices to test deque behavior
        prices = [Decimal(str(i)) for i in range(15)]
        for price in prices:
            manager.add_price(price)
            
        assert len(manager.prices) == 10  # Should be limited by maxlen
        assert list(manager.prices) == [float(i) for i in range(5, 15)]  # Should have last 10 prices

    def test_send_update(self, mock_config):
        """Test update message queueing."""
        mock_config.frontend = True
        manager = WebSocketManager(mock_config)
        
        # Add some prices first
        for i in range(3):
            manager.add_price(Decimal(str(i)))
        
        message = {'status': 'testing'}
        stats = {'profit': 100}
        
        manager.send_update('test', message, stats)
        
        assert len(manager.message_queue) == 1
        queued_message = manager.message_queue[0]
        assert queued_message['bot'] == mock_config.name
        assert queued_message['type'] == 'test'
        assert queued_message['message'] == message
        assert queued_message['stats']['profit'] == 100
        assert queued_message['stats']['prices'] == [0.0, 1.0, 2.0]

    def test_send_update_frontend_disabled(self, mock_config):
        """Test update message queueing when frontend is disabled."""
        mock_config.frontend = False
        manager = WebSocketManager(mock_config)
        
        manager.send_update('test', {'status': 'testing'}, {'profit': 100})
        
        assert len(manager.message_queue) == 0

    @pytest.mark.asyncio
    async def test_close(self, mock_config, mock_websocket):
        """Test websocket closure."""
        manager = WebSocketManager(mock_config)
        manager.ws = mock_websocket
        
        await manager.close()
        
        mock_websocket.close.assert_called_once()
