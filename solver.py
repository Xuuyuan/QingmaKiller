"""作答决策: 依据本地题库、tikuAdapter 搜题结果与正确率决定提交内容"""
import random
import time

from config import options_list
from logger import logger
from tiku import search


def decide_answer(question, question_type, options, questions, now_right_rate, max_right_rate):
    """决定本题的作答, 返回 (should_submit, my_answer)。

    should_submit 为 False 表示跳过本题(防刷题题目/网络题库未找到答案/tikuAdapter不可用),
    相关日志与等待已在函数内部完成。
    """
    # 检测刷题题目
    if '刷题' in question or '请选择' in question:
        logger.warning('检测到防刷题题目, 自动跳过')
        return False, ''
    if question in questions:  # 题目已存在本地题库
        if now_right_rate > max_right_rate:  # 正确率过高
            logger.warning(f'该题目已存在本地题库中/正确率过高!  正确答案为 {questions[question]}, 将自动提交随机答案! ')
            if question_type == 0:
                my_answer = options_list[random.randint(0, len(options)-1)]
            else:
                my_answer = ''.join(random.sample(
                    options_list[:len(options)], 2))
        else:
            logger.info(f'该题目已存在本地题库中!  正确答案为 {questions[question]}, 将自动提交! ')
            my_answer = questions[question]
        return True, my_answer

    # 题目不存在本地题库中, 尝试从网络题库获取
    # my_answer = ''
    force_choose = False
    if question_type == 0:
        for d in range(len(options)):
            if '下都是' in options[d] or '上都是' in options[d]:  # 有出现对应文本的选项直接提交
                my_answer = options_list[d]
                force_choose = True
    if now_right_rate > max_right_rate:  # 正确率过高, 随机提交答案
        if question_type == 0:  # 单选题
            my_answer = options_list[random.randint(0, len(options)-1)]
        else:  # 多选题
            my_answer = ''.join(random.sample(
                options_list[:len(options)], 2))
        logger.warning('正确率过高, 将自动提交随机答案! ')
        force_choose = True
    elif not force_choose:
        my_answer = search(question, question_type, options)
        if my_answer is None:  # tikuAdapter不可用, 自动跳过本题
            return False, ''
    if my_answer == '':  # 网络题库未找到答案
        if now_right_rate > max_right_rate:  # 正确率高于保底正确率, 随机提交
            if question_type == 0:
                my_answer = options_list[random.randint(
                    0, len(options)-1)]
            else:
                my_answer = ''.join(random.sample(
                    options_list[:len(options)], 2))
            time.sleep(1)
        else:
            logger.warning('网络题库未找到答案, 本题跳过! ')
            time.sleep(3)
            return False, ''
    return True, my_answer
