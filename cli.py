"""交互输入与参数校验"""
import sys
import time
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


def select_subject(courses):  # 科目列表展示并选定需要刷题的科目, 循环询问直到输入合法
    allowed_course_ids = []
    logger.info('科目ID | 科目名称')
    for course_id, course_name in courses.items():
        logger.info(f'{course_id} | {course_name}')
        allowed_course_ids.append(course_id)

    while True:
        subject_id = input('请输入需要刷题的科目ID: ').strip()
        if subject_id == '':
            logger.error('未输入科目ID! ')
        elif not subject_id.isdigit():
            logger.error('科目ID错误, 请重新输入! ')
        elif subject_id not in allowed_course_ids:
            logger.error('科目不在当前开放的范围内, 请重新输入! ')
        else:
            return subject_id


def _input_nonnegative_int(prompt, default):  # 循环询问直到输入合法的非负整数, 空输入采用默认值
    while True:
        raw = input(prompt).strip()
        if raw == '':
            return default
        if raw.isdigit():
            return int(raw)
        logger.error('输入必须为非负整数, 请重新输入! ')


def _input_rate(prompt, default):  # 循环询问直到输入(0,1]内的数值, 空输入采用默认值
    while True:
        raw = input(prompt).strip()
        if raw == '':
            return default
        try:
            value = float(raw)
        except ValueError:
            logger.error('输入必须为数字, 请重新输入! ')
            continue
        if 0 < value <= 1:
            return value
        logger.error('正确率所允许的区间为: (0, 1], 请重新输入! ')


def collect_config():  # 收集答题参数, 逐项校验, 非法输入就地重新询问
    logger.info('提示：若仅需满足课程要求，以下配置项均保持默认(不输入任何内容)即可。')

    now_times = _input_nonnegative_int('请输入当前的答题数(不输入默认为0): ', 0)
    while True:  # 当前答对数不能超过当前答题数
        now_right_times = _input_nonnegative_int('请输入当前的答对数(不输入默认为0): ', 0)
        if now_right_times <= now_times:
            break
        logger.error('当前答对数不能大于当前答题数, 请重新填写! ')
    now_right_rate = now_right_times / now_times if now_times != 0 else 0  # 计算当前正确率

    while True:  # 目标答对次数必须为正且不小于当前答对数
        target_times = _input_nonnegative_int('请输入需要刷到的目标答对次数(不输入默认为550): ', default_target_times)
        if target_times == 0:
            logger.error('目标答对次数必须大于0, 请重新填写! ')
        elif target_times < now_right_times:
            logger.error('目标答对次数不能小于当前答对次数, 请重新填写! ')
        else:
            break

    target_right_rate = _input_rate('请输入需要刷题的保底正确率(不输入默认为0.6): ', default_target_right_rate)
    while True:  # 上限正确率必须大于保底正确率
        max_right_rate = _input_rate('请输入需要刷题的上限正确率(不输入默认为0.9): ', default_max_right_rate)
        if max_right_rate > target_right_rate:
            break
        logger.error('保底正确率不能大于或等于上限正确率, 请重新填写! ')

    return RunConfig(now_times, now_right_times, now_right_rate, target_times,
                     target_right_rate, max_right_rate)


def countdown(seconds, action):  # 单行倒计时展示等待过程, 结束后清除该行
    for remaining in range(seconds, 0, -1):
        print(f'\r{action}, 剩余 {remaining} 秒…', end='', flush=True, file=sys.stderr)
        time.sleep(1)
    print('\r' + ' ' * 60 + '\r', end='', flush=True, file=sys.stderr)


def print_run_summary(stats, elapsed_seconds, now_times, now_right_times, now_right_rate,
                      target_times, target_right_rate):  # 输出本次运行统计, 未产生任何动作时不输出
    if not any(stats.values()):
        return
    submitted = stats['correct'] + stats['wrong']
    minutes, seconds = divmod(int(elapsed_seconds), 60)
    logger.info('=== 本次运行统计 ===')
    logger.info(f'提交答题: {submitted} 次 (答对 {stats["correct"]} / 答错 {stats["wrong"]})')
    logger.info(f'跳过题目: {stats["anti"] + stats["no_answer"] + stats["adapter"]} 次 '
                f'(防刷题 {stats["anti"]} / 未搜到答案 {stats["no_answer"]} / 搜题服务不可用 {stats["adapter"]})')
    logger.info(f'触发答题冷却: {stats["cooldown"]} 次')
    if submitted > 0:
        logger.info(f'本次耗时: {minutes}分{seconds}秒 (平均每题 {elapsed_seconds / submitted:.1f} 秒)')
    else:
        logger.info(f'本次耗时: {minutes}分{seconds}秒')
    logger.info(f'当前累计: 答对 {now_right_times}/{now_times} | 正确率 {now_right_rate * 100:.2f}% '
                f'(目标: 答对 {target_times} 次, 正确率 {target_right_rate * 100:g}%)')
