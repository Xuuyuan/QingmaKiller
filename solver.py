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
    if question in questions:  # 题目已存在本地题库
        if now_right_rate > max_right_rate:  # 正确率过高
            logger.warning(f'该题目已存在本地题库中/正确率过高!  正确答案为 {questions[question]}, 将自动提交随机答案! ')
            my_answer = _random_answer(question_type, len(options))
        else:
            logger.info(f'该题目已存在本地题库中!  正确答案为 {questions[question]}, 将自动提交! ')
            my_answer = questions[question]
        return True, my_answer, None

    # 题目不存在本地题库中, 尝试从网络题库获取
    my_answer = ''
    force_choose = False
    if question_type == 0:
        for d in range(len(options)):
            if '下都是' in options[d] or '上都是' in options[d]:  # 有出现对应文本的选项直接提交
                my_answer = options_list[d]
                force_choose = True
    if now_right_rate > max_right_rate:  # 正确率过高, 随机提交答案
        my_answer = _random_answer(question_type, len(options))
        logger.warning('正确率过高, 将自动提交随机答案! ')
        force_choose = True
    elif not force_choose:
        my_answer = search(question, question_type, options)
        if my_answer is None:  # tikuAdapter不可用, 自动跳过本题
            return False, '', 'adapter'
    if my_answer == '':  # 网络题库未找到答案
        logger.warning('网络题库未找到答案, 本题跳过! ')
        return False, '', 'no_answer'
    return True, my_answer, None
