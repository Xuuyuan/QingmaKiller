import os
import random
import subprocess
import time

from api import build_headers, fetch_question, get_course_list, submit_answer
from auth import clear_saved_session, handshake_from_url, load_saved_session, save_session
from bank import QuestionBank
from cli import collect_config, countdown, print_run_summary, select_subject
from config import base_url, options_list
from logger import logger
from paths import get_app_dir
from solver import decide_answer
from tiku import adapter_alive
from utils import decrypt

# 路径修正
application_path = get_app_dir()

os.chdir(application_path)
logger.info(f'当前工作目录已锁定至: {application_path}')


class UserQuit(Exception):
    """用户在交互过程中主动选择退出程序"""


def validate_cookie(cookie, retries=3):  # 以课程列表校验会话有效性, 失败返回None
    for attempt in range(retries):
        course_list = get_course_list(cookie)
        if course_list['isSuccess']:
            return course_list
        if attempt < retries - 1:
            logger.warning(f'会话校验未通过, 将在1秒后重试({attempt + 2}/{retries})…')
            time.sleep(1)
    return None


def login_by_url():  # 通过APP复制的URL认证, 直到成功为止
    while True:
        url = input('请输入青马易战URL: ').strip()
        if url == '':
            logger.error('未输入URL! 请在易班APP内进入青马易战主界面, 点击右上角交互按钮选择【复制链接】。')
            continue
        cookie, reason = handshake_from_url(url)
        if cookie is None:
            logger.error(f'URL认证失败: {reason}! 请在易班APP内重新复制最新链接后重试。')
            continue
        course_list = validate_cookie(cookie)
        if course_list is None:
            logger.warning('URL握手成功但会话校验未通过, 请重新复制URL后重试')
            continue
        logger.success(f'获取到cookie: {cookie}')
        save_session(cookie)
        return cookie, course_list


def acquire_session():  # 会话获取链路: 本地持久化会话 → URL握手, 永不返回None
    saved = load_saved_session()
    if saved:
        logger.info('检测到本地保存的会话, 正在验证…')
        course_list = validate_cookie(saved)
        if course_list is not None:
            logger.success(f'本地会话有效, 已跳过认证: {saved}')
            return saved, course_list
        clear_saved_session()
        logger.warning('本地会话已失效, 需要重新认证')

    logger.info('提示: 请在易班APP内进入青马易战主界面(有大视频播放的页面), 点击右上角交互按钮, 选择【复制链接】, 将获取到的URL粘贴到下方输入框中。')
    logger.info('提示: 认证成功后会话会缓存到本地, 有效期内再次运行无需重新输入URL。')
    return login_by_url()


tiku_adapter_process = None  # 本程序自动拉起的tikuAdapter子进程, 程序退出时同步关闭


