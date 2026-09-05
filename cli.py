"""交互输入与参数校验"""
from typing import NamedTuple

from config import default_max_right_rate, default_target_right_rate, default_target_times
from logger import logger


class RunConfig(NamedTuple):
    now_times: int
    now_right_times: int
    now_right_rate: float
    target_times: int
    target_right_rate: float
    max_right_rate: float


def select_subject(courses):  # 科目列表展示并选定需要刷题的科目, 校验失败返回None
    allowed_course_ids = []
    logger.info('科目ID | 科目名称')
    for i in courses.items():
        logger.info(f'{i[0]} | {i[1]}')
        allowed_course_ids.append(i[0])

    subjectId = input('请输入需要刷题的科目ID: ')
    if subjectId == '':
        logger.error('未输入科目ID! ')
        return None
    elif not subjectId.isdigit():
        logger.error('科目ID错误, 请重新输入! ')
        return None
    elif subjectId not in allowed_course_ids:
        logger.error('科目不在当前开放的范围内, 请重新输入! ')
        return None
    return subjectId


def collect_config():  # 收集答题参数并做防呆验证, 校验失败返回None
    logger.info('提示: 请先打开本目录下的tikuAdapter.exe, 以保证搜题功能正常使用。')
    logger.info('提示：若仅需满足课程要求，以下配置项均保持默认(不输入任何内容)即可。')
    now_times_str = input('请输入当前的答题数(不输入默认为0): ')
    now_right_times_str = input('请输入当前的答对数(不输入默认为0): ')
    now_times = int(now_times_str) if now_times_str != '' else 0
    now_right_times = int(
        now_right_times_str) if now_right_times_str != '' else 0
    now_right_rate = now_right_times / now_times if now_times != 0 else 0  # 计算当前正确率

    target_times_str = input('请输入需要刷到的目标答对次数(不输入默认为550): ')
    target_times = int(target_times_str) if target_times_str != '' else default_target_times

    target_right_rate_str = input('请输入需要刷题的保底正确率(不输入默认为0.6): ')
    target_right_rate = float(target_right_rate_str) if target_right_rate_str != '' else default_target_right_rate

    max_right_rate_str = input('请输入需要刷题的上限正确率(不输入默认为0.9): ')
    max_right_rate = float(max_right_rate_str) if max_right_rate_str != '' else default_max_right_rate

    # 防呆验证
    if target_times <= 0 or now_right_times < 0 or now_times < 0:
        logger.error('答题次数不能小于0, 请重新填写! ')
        return None
    elif target_times < now_right_times:
        logger.error('目标答对次数不能小于当前答对次数, 请重新填写! ')
        return None
    elif now_times < now_right_times:
        logger.error('当前答题数不能小于当前答对数, 请重新填写! ')
        return None
    elif target_right_rate >= max_right_rate:
        logger.error('保底正确率不能大于或等于上限正确率, 请重新填写! ')
        return None
    elif max_right_rate <= 0 or target_right_rate <= 0 or max_right_rate > 1 or target_right_rate > 1:
        logger.error('正确率所允许的区间为: (0, 1], 请重新选择! ')
        return None

    return RunConfig(now_times, now_right_times, now_right_rate, target_times,
                     target_right_rate, max_right_rate)
