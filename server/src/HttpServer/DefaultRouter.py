import threading
from fastapi import APIRouter
import hashlib
import hmac
import os
import sys
import time
from ServerStatus import ServerStatus
import Utils
from wsgiref.headers import Headers
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.requests import Request
from Utils import HttpResult as Result


Logger = Utils.get_logger('     HTTP')


# 计算hmac
def hash_mac(key: str, content: bytes, alg=hashlib.sha1):
    hmac_code = hmac.new(key.encode(), content, alg)
    return hmac_code.hexdigest()


class DefaultRouter:

    def __init__(self, config: dict, shared_objects: dict):
        self.config = config
        self.shared_objects = shared_objects
        self.gocq_config = shared_objects['gocq_config']
        self.server_config = shared_objects['server_config']
        self.http_app = shared_objects['http_app']
        self.websocket_manager = shared_objects['websocket_manager']
        self.status_operator = shared_objects['status_operator']

        self.router = APIRouter()

        # 接口: 发送二维码
        @self.http_app.get('/qrcode')
        async def api_qrcode():
            path = os.path.join(config['gocq_path_dir'], 'qrcode.png')
            if os.path.isfile(path):
                return FileResponse(path)
            else:
                return Response(status_code=405)

        # 接口: 处理GOCQ事件
        @self.http_app.post('/gocq')
        async def api_gocq(request: Request):
            # print(request)
            body_bytes = await request.body()
            header_token = request.headers['X-Signature']
            body_hash = hash_mac(config['gocq_secret'], body_bytes)
            if f'sha1={body_hash}' != header_token:
                Logger.warning('go-cqhttp 事件签名错误，请检查是否被篡改')

            body_json = await request.json()
            msg = body_json
            # print(msg)
            if msg['post_type'] == 'meta_event' and msg['meta_event_type'] == 'heartbeat':
                # Logger.debug('GOCQ发来的心跳')
                if self.status_operator() != ServerStatus.RUNNING:
                    self.status_operator(ServerStatus.RUNNING)
                return
            await self.websocket_manager.broadcast(body_bytes)
            return Result.success()

        # 接口: 启动go-cqhttp
        @self.http_app.post('/start')
        async def api_start(wait: bool = False):
            Logger.debug('尝试启动 go-cqhttp')
            if self.status_operator() != ServerStatus.STOPPED:
                Logger.warning('Already started, 已经启动了')
                return Result.success('Already started, 已经启动了', code=201)
            if wait:
                def start_thread():
                    time.sleep(5)
                    shared_objects['gocq_process'].start()
                threading.Thread(target=start_thread).start()
            else:
                shared_objects['gocq_process'].start()
            return Result.success('启动成功')

        # 接口: 服务器状态
        @self.http_app.get('/status')
        async def api_status():
            result = {
                'status': self.status_operator(),
                'gocq': {
                }
            }
            return Result.success(result)

        # 中间件: HTTP请求
        @self.http_app.middleware('http')
        async def middleware_http(request: Request, call_next):
            start_time = time.time()  # 收到http请求

            if not self.shared_objects['accept_connection']:
                response = JSONResponse(Result.error(405, 'server not running'))
            elif request.url.path in ['/gocq', '/qrcode']:
                response = await call_next(request)
            else:
                headers: Headers = request.headers
                try:
                    if config['token'] == '' or headers['token'] == config['token']:
                        response = await call_next(request)
                    else:
                        raise ValueError('token错误')
                except ValueError:
                    response = JSONResponse(Result.no_auth())

            process_time = time.time() - start_time  # 请求处理完毕
            response.headers['X-Process-Time'] = str(process_time)
            # Logger.debug(f'{request.method:.4s} {request.url.path} {response.status_code}')
            return response

        # 事件: HTTP服务器启动
        @self.http_app.on_event('startup')
        async def event_startup():
            self.shared_objects['accept_connection'] = True
            Logger.info(f'服务器已在 http://{self.server_config["host"]}:{self.server_config["port"]["http"]} 启动')
            Logger.debug(f'调试地址: http://{Utils.get_self_ip()}:{self.server_config["port"]["http"]}')
            if '--auto-start' in sys.argv:
                # time.sleep(1)
                # threading.Thread(target=await api_start).start()
                # await asyncio.sleep(5)
                # asyncio.get_event_loop().create_task(asyncio.sleep(5))
                # asyncio.get_event_loop().create_task(api_start())
                await api_start(True)

        # 事件: HTTP服务器关闭
        @self.http_app.on_event('shutdown')
        async def event_shutdown():
            # Logger.info('服务器将被关闭')
            pass

        # 接口: WebSocket请求
        @self.http_app.websocket('/websocket')
        async def api_websocket(websocket: WebSocket):

            if not self.shared_objects['accept_connection']:
                await websocket.close(405)
                return

            headers = websocket.headers
            try:
                if config['token'] != '' and headers['token'] != config['token']:
                    raise KeyError('token错误')
            except KeyError:
                await websocket.close(401)
                Logger.warning(f'{websocket.client.host}:{websocket.client.port} 没有权限，WebSocket被拒绝连接')
                return

            await self.websocket_manager.connect(websocket)
            try:
                while True:
                    _ = await websocket.receive_text()
                    # print(data)
                    time.sleep(0.1)
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket)