def ensure_tiku_adapter():  # 探测本地搜题服务, 未运行时尝试自动拉起同目录的tikuAdapter.exe
    global tiku_adapter_process
    if adapter_alive():
        logger.info('搜题服务(tikuAdapter)运行正常')
        return
    exe_path = os.path.join(application_path, 'tikuAdapter.exe')
    if not os.path.exists(exe_path):
        logger.warning('未找到搜题程序 tikuAdapter.exe, 本地题库未命中的题目将被跳过! ')
        return
    logger.info('搜题服务未运行, 正在尝试自动启动 tikuAdapter.exe…')
    try:  # 输出重定向到独立日志文件, 避免搜题服务日志混入主程序终端
        with open(os.path.join(application_path, 'tikuadapter.log'), 'w', encoding='utf-8') as log_fp:
            tiku_adapter_process = subprocess.Popen(
                [exe_path], cwd=application_path, stdin=subprocess.DEVNULL,
                stdout=log_fp, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except OSError as exc:
        logger.warning(f'tikuAdapter 自动启动失败({exc}), 本地题库未命中的题目将被跳过! 可手动启动后重试。')
        return
    for _ in range(15):  # 最多等待15秒直到搜题服务就绪
        if adapter_alive():
            logger.info('搜题服务已启动')
            return
        time.sleep(1)
    logger.warning('等待搜题服务启动超时, 本地题库未命中的题目将被跳过! ')


def stop_tiku_adapter():  # 关闭由本程序拉起的搜题服务, 用户手动启动的不做处理
    if tiku_adapter_process is None or tiku_adapter_process.poll() is not None:
        return
    try:
        tiku_adapter_process.terminate()
        tiku_adapter_process.wait(timeout=5)
        logger.info('已同步关闭搜题服务(tikuAdapter)。')
    except Exception as exc:
        logger.warning(f'关闭搜题服务失败({exc}), 如有残留请手动结束 tikuAdapter 进程! ')


def main():
    logger.info('=== Qingmakiller 青马易战自动答题工具 ===')
    ensure_tiku_adapter()
    cookie, course_list = acquire_session()

    # 选定需要刷题的科目
    subjectId = select_subject(course_list['courses'])

    run_config = collect_config()
    now_times, now_right_times, now_right_rate, target_times, target_right_rate, max_right_rate = run_config

    # 开始前确认摘要
    subject_name = course_list['courses'].get(subjectId, subjectId)
    logger.info(f'即将开始: 科目 {subject_name}(ID {subjectId}) | 目标答对 {target_times} 次 | '
                f'保底正确率 {target_right_rate * 100:g}% / 上限正确率 {max_right_rate * 100:g}%')
    if input('直接回车开始答题, 输入 q 并回车退出: ').strip().lower() == 'q':
        raise UserQuit

    headers = build_headers(cookie, f'{base_url}/yiban-web/stu/toSubject.jhtml?courseId={subjectId}')

    # 载入文件(不存在则进行初始化)
    bank = QuestionBank(subjectId)
    questions = bank.questions

    stats = {'correct': 0, 'wrong': 0, 'anti': 0, 'no_answer': 0, 'adapter': 0, 'cooldown': 0}
    started_at = time.monotonic()
    run_times = 0
    try:
        # 开始运行
        while now_right_times <= target_times or now_right_rate < target_right_rate:  # 循环条件
            # 获取题目及选项
            now_subject = fetch_question(headers, subjectId)
            if now_subject is None:
                break
            logger.info(f'{now_right_times}->{target_times} '
                        f'{now_subject["description"]} {now_subject["text_options"]}')
            should_submit, my_answer, skip_reason = decide_answer(
                now_subject['question'], now_subject['type'], now_subject['options'],
                questions, now_right_rate, max_right_rate)
            if not should_submit:  # 跳过后随机延迟, 避免高频取题触发风控
                stats[skip_reason] += 1
                countdown(random.randint(4, 10), '本题已跳过')
                continue
            # 随机休眠, 防止检测
            time.sleep(random.randint(4, 10))

            # 提交答案
            res_submit = submit_answer(headers, subjectId, now_subject['uuid'], my_answer)

            message = res_submit['message']
            if message == '回答正确！':  # 回答正确
                run_times += 1
                now_times += 1
                now_right_times += 1
                now_right_rate = now_right_times / now_times
                stats['correct'] += 1
                bank.record(now_subject['question'], now_subject['text_options'], my_answer, '?')
                logger.success(
                    f'本题回答正确!  当前提交次数 {run_times} 目标答对数 {target_times} 现答对数 {now_right_times} 现答题数 {now_times} 正确率 {now_right_rate * 100:.2f}%/{target_right_rate * 100}%')
            elif message == '回答错误！':  # 回答错误
                run_times += 1
                now_times += 1
                now_right_rate = now_right_times / now_times
                stats['wrong'] += 1
                rightAnswer = decrypt(res_submit['data']['rightOption'])
                bank.record(now_subject['question'], now_subject['text_options'],
                            ''.join(k for k in options_list if k in rightAnswer), rightAnswer)
                logger.info(f'本题回答错误!  提交答案: {my_answer} 正确答案: {rightAnswer} 当前提交次数 {run_times}/{target_times} 现答对数 {now_right_times} 现答题数 {now_times} 正确率 {now_right_rate * 100:.2f}%/{target_right_rate * 100}%')
            elif message == '您的答题速度过快，请认真答题，30s后可继续答题.':  # 触发答题冷却
                stats['cooldown'] += 1
                countdown(30, '触发答题冷却')
            else:  # 发现未知回复, 交由用户决定继续或退出
                logger.error(f'发现未知回复文本: {res_submit}')
                if input('直接回车继续答下一题, 输入 q 并回车退出: ').strip().lower() == 'q':
                    raise UserQuit
        else:  # 循环条件自然结束(目标达成), 取题失败break时不提示
            logger.success('运行完毕。')
    finally:
        # 无论目标达成、手动中断还是异常退出, 都输出本次运行统计
        print_run_summary(stats, time.monotonic() - started_at, now_times, now_right_times,
                          now_right_rate, target_times, target_right_rate)


if __name__ == '__main__':
    consecutive_errors = 0
    while True:
        try:
            main()
            consecutive_errors = 0
        except KeyboardInterrupt:  # 手动中断(Ctrl+C), 直接干净退出
            logger.info('已手动中断, 程序退出。')
            break
        except UserQuit:  # 用户在交互中主动选择退出
            logger.info('程序已退出。')
            break
        except Exception:
            consecutive_errors += 1
            logger.exception('运行中出现未处理的异常')
            if consecutive_errors >= 3:
                logger.error('连续异常次数过多, 程序退出! 详情请查看 qingmakiller.log')
                break
            logger.warning(f'将在2秒后自动重新运行… (连续异常 {consecutive_errors}/3)')
            time.sleep(2)
        else:
            # 本轮正常结束(目标达成或取题失败), 由用户决定是否继续下一轮
            if input('本轮已结束。直接回车继续下一轮, 输入 q 并回车退出: ').strip().lower() == 'q':
                logger.info('程序已退出。')
                break
    stop_tiku_adapter()  # 所有退出路径(正常结束/主动退出/中断/连续异常)最终都汇合到这里
