"""作答决策: 依据本地题库、tikuAdapter 搜题结果与正确率决定提交内容"""
import random

from config import options_list
from logger import logger
from tiku import search


def _random_answer(question_type, option_count):  # 正确率过高时生成的随机答案
    if question_type == 0:  # 单选题
        return options_list[random.randint(0, option_count - 1)]
    return ''.join(random.sample(options_list[:option_count], 2))  # 多选题


def decide_answer(question, question_type, options, questions, now_right_rate, max_right_rate):
    """决定本题的作答, 返回 (should_submit, my_answer, skip_reason)。

    should_submit 为 False 表示跳过本题, skip_reason 取值:
    'anti'(防刷题题目) / 'no_answer'(本地与网络题库均未找到答案) / 'adapter'(搜题服务不可用);
    should_submit 为 True 时 skip_reason 为 None。
    跳过后的等待延迟由调用方(main)统一随机处理, 本函数内部不做等待。
    """
    # 检测刷题题目
    if '刷题' in question or '请选择' in question:
        logger.warning('检测到防刷题题目, 自动跳过')
        return False, '', 'anti'
    if now_right_rate > max_right_rate:
        if question in questions:
            logger.warning(f'该题目已存在本地题库中/正确率过高!  正确答案为 {questions[question]}, 将自动提交随机答案! ')
        else:
            logger.warning('正确率过高, 将自动提交随机答案! ')
        return True, _random_answer(question_type, len(options)), None
    if question in questions:
        logger.info(f'该题目已存在本地题库中!  正确答案为 {questions[question]}, 将自动提交! ')
        return True, questions[question], None

    if question_type == 0:
        # 保留多个特殊选项命中时选择最后一个的行为。
        for index in range(len(options) - 1, -1, -1):
            if '下都是' in options[index] or '上都是' in options[index]:
                return True, options_list[index], None

    my_answer = search(question, question_type, options)
    if my_answer is None:
        return False, '', 'adapter'
    if my_answer == '':
        logger.warning('网络题库未找到答案, 本题跳过! ')
        return False, '', 'no_answer'
    return True, my_answer, None
