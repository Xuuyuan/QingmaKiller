import os
import sys

from loguru import logger

# 日志文件固定生成在程序目录(打包为exe后为exe所在目录), 与main.py中的路径修正逻辑保持一致
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(application_path, 'qingmakiller.log')

logger.remove()
logger.add(sys.stderr, colorize=True)
logger.add(LOG_FILE, rotation='10 MB', level='TRACE', encoding='utf-8', enqueue=True)
