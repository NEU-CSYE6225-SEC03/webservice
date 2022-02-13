import logging
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler

from tool.Config import Config


class _Logger(logging.Logger):

    def __init__(self, level, format, filename=None):

        super().__init__(__name__)

        # 设置收集器级别
        self.setLevel(level)

        # 初始化format，设置格式
        fmt = logging.Formatter(format)

        # 初始化处理器
        if filename is not None:
            # file_handler = logging.FileHandler(filename)
            # handler = RotatingFileHandler(filename, maxBytes=1024000, backupCount=10)
            file_handler = TimedRotatingFileHandler(filename, when="D", interval=1, backupCount=15, encoding="UTF-8",
                                                    delay=False, utc=True)
            # 设置handler级别
            file_handler.setLevel(level)
            # 添加handler
            self.addHandler(file_handler)
            # 添加日志处理器
            file_handler.setFormatter(fmt)
        else:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(level)
            self.addHandler(stream_handler)
            stream_handler.setFormatter(fmt)


class Logger(object):
    __config = Config.getInstance()

    __logger = _Logger(level=__config['LOG_LEVEL'], format=__config['LOG_FORMAT'], filename=__config['LOG_FILENAME'])

    @staticmethod
    def getInstance():
        return Logger.__logger
