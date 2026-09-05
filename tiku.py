"""tikuAdapter 本地搜题服务(localhost:8060)客户端"""
import json
import random
import time

import requests

from config import headers_tiku, tiku_adapter_url
from logger import logger


def search(question, question_type, options):  # 搜题并按题型规整答案, tikuAdapter不可用时返回None
    try:
        req_tiku = requests.post(tiku_adapter_url, json={
                                 "question": question, "type": question_type, "options": options}, headers=headers_tiku)
    except requests.exceptions.ConnectionError:
        logger.error('无法连接到tikuAdapter, 自动跳过本题, 请先启动tikuAdapter再运行本程序! ')
        time.sleep(random.randint(4, 10))
        return None
    except Exception as e:
        logger.error(f'连接tikuAdapter时发现错误, 自动跳过本题: {e}')
        time.sleep(random.randint(4, 10))
        return None
    res_tiku = json.loads(req_tiku.text)
    my_answer = res_tiku['answer']['answerKeyText']
    if question_type == 0 and len(my_answer) > 1:  # 避免单选题提交多选
        my_answer = my_answer[0]
    # 避免多选题提交单选
    elif question_type == 1 and len(my_answer) == 1:
        my_answer = ''

    if question_type == 1:  # 多选题去重
        my_answer = ''.join(set(my_answer))
    logger.info(f'网络题库搜索结果: {my_answer}')
    return my_answer
