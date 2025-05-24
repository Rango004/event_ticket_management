# tests.py
from channels.testing import WebsocketCommunicator
from ticketing_system.asgi import application

async def test_csrf_protection():
    communicator = WebsocketCommunicator(application, "/ws/chat/")
    connected, _ = await communicator.connect()
    assert connected is False  # Should fail without CSRF token