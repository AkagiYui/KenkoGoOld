import os
import subprocess
import sys
import threading
from typing import Union
import Utils
from ServerStatus import ServerStatus
import logging

Logger = Utils.get_logger('go-cqhttp')
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
            text_output = self.process.stdout.readline().strip()
            if text_output.find(']:') != -1:
                text_output = text_output[text_output.find(']:') + 2:].strip()
            if not text_output:
                continue
            elif '账号密码未配置, 将使用二维码登录' in text_output:
                self.status_operator(ServerStatus.GETTING_QRCODE)
            elif '开始尝试登录并同步消息' in text_output:
                pass
            elif 'Protocol -> connect server error: dial tcp error: ' in text_output:
                Logger.warning('服务器连接失败')
                self.status_operator(ServerStatus.OFFLINE)
            elif 'Protocol -> unexpected disconnect: ' in text_output:
                text_output = text_output[len('Protocol -> unexpected disconnect: '):].strip()
                Logger.warning(f'预期外的断线: {text_output}')
            elif 'Protocol -> register client failed: Packet timed out' in text_output:
                Logger.warning(f'注册客户端失败: 包超时')
            elif 'Bot已离线: ' in text_output:
                text_output = text_output[len('Bot已离线: '):].strip()
                Logger.warning(f'Bot已离线: {text_output}')
            elif '扫码登录无法恢复会话' in text_output:
                Logger.error('快速重连失败，扫码登录无法恢复会话，go-cqhttp将重启')
                self.restart()
            elif 'Protocol -> connect to server' in text_output:
                self.status_operator(ServerStatus.CONNECTING_TO_TENCENT)
            # elif '登录时发生致命错误: not found error correction level and mask' in text_output:
            #     self.status_operator(ServerStatus.CONNECT_FAILED)
            elif '登录时发生致命错误: ' in text_output:
                self.status_operator(ServerStatus.CONNECT_FAILED)
                Logger.error(text_output)
                self.restart()
            elif '登录时发生致命错误: fetch qrcode error: Packet timed out' in text_output:
                Logger.warning('[GOCQ] 二维码获取失败，等待重新生成二维码')
                self.status_operator(ServerStatus.FAIL_TO_FETCH_QRCODE)
                self.restart()
            elif '请使用手机QQ扫描二维码 (qrcode.png)' in text_output:
                self.status_operator(ServerStatus.WAIT_FOR_SCAN)
                Logger.info(f'等待扫描二维码，请使用登录了 {self.shared_objects["server_config"]["account"]["uin"]} 的手机QQ扫描二维码')
            elif '二维码过期' in text_output:
                Logger.warning('二维码已过期，等待重新生成二维码')
                self.status_operator(ServerStatus.QRCODE_EXPIRED)
                self.restart()
            elif '登录成功 欢迎使用:' in text_output:
                Logger.info('已登录，正在等待消息上报')
                self.status_operator(ServerStatus.LOGGED_IN)
            elif '检查更新失败: Get "https://api.github.com/repos/Mrs4s/go-cqhttp/releases/latest":' \
                 ' dial tcp: lookup api.github.com: no such host' in text_output:
                Logger.debug('检查更新失败，请检查github访问是否通畅')
            elif '资源初始化完成, 开始处理信息' in text_output:
                # self.status_operator(ServerStatus.LOGGED_IN)
                Logger.info('资源初始化完成, 开始处理信息')
            elif '恢复会话失败: Packet timed out , 尝试使用正常流程登录' in text_output:
                Logger.warning('登录失败，请检查是否频繁登录！')
            elif '上报 Event 数据到' in text_output and '失败' in text_output:
                if 'wsarecv: An existing connection was forcibly closed by the remote host.' in text_output:
                    pass
                elif 'EOF' in text_output:
                    pass
            elif '警告' in text_output:
                if '可能出现消息丢失/延迟或频繁掉线等情况, 请检查本地网络状态' in text_output:
                    Logger.warning(text_output)

            elif 'Bot 账号在客户端' in text_output:
                Logger.info(f'{text_output}')
            else:
                Logger.debug(f'{text_output}')

    def stop(self):
        if self.status_operator() == ServerStatus.STOPPING:
            return
        if self.status_operator() != ServerStatus.STOPPING:
            Logger.debug('正在停止 go-cqhttp')
            self.status_operator(ServerStatus.STOPPING)
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
                Logger.warning(f'api 端口 {__server["port"]} 被占用，已尝试修改为{_gocq_port_api}！')
                __server['port'] = _gocq_port_api

            post_config = __server['post'][0]
            post_config['secret'] = self.config['gocq_secret']
            post_config['url'] = f'http://127.0.0.1:{self.shared_objects["server_config"]["port"]["http"]}/gocq'
            # _server['http']['post'][0] = post_config
            break

        self.gocq_config.save()
