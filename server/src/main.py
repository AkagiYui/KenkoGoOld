import logging
import signal
import sys
import time
from typing import Union
import Utils
from Server import Server


# 信号响应处理器
def signal_handler(sign, _):
    if sign in [signal.SIGINT, signal.SIGTERM]:
        Logger.debug('收到退出信号，正在退出...')
        global time_to_exit
        time_to_exit = True


if __name__ == '__main__':
    if sys.gettrace() is not None:
        print('Debug Mode')

    # 创建日志打印器
    Logger: logging.Logger = Utils.get_logger('     main')
    Logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.INFO)

    time_to_exit = False
    shared_objects = {
        'exit_code': 0,
    }

    # 设置信号响应
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    server: Union[Server, None] = None
    try:
        server: Server = Server({}, shared_objects)
    except SystemError as e:
        time_to_exit = True
        shared_objects['exit_code'] = 1
        Logger.error(e)
    except ValueError as e:
        time_to_exit = True
        shared_objects['exit_code'] = 2
        Logger.error(e)
    else:
        server.start()

    if time_to_exit:
        Logger.error('Server 出现异常，正在退出...')

    while not time_to_exit:
        time.sleep(0)

    if isinstance(server, Server):
        server.stop()

    Logger.info('程序已退出，欢迎下次使用')
    sys.exit(shared_objects['exit_code'])
