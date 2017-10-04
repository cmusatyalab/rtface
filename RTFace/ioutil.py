import socket
import time
import logging
import sys
import os
import shutil
from demo_config import Config


def getLogger(name):
    logger = logging.getLogger(name)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)
    if Config.DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger


def remove_dir(dir_name):
    shutil.rmtree(dir_name, ignore_errors=True)


def create_dir(dir_name):
    if '~' in dir_name:
        directory = os.path.expanduser(dir_name)
    if not os.path.exists(directory):
        print 'create dir: ' + directory
        os.makedirs(directory)


def timeit(method):
    LOG = getLogger(__name__)

    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()

        if Config.LOG_TIME:
            LOG.debug('%r %.1f ms' %
                      (method.__name__, (te - ts) * 1000))
        return result
    return timed


def get_unused_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    addr, port = s.getsockname()
    s.close()
    return port
