# -*- coding: utf-8 -*-
#br 这个是从server.py过来的
import logging
import sys

from loguru import logger


def __exception_handle(e_type, e_value, e_traceback):
    if issubclass(e_type, KeyboardInterrupt):
        print('\nBye...')
        sys.exit(0)

    sys.__excepthook__(e_type, e_value, e_traceback)


class __InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def hook_except_handle():
    sys.excepthook = __exception_handle
    # sys.excepthook` 是一个系统级别的异常处理钩子函数，只有在程序抛出未被捕获的异常时才会被调用。当程序出现未捕获的异常时，Python 解释器将异常信息传递给 `sys.excepthook` 函数进行处理。如果没有设置该函数，则使用默认的异常处理方式。2023-5-11

def hook_logging(**kwargs):
    logging.basicConfig(handlers=[__InterceptHandler()], **kwargs)
