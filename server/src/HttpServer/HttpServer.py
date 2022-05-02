import sys
import threading
from typing import Union
from .DefaultRouter import DefaultRouter
import Utils
import logging
from .WebsocketManager import WebsocketManager
import uvicorn as uvicorn
from fastapi import FastAPI
from .GocqApi import GocqApi

Logger = Utils.get_logger('     HTTP')
Logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)


# HTTP服务器
class HttpServer:

    def __init__(self, config: dict, shared_objects: dict = None):
        self.config = config
        self.shared_objects = shared_objects
        self.gocq_config = shared_objects['gocq_config']
        self.server_config = shared_objects['server_config']

        self.port = self.server_config['port']['http']
        self.host = self.server_config['host']

        # 检查HTTP服务器端口占用
        if Utils.is_port_in_use(self.port):
            if not self.server_config['port']['auto_change']:
                raise SystemError(f'端口 {self.port} 被占用！')
            _port_http = Utils.get_free_port()
            Logger.warning(f'端口 {self.port} 被占用，已尝试修改为{_port_http}！')
            self.server_config['port']['http'] = _port_http
            self.server_config.save()
            self.port = _port_http

        self.websocket_manager = WebsocketManager()
        self.shared_objects['websocket_manager'] = self.websocket_manager
        self.thread_http: Union[threading.Thread, None] = None
        shared_objects['accept_connection'] = False

        self.app = FastAPI(docs_url=None, redoc_url=None)
        self.shared_objects['http_app'] = self.app

        self.default_router = DefaultRouter({
            'gocq_secret': config['gocq_secret'],
            'token': config['token'],
            'gocq_path_dir': config['gocq_path_dir'],
        }, shared_objects)
        self.app.include_router(self.default_router.router, prefix='')

        self.gocq_api = GocqApi({
            'access_token': config['gocq_access_token'],
        }, shared_objects)
        self.app.include_router(self.gocq_api.router, prefix='/api')

    def start(self):
        self.thread_http = threading.Thread(
            target=uvicorn.run,
            daemon=True,
            kwargs={
                'app': self.app,
                'host': self.host,
                'port': self.port,
                'log_level': 'error' if '--debug' in sys.argv else 'critical',
                'workers': 1
            }
        )
        self.thread_http.start()

    def stop(self):
        self.shared_objects['accept_connection'] = False
        Logger.debug('服务器关闭中')
        self.websocket_manager.close_all()
        Utils.stop_thread(self.thread_http)
        Logger.debug('服务器已关闭')
