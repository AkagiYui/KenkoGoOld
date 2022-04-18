import logging
import colorlog
import ruamel.yaml


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


class YamlConfig(dict):

    def __init__(self, path, auto_load=True, auto_save=True):
        super().__init__()
        self.data = {}
        self.path = path
        self.yaml_controller = ruamel.yaml.YAML()
        self.auto_save = auto_save
        if auto_load:
            self.load()

    def set_data(self, value):
        self.data = value

    def load(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            # self.data = yaml.safe_load(f)
            self.data = self.yaml_controller.load(f)

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
