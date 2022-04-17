import logging
import Utils
import sys
from GocqApi import GocqApi

Logger: logging.Logger = Utils.get_logger('Events')
Logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)


class Events:
    def __init__(self, config: dict, shared_objects: dict):
        self.config = config
        self.shared_objects = shared_objects
        self.gocq_api: GocqApi = shared_objects['gocq_api']

    def on_open(self):
        Logger.debug('WebSocket连接成功')

    def on_message(self, message: dict):
        Logger.debug(f'收到消息: {message}')
        try:
            if message['group_id'] == 1234567890 and message['raw_message'] == 'ttest':
                self.gocq_api.send_group_msg(1234567890, '哈哈')
        except Exception as e:
            pass

    def on_close(self, code, reason):
        Logger.debug(f'WebSocket关闭: {code} {reason}')

    def on_error(self, error):
        Logger.debug(f'WebSocket错误: {error}')
