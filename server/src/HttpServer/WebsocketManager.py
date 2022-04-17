import asyncio
import json
import sys
import Utils
import logging
from typing import List, Union
from fastapi import WebSocket
from Utils import CustomJsonEncoder

Logger = Utils.get_logger('WebSocket')
Logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)


# WebSocket连接管理器
class WebsocketManager:

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        client = websocket.client
        Logger.info(f'连接新增 {client.host}:{client.port}')
        self.active_connections.append(websocket)
        # await websocket.send_bytes(b'connected')

    def disconnect(self, websocket: WebSocket):
        client = websocket.client
        Logger.info(f'连接断开 {client.host}:{client.port}')
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Union[str, bytes, dict]):
        # print(self.active_connections, message)
        if isinstance(message, str):
            message = message.encode('utf-8')
        elif isinstance(message, dict):
            message = json.dumps(message, cls=CustomJsonEncoder).encode('utf-8')
        for connection in self.active_connections:
            await connection.send_bytes(message)

    def close_all(self):  # 未实现
        loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        for connection in self.active_connections:
            try:
                loop.run_until_complete(connection.close())
                # loop.run_until_complete(connection.close())
            except ValueError:
                pass
