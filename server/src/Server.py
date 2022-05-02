import asyncio
import time
import os
import platform
import re
import sys
import tarfile
import zipfile
import requests
import Utils
from ServerStatus import ServerStatus
from GocqProcess.GocqProcess import GocqProcess
from HttpServer.HttpServer import HttpServer
import logging
from GocqMessage import GocqMessage

Logger: logging.Logger = Utils.get_logger('   Server')
Logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)

# import nest_asyncio
# nest_asyncio.apply()


# 本体
class Server:
    VERSION: int = 6
    VERSION_STRING: str = '0.0.6'
    APP_NAME: str = 'KenkoGo - Server'

    _status: ServerStatus = ServerStatus.STOPPED

    @property
    def status(self) -> ServerStatus:
        return self._status

    @status.setter
    def status(self, value: ServerStatus):
        if value == self._status:
            return
        self._status = value
        Logger.info(f'go-cqhttp 状态改变为 {value.name}')

        # 推送状态改变事件
        # try:
        #     loop = asyncio.get_running_loop()
        #     loop = loop.create_task
        # except RuntimeError:
        #     loop = asyncio.new_event_loop()
        #     loop = loop.run_until_complete
        # loop(self.http_server.websocket_manager.broadcast(
        #     GocqMessage.server_event('gocq_event', value)
        # ))
        self.http_server.websocket_manager.broadcast_sync(
            GocqMessage.server_event('gocq_event', value)
        )

    # 状态操作器
    def status_operator(self, status: ServerStatus = None) -> ServerStatus:
        if status is not None and isinstance(status, ServerStatus):
            self.status = status
        return self.status

    def __init__(self, config: dict, shared_objects: dict):
        self.config = config
        self.shared_objects = shared_objects

        # 打印版本信息
        Logger.info(self.APP_NAME)
        Logger.info(f'Version: {self.VERSION_STRING}')
        Logger.debug(f'Version Num: {self.VERSION}')

        # 检查系统
        self.is_win = platform.system().strip().lower().startswith('win')
        is_linux = platform.system().strip().lower().startswith('lin')
        if not self.is_win and not is_linux:
            raise SystemError('Unsupported OS, 不支持的操作系统')
        self.flag_arch = platform.machine().strip().lower()
        if self.flag_arch.startswith('x86_64') or self.flag_arch.startswith('amd64'):
            self.flag_arch = 'amd64'
        else:
            raise SystemError('Unsupported architecture, 不支持的操作系统')

        # 读取配置文件
        self.config = Utils.YamlConfig('./config.yml')

        # 定义一些常量
        gocq_path_dir = './gocq'
        gocq_secret = 'eh182yg909du1uas'
        gocq_access_token = 'jdo1902d18092yhf'
        gocq_path_config = os.path.join(gocq_path_dir, 'config.yml')
        gocq_name_bin = 'go-cqhttp' + (('.exe' if self.is_win else ''))
        gocq_path_bin = os.path.join(gocq_path_dir, gocq_name_bin)

        # 检查go-cqhttp的文件情况
        if not os.path.isdir(gocq_path_dir):
            Logger.debug('go-cqhttp 目录不存在，正在创建')
            os.mkdir(gocq_path_dir)
        if not os.path.isfile(gocq_path_config):
            Logger.debug('go-cqhttp 配置文件不存在，正在创建')
            _config = Utils.YamlConfig(gocq_path_config)
            _config.set_data(Utils.default_gocq_config.copy())
            _config['account']['uin'] = int(self.config['account']['uin'])
            _config['default-middlewares']['access-token'] = gocq_access_token
            for server in _config['servers']:
                if 'http' not in server.keys():
                    continue
                _server = server['http']
                _server['post'][0]['secret'] = gocq_secret
            _config.save()
            self.gocq_config = _config
        else:
            self.gocq_config = Utils.YamlConfig(gocq_path_config)

        if not os.path.isfile(gocq_path_bin):
            Logger.info('go-cqhttp 可执行文件不存在，尝试下载')
            flag_system = 'windows' if self.is_win else 'linux'
            text_re = f'{flag_system}.*{self.flag_arch}.*'
            if flag_system == 'linux':
                text_re += 'tar.gz'
            elif flag_system == 'windows':
                text_re += 'zip'

            release_url = 'https://api.github.com/repos/Mrs4s/go-cqhttp/releases'
            release_content = requests.get(release_url).json()

            gocq_version = self.config['gocq']['version']
            for release in release_content:
                if release['tag_name'].find(gocq_version) != -1:
                    release_content = release['assets']
                    break
            else:
                raise ValueError('Version not found, 版本未找到')

            for asset in release_content:
                if re.search(text_re, asset['name']):
                    release_url = asset['browser_download_url']
                    break
            else:
                raise ValueError('Architecture not found, 版本中未找到该系统架构')

            try:
                release_content = requests.get(release_url, stream=True)
            except requests.exceptions.ConnectionError as e:
                # Logger.error('下载失败，请检查网络连接')
                raise SystemError(f'go-cqhttp 下载失败，请检查与 GitHub 的连接，或手动下载可执行文件到 {gocq_path_dir} 目录并命名为 {gocq_name_bin}') from e

            gocq_path_compressed = gocq_path_bin + ('.zip' if self.is_win else '.tar.gz')
            with open(gocq_path_compressed, 'wb') as __f:
                for chunk in release_content.iter_content(chunk_size=1024):
                    if chunk:
                        __f.write(chunk)

            if self.is_win:
                if not zipfile.is_zipfile(gocq_path_compressed):
                    raise TypeError('Downloaded file is not a zip file, 下载的文件不是zip文件')
                with zipfile.ZipFile(gocq_path_compressed, 'r') as f:
                    if 'go-cqhttp.exe' not in f.namelist():
                        raise ValueError('File not found in compressed file, 压缩文件中未找到可执行文件')
                    f.extract('go-cqhttp.exe', gocq_path_dir)
                    os.rename(os.path.join(gocq_path_dir, 'go-cqhttp.exe'), gocq_path_bin)
            else:
                if not tarfile.is_tarfile(gocq_path_compressed):
                    raise TypeError('Downloaded file is not a tar file, 下载的文件不是tar文件')
                with tarfile.open(gocq_path_compressed, 'r:gz') as f:
                    if 'go-cqhttp' not in f.getnames():
                        raise ValueError('File not found in compressed file, 压缩文件中未找到可执行文件')
                    f.extract('go-cqhttp', gocq_path_dir)
                    os.rename(os.path.join(gocq_path_dir, 'go-cqhttp'), gocq_path_bin)
            os.remove(gocq_path_compressed)

        shared_objects['status_operator'] = self.status_operator
        shared_objects['server_config'] = self.config
        shared_objects['gocq_config'] = self.gocq_config

        self.http_server = HttpServer({
            'gocq_path_dir': gocq_path_dir,
            'gocq_access_token': gocq_access_token,
            'gocq_secret': gocq_secret,
            'token': self.config['token'],
            'auto_change_port': self.config['port']['auto_change'],
        }, shared_objects)
        shared_objects['http_server'] = self.http_server

        self.gocq_process = GocqProcess({
            'gocq_path_dir': gocq_path_dir,
            'gocq_name_bin': gocq_name_bin,
            'gocq_secret': gocq_secret,
            'gocq_access_token': gocq_access_token,
            'gocq_uin': self.config['account']['uin'],
        }, shared_objects)
        shared_objects['gocq_process'] = self.gocq_process

    def start(self):
        self.http_server.start()

    def stop(self):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            self.http_server.websocket_manager.broadcast(
                GocqMessage.server_event('server_event', 'server_stopping')
            )
        )
        Logger.debug('正在停止 KenkoGoServer')
        if self.status != ServerStatus.STOPPED:
            self.gocq_process.stop()
            time.sleep(0.1)
        self.http_server.stop()
