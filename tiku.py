"""tikuAdapter 本地搜题服务(localhost:8060)客户端"""
import json

import requests

from config import headers_tiku, tiku_adapter_base, tiku_adapter_url
from logger import logger


def adapter_alive(timeout=2):  # 探测本地搜题服务是否在运行
    try:
        requests.get(tiku_adapter_base, timeout=timeout)
        return True
    except requests.RequestException:
        return False


def search(question, question_type, options):  # 搜题并按题型规整答案, tikuAdapter不可用或响应异常时返回None
    try:
        req_tiku = requests.post(tiku_adapter_url, json={
                                 "question": question, "type": question_type, "options": options},
                                 headers=headers_tiku, timeout=30)
    except requests.exceptions.ConnectionError:
        logger.error('无法连接到tikuAdapter, 自动跳过本题, 请先启动tikuAdapter再运行本程序! ')
        return None
    except Exception as e:
        logger.error(f'连接tikuAdapter时发现错误, 自动跳过本题: {e}')
        return None
    try:  # 响应为空/非JSON或结构异常(如服务正在退出、未配置题库)时跳过本题, 避免中断整轮运行
        my_answer = json.loads(req_tiku.text)['answer']['answerKeyText']
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.error(f'tikuAdapter响应异常, 自动跳过本题! HTTP {req_tiku.status_code}: {req_tiku.text[:200]}')
        return None
    if not my_answer:  # 网络题库未命中
        return ''
    if question_type == 0 and len(my_answer) > 1:  # 避免单选题提交多选
        my_answer = my_answer[0]
    # 避免多选题提交单选
    elif question_type == 1 and len(my_answer) == 1:
        my_answer = ''

    if question_type == 1:  # 多选题去重
        my_answer = ''.join(set(my_answer))
    logger.info(f'网络题库搜索结果: {my_answer}')
    return my_answer
