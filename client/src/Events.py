import logging
import Utils
import sys
from GocqApi import GocqApi
from ServerStatus import ServerStatus

Logger: logging.Logger = Utils.get_logger('Events')
Logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)


class Events:
    def __init__(self, config: dict, shared_objects: dict):
        self.config = config
        self.shared_objects = shared_objects
        self.gocq_api: GocqApi = shared_objects['gocq_api']
        self.client_config = shared_objects['client_config']

    def on_server_status_changed(self, status: ServerStatus):
        Logger.info(f'服务器状态改变: {status}')
        if status == ServerStatus.WAIT_FOR_SCAN:
            url = self.client_config['server']
            url = f'http://{url["host"]}:{url["port"]}/qrcode'
            Logger.info(f'等待扫描二维码: {url}')

    def on_connect(self):
        Logger.info('服务器连接成功')

    def on_disconnect(self):
        Logger.warning('服务器断开连接')

    def on_message(self, message: dict):
        Logger.debug(f'收到消息: {message}')
        try:
            if message['user_id'] == 2221110033 and message['raw_message'] == 'testt':
                self.gocq_api.send_group_msg(message['group_id'], '哈哈')
        except KeyError:
            pass

