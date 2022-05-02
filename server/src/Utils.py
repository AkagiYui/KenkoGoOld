import json
import random
import logging
import inspect
import ctypes
import colorlog
from ServerStatus import ServerStatus
import os
import ruamel.yaml


def is_port_in_use(_port: int, _host='127.0.0.1'):
    import socket
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((_host, _port))
        return True
    except socket.error:
        return False
    finally:
        if s:
            s.close()


def get_free_port():
    result = random.randint(10000, 65535)
    while is_port_in_use(result):
        result = random.randint(10000, 65535)
    return result


def get_logger(name, log_level: int = logging.DEBUG) -> logging.Logger:
    res = logging.getLogger(name)
    res.setLevel(log_level)
    if not res.handlers:
        res.addHandler(_get_console_handler(name))
    return res


def _get_console_handler(name: str = '') -> logging.StreamHandler:
    log_colors_config = {
        'DEBUG': 'white',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
    console_handler = logging.StreamHandler()
    console_handler.setLevel(-1000)
    console_handler.setFormatter(colorlog.ColoredFormatter(
        fmt=f'%(log_color)s%(asctime)s [%(levelname)8s] [{name}] %(message)s',
        # datefmt='%Y-%m-%d %H:%M:%S',
        log_colors=log_colors_config
    ))
    return console_handler


def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)


# 获取自身ip
# https://www.zhihu.com/question/49036683/answer/1243217025
def get_self_ip():
    s = None
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    finally:
        if s:
            s.close()


# 获取公网ip
def get_public_ip(method: int = 0):
    import requests
    if method == 0:
        return requests.get('https://api.ipify.org').text
    elif method == 1:
        return requests.get('https://api.ip.sb/ip').text
    elif method == 2:
        return requests.get('http://myexternalip.com/raw').text
    elif method == 3:
        return requests.get('http://ip.42.pl/raw').text
    elif method == 4:
        return requests.get('http://myip.ipip.net/').text  # 非纯ip
    elif method == 5:
        return requests.get('http://ipecho.net/plain').text
    elif method == 6:
        return requests.get('http://hfsservice.rejetto.com/ip.php').text


class CustomJsonEncoder(json.JSONEncoder):
    def default(self, _object):
        if isinstance(_object, ServerStatus):
            return {
                'code': _object.value,
                'name': _object.name
            }
        return json.JSONEncoder.default(self, _object)


# HTTP响应体
class HttpResult:
    @classmethod
    def success(cls, data=None, msg='', code=200):
        return {'code': code, 'msg': msg, 'data': data}

    @classmethod
    def no_auth(cls, msg='身份未认证'):
        return {'code': 401, 'msg': msg, 'data': None}

    @classmethod
    def error(cls, status_code=404, msg=''):
        return {'code': status_code, 'msg': msg, 'data': None}


default_middleware = {
    'access-token': '1231',
    'filter': '',
    'rate-limit': {
        'enabled': False,
        'frequency': 1,
        'bucket': 1,
    },
}

default_gocq_config = {
    'account': {
        'uin': 0,
        'password': '',
        'encrypt': False,
        'status': 0,
        'relogin': {
            'delay': 3,
            'interval': 3,
            'max-times': 0,
        },
        'use-sso-address': True,
    },
    'heartbeat': {
        'interval': 5,
    },
    'message': {
        'post-format': 'string',
        'ignore-invalid-cqcode': False,
        'force-fragment': False,
        'fix-url': False,
        'proxy-rewrite': '',
        'report-self-message': True,
        'remove-reply-at': False,
        'extra-reply-data': False,
        'skip-mime-scan': False,
    },
    'output': {
        'log-level': 'error',  # 默认为warn, 支持 trace,debug,info,warn,error
        'log-aging': 30,
        'log-force-new': False,
        'debug': False,
    },
    'default-middlewares': default_middleware,
    'database': {
        'leveldb': {
            'enable': True,
        },
    },
    'servers': [
        {
            'http': {
                'host': '127.0.0.1',
                'port': 35700,
                'timeout': 5,
                'long-polling': {
                    'enabled': False,
                    'max-queue-size': 2000,
                },
                'middlewares': default_middleware,
                'post': [
                    {
                        'url': 'http://127.0.0.1:15700/gocq',
                        'secret': '',
                    }
                ],
            }
        },
        # {
        #     'ws': {
        #         'host': '0.0.0.0',
        #         'port': 6700,
        #         'middlewares': default_middleware,
        #     }
        # },
        # {
        #     'ws-reverse': {
        #         'universal': 'ws://127.0.0.1:36700',
        #         'reconnect-interval': 3000,
        #         'middlewares': default_middleware,
        #     }
        # }
    ],
}


class YamlConfig(dict):

    def __init__(self, path, auto_load=True, auto_save=True, auto_create=True):
        super().__init__()
        self.data = {}
        self.path = path
        self.yaml_controller = ruamel.yaml.YAML()
        self.auto_save = auto_save
        self.auto_create = auto_create
        if auto_load:
            self.load()

    def set_data(self, value):
        self.data = value

    def load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                self.data = self.yaml_controller.load(f)
        except FileNotFoundError:
            if self.auto_create:
                self.save()
            else:
                raise

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            self.yaml_controller.dump(self.data, f)

    def __getitem__(self, key):
        try:
            return self.data[key]
        except KeyError:
            return None

    def __setitem__(self, key, value):
        if value != self.data.get(key):
            self.data[key] = value
            if self.auto_save:
                self.save()

