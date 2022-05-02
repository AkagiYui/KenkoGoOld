import os
import re
import subprocess
import sys
import threading
from typing import Union
from GocqMessage import GocqMessage
import Utils
from ServerStatus import ServerStatus
import logging

Logger2 = Utils.get_logger('go-cqhttp')
Logger2.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)
Logger = Utils.get_logger('  Process')
Logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)


# go-cqhttp子进程
class GocqProcess:
    gocq_name_bin = 'go-cqhttp'
    gocq_port_api = 35700

    def __init__(self, config: dict, shared_objects: dict):
        self.config = config
        self.shared_objects = shared_objects
        self.gocq_config = shared_objects['gocq_config']
        self.server_config = shared_objects['server_config']
        self.status_operator = shared_objects['status_operator']
        self.websocket_manager = shared_objects['websocket_manager']

        self.gocq_path_dir = config['gocq_path_dir']
        self.gocq_name_bin = config['gocq_name_bin']
        self.gocq_path_bin = os.path.join(self.gocq_path_dir, self.gocq_name_bin)

        self.process: Union[subprocess.Popen, None] = None
        self.thread_read_output: Union[threading.Thread, None] = None

    def start(self):
        self.status_operator(ServerStatus.STARTING)
        self.refresh_config()
        self.shared_objects['http_server'].gocq_api.refresh_config()
        self.process = subprocess.Popen(
            args=f'{self.gocq_path_bin} -faststart',
            cwd=self.gocq_path_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8'
        )
        self.thread_read_output = threading.Thread(target=self._read_output)
        self.thread_read_output.start()

    def _read_output(self):
        while self.process.poll() is None:
            output_list = self.process.stdout.readlines(1)
            if not output_list:
                continue
            text_output: str = output_list[0]
            text_output = text_output.strip()

            # Logger.warning(f'%d {text_output}', 1)

            # 删除颜色标签
            color_regex = re.compile(r'\x1b\[\d+(;\d+)?m')
            match_result = re.match(color_regex, text_output)
            # Logger.warning(f'%d {text_output}', 2)
            if not match_result:
                continue
            text_output = re.sub(color_regex, '', text_output).strip()
            # Logger.warning(f'%d {text_output}', 3)

            # 删除日期与日志等级
            match_result = re.match(r'\[\d+-\d+-\d+ \d+:\d+:\d+] \[[A-Z]+\]: ', text_output)
            # Logger.warning(f'%d {text_output}', 4)
            if not match_result:
                continue
            # Logger.warning(f'%d {text_output}', 5)
            if match_result.end() == len(text_output):
                continue
            # Logger.warning(f'%d {text_output}', 6)
            text_output = text_output[match_result.end():].strip()

            # Logger.warning(f'%d {text_output}', 7)

            if not text_output:
                continue

            if not text_output.startswith('上报 Event 数据'):
                Logger2.debug(text_output)

            if text_output.startswith('开始尝试登录并同步消息'):
                pass
            elif text_output.startswith('检查更新完成. 当前已运行最新版本'):
                pass
            elif text_output.startswith('上报 Event 数据'):
                pass
            elif text_output.startswith('资源初始化完成, 开始处理信息'):
                pass
            elif text_output.startswith('当前版本:'):
                pass
            elif text_output.startswith('使用协议: '):
                pass
            elif text_output.startswith('将使用 device.json 内的设备信息运行Bot.'):
                pass
            elif text_output.startswith('账号密码未配置, 将使用二维码登录'):
                self.status_operator(ServerStatus.GETTING_QRCODE)
            elif text_output.startswith('扫码成功, 请在手机端确认登录.'):
                self.status_operator(ServerStatus.WAIT_FOR_CONFIRM)
            elif text_output.startswith('恢复会话失败: Packet timed out , 尝试使用正常流程登录'):
                Logger.warning('恢复登录失败，请检查是否频繁登录！')
            elif text_output.startswith('Bot 账号在客户端'):
                Logger.info(text_output)
            elif text_output.startswith('Protocol -> '):
                text_output = text_output.removeprefix('Protocol -> ')
                if text_output.startswith('unexpected disconnect: '):
                    text_output = text_output.removeprefix('unexpected disconnect: ')
                    Logger.warning(f'预期外的断线: {text_output}')
                elif text_output.startswith('register client failed: Packet timed out'):
                    Logger.warning('注册客户端失败: 数据包超时')
                elif text_output.startswith('connect server error: dial tcp error: '):
                    Logger.warning('服务器连接失败')
                    self.status_operator(ServerStatus.OFFLINE)
                elif text_output.startswith('connect to server'):
                    self.status_operator(ServerStatus.CONNECTING_TO_TENCENT)
                elif text_output.startswith('resolve long message server error'):
                    Logger.warning('长消息服务器延迟测试失败')
                elif text_output.startswith('test long message server response latency error'):
                    Logger.warning('长消息服务器响应延迟测试失败,')
            elif text_output.startswith('Bot已离线: '):
                text_output = text_output.removeprefix('Bot已离线: ')
                Logger.warning(f'Bot已离线: {text_output}')
            elif text_output.startswith('扫码登录无法恢复会话'):
                Logger.error('快速重连失败，扫码登录无法恢复会话，go-cqhttp将重启')
                self.restart()
            elif text_output.startswith('登录时发生致命错误: '):
                text_output = text_output.removeprefix('登录时发生致命错误: ')
                if text_output.startswith('fetch qrcode error: Packet timed out'):
                    Logger.warning('二维码获取失败，等待重新生成二维码')
                    self.status_operator(ServerStatus.FAIL_TO_FETCH_QRCODE)
                elif text_output.startswith('not found error correction level and mask'):
                    self.status_operator(ServerStatus.CONNECT_FAILED)
                    self.restart()
                else:
                    Logger.error(text_output)
                    self.status_operator(ServerStatus.CONNECT_FAILED)
                    self.restart()
            elif text_output.startswith('请使用手机QQ扫描二维码 (qrcode.png)'):
                self.status_operator(ServerStatus.WAIT_FOR_SCAN)
                Logger.info(f'等待扫描二维码，请使用登录了 {self.shared_objects["server_config"]["account"]["uin"]} 的手机QQ扫描二维码')
                Logger.debug(f'二维码URL: http://127.0.0.1:{self.shared_objects["server_config"]["port"]["http"]}/qrcode')
            elif text_output.startswith('扫码被用户取消.'):
                self.status_operator(ServerStatus.QRCODE_CANCELED)
                self.restart()
            elif text_output.startswith('二维码过期'):
                self.status_operator(ServerStatus.QRCODE_EXPIRED)
                Logger.warning('二维码已过期，等待重新生成二维码')
                self.restart()
            elif text_output.startswith('登录成功 欢迎使用:'):
                self.status_operator(ServerStatus.LOGGED_IN)
                Logger.info('已登录，正在等待消息上报')
            elif text_output.startswith('检查更新失败: '):
                text_output = text_output.removeprefix('检查更新失败: ')
                # Get "https://api.github.com/repos/Mrs4s/go-cqhttp/releases/latest"
                # : dial tcp: lookup api.github.com: no such host
                Logger.warning(f'检查更新失败，请检查github访问是否通畅。{text_output}')
            elif text_output.startswith('快速重连失败'):
                text_output = text_output.removeprefix('快速重连失败').strip()
                if text_output.startswith(', 扫码登录无法恢复会话.'):
                    Logger.warning('重连失败，go-cqhttp将重启')
                    self.restart()
            elif text_output.startswith('群消息发送失败: '):
                self.websocket_manager.broadcast_sync(
                    GocqMessage.server_event('message_event', text_output)
                )
                text_output = text_output.removeprefix('群消息发送失败: ')
                Logger.warning(f'群消息发送失败: {text_output}')
            elif text_output.startswith('频道消息发送失败: '):
                self.websocket_manager.broadcast_sync(
                    GocqMessage.server_event('message_event', text_output)
                )
                text_output = text_output.removeprefix('频道消息发送失败: ')
                Logger.warning(f'频道消息发送失败: {text_output}')

    def stop(self):
        if self.status_operator() == ServerStatus.STOPPING:
            return
        if self.status_operator() != ServerStatus.STOPPING:
            Logger.debug('正在停止 go-cqhttp')
            self.status_operator(ServerStatus.STOPPING)
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.status_operator(ServerStatus.STOPPED)

    def restart(self):
        self.stop()
        self.start()

    # 重置go-cqhttp配置文件
    def refresh_config(self):
        self.gocq_config['account']['uin'] = self.config['gocq_uin']
        self.gocq_config['default-middlewares']['access-token'] = self.config['gocq_access_token']
        for _server in self.gocq_config['servers']:
            if 'http' not in _server.keys():
                continue
            __server = _server['http']
            if Utils.is_port_in_use(int(__server['port'])):
                _gocq_port_api = Utils.get_free_port()
                Logger2.warning(f'api 端口 {__server["port"]} 被占用，已尝试修改为{_gocq_port_api}！')
                __server['port'] = _gocq_port_api

            post_config = __server['post'][0]
            post_config['secret'] = self.config['gocq_secret']
            post_config['url'] = f'http://127.0.0.1:{self.shared_objects["server_config"]["port"]["http"]}/gocq'
            # _server['http']['post'][0] = post_config
            break

        self.gocq_config.save()
