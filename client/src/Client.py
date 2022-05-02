import json
import logging
import threading
from Events import Events
import requests
import websocket
import time
import Utils
import sys
from GocqApi import GocqApi
from ServerStatus import ServerStatus

Logger: logging.Logger = Utils.get_logger('Client')
Logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)


# 本体
class Client:
    VERSION: int = 3
    VERSION_STRING: str = '0.0.3'
    APP_NAME: str = 'KenkoGo - Client'

    _status = 0

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if value == self._status:
            return
        self._status = value

    # 状态操作器
    def status_operator(self, status=None):
        if status is not None and isinstance(status, int):
            self.status = status
        return self.status

    def __init__(self, config: dict, shared_objects: dict):
        self.config = config
        self.shared_objects = shared_objects

        # 打印版本信息
        Logger.info(self.APP_NAME)
        Logger.info(f'Version: {self.VERSION_STRING}')
        Logger.debug(f'Version Num: {self.VERSION}')

        # 读取配置文件
        self.config = Utils.YamlConfig('./config.yml')
        shared_objects['client_config'] = self.config

        self.server_port = self.config['server']['port']
        self.server_host = self.config['server']['host']
        self.server_token = self.config['server']['token']
        self.server_base_url = f'http://{self.server_host}:{self.server_port}'
        self.server_ws_url = f'ws://{self.server_host}:{self.server_port}/websocket'

        # 设置请求器
        self.r = requests.Session()
        self.r.headers.update({'token': self.server_token})
        shared_objects['r'] = self.r

        # 创建api
        self.gocq_api = GocqApi({
            'server_base_url': self.server_base_url,
        }, shared_objects)

        shared_objects['gocq_api'] = self.gocq_api

        # 设置事件
        self.events = Events({}, shared_objects)

        # 设置WebSocket
        self.thread_ws = None
        self.ws_app = websocket.WebSocketApp(
            url=self.server_ws_url,
            header={'token': self.server_token},
            on_message=self.event_message,
            on_open=self.event_open,
            on_error=self.event_error,
            on_close=self.event_close,
        )

    # 测试连接服务器
    def can_connect(self):
        try:
            response = self.r.get(f'{self.server_base_url}/status')
            if response.status_code != 200:
                raise ConnectionError('服务器连接失败')
            response = response.json()
            if response['code'] == 200:
                return True, None
            else:
                raise ConnectionError(response['msg'])
        except Exception as e:
            return False, e

    # 开始
    def start(self):
        while True:
            if self.shared_objects['time_to_exit'] is True:
                return
            result = self.can_connect()
            if result[0]:
                break
            Logger.error('服务器连接失败.')
            # Logger.debug(result[1])
            time.sleep(1)

        self.thread_ws = threading.Thread(
            target=self.ws_app.run_forever,
            daemon=True,
            kwargs={}
        )
        self.thread_ws.start()

    def stop(self):
        self.ws_app.close()
        if isinstance(self.thread_ws, threading.Thread):
            self.thread_ws.join()

    # 事件: 已连接
    def event_open(self, _):
        Logger.debug('WebSocket连接成功')
        self.events.on_connect()

    # 事件: 收到消息
    def event_message(self, _, message):
        # Logger.debug(f'收到消息: {message}')
        message = message.decode("utf-8").strip()
        message = json.loads(message)
        if message['post_type'] == 'server_event':
            if message['server_event_type'] == 'gocq_event':  # go-cqhttp 事件
                status: ServerStatus = ServerStatus(message['data']['code'])
                self.events.on_server_status_changed(status)
            elif message['server_event_type'] == 'server_event':  # 服务器事件
                data = message['data']
                if data == 'server_stopping':
                    Logger.warning('服务器正在停止')
        else:
            self.events.on_message(message)

    # 事件: 出错
    def event_error(self, _, error):
        Logger.error(f'WebSocket出错: {error}')

    # 事件: 关闭
    def event_close(self, _, code, reason):
        Logger.warning(f'WebSocket关闭: {code} {reason}')
        self.events.on_disconnect()
        self.start()
