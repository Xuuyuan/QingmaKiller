import os
import sys

from loguru import logger

from paths import get_app_dir

# 日志文件固定生成在程序目录(打包为exe后为exe所在目录)
LOG_FILE = os.path.join(get_app_dir(), 'qingmakiller.log')

logger.remove()
logger.add(sys.stderr, colorize=True)
logger.add(LOG_FILE, rotation='10 MB', level='TRACE', encoding='utf-8', enqueue=True)
