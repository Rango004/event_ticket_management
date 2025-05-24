# consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
from django.middleware.csrf import CsrfViewMiddleware
from django.http.request import HttpRequest
from channels.exceptions import DenyConnection
import json

class CSRFAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        try:
            request = HttpRequest()
            request.META = {
                'HTTP_COOKIE': dict(scope['headers']).get(b'cookie', b'').decode(),
                'CSRF_COOKIE': dict(scope['headers']).get(b'x-csrftoken', b'').decode()
            }
            middleware = CsrfViewMiddleware()
            middleware.process_request(request)
        except Exception as e:
            await send({
                'type': 'websocket.close',
                'code': 4001,
                'reason': 'CSRF Validation Failed'
            })
            return

        return await self.app(scope, receive, send)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            # CSRF validation
            await self.accept()
            await self.send(text_data=json.dumps({
                'type': 'connection_success',
                'message': 'Connected successfully'
            }))
        except Exception as e:
            await self.close(code=4001)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            user = self.scope['user']
            
            if not user.is_authenticated:
                raise Exception("Authentication required")

            # Handle message processing here
            
            await self.send(text_data=json.dumps({
                'type': 'chat_message',
                'message': data['message'],
                'user': user.username
            }))
            
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format", 4001)
        except KeyError as e:
            await self.send_error(f"Missing field: {str(e)}", 4002)
        except Exception as e:
            await self.send_error(str(e), 4000)

    async def send_error(self, message, code=4000):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'code': code,
            'message': message
        }))