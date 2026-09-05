import os
import random
import time

from api import build_headers, fetch_question, get_course_list, submit_answer
from auth import clear_saved_session, handshake_from_url, load_saved_session, save_session
from bank import QuestionBank
from cli import collect_config, select_subject
from config import base_url, options_list
from logger import logger
from paths import get_app_dir
from solver import decide_answer
from utils import decrypt

# 路径修正
application_path = get_app_dir()

os.chdir(application_path)
logger.info(f'当前工作目录已锁定至: {application_path}')


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


def main():
    logger.info('=== Qingmakiller 青马易战自动答题工具 ===')
    cookie, course_list = acquire_session()

    # 选定需要刷题的科目
    subjectId = select_subject(course_list['courses'])
    if subjectId is None:
        return

    run_config = collect_config()
    if run_config is None:
        return
    now_times, now_right_times, now_right_rate, target_times, target_right_rate, max_right_rate = run_config

    headers = build_headers(cookie, f'{base_url}/yiban-web/stu/toSubject.jhtml?courseId={subjectId}')

    # 载入文件(不存在则进行初始化)
    bank = QuestionBank(subjectId)
    questions = bank.questions

    run_times = 0
    # 开始运行
    while now_right_times <= target_times or now_right_rate < target_right_rate:  # 循环条件
        # 获取题目及选项
        now_subject = fetch_question(headers, subjectId)
        if now_subject is None:
            break
        logger.info(f'{now_right_times}->{target_times} '
                    f'{now_subject["description"]} {now_subject["text_options"]}')
        should_submit, my_answer = decide_answer(
            now_subject['question'], now_subject['type'], now_subject['options'],
            questions, now_right_rate, max_right_rate)
        if not should_submit:
            continue
        # 随机休眠, 防止检测
        time.sleep(random.randint(4, 10))

        # 提交答案
        res_submit = submit_answer(headers, subjectId, now_subject['uuid'], my_answer)

        if res_submit['message'] == '回答正确！':  # 回答正确
            run_times += 1
            now_times += 1
            now_right_times += 1
            now_right_rate = now_right_times / now_times
            bank.record(now_subject['question'], now_subject['text_options'], my_answer, '?')
            logger.success(
                f'本题回答正确!  当前提交次数 {run_times} 目标答对数 {target_times} 现答对数 {now_right_times} 现答题数 {now_times} 正确率 {now_right_rate * 100:.2f}%/{target_right_rate * 100}%')
        elif res_submit['message'] == '回答错误！':  # 回答错误
            run_times += 1
            now_times += 1
            now_right_rate = now_right_times / now_times
            rightAnswer = decrypt(res_submit['data']['rightOption'])
            bank.record(now_subject['question'], now_subject['text_options'],
                        ''.join(k for k in options_list if k in rightAnswer), rightAnswer)
            logger.info(f'本题回答错误!  提交答案: {my_answer} 正确答案: {rightAnswer} 当前提交次数 {run_times}/{target_times} 现答对数 {now_right_times} 现答题数 {now_times} 正确率 {now_right_rate * 100:.2f}%/{target_right_rate * 100}%')
        elif res_submit['message'] == '您的答题速度过快，请认真答题，30s后可继续答题.':  # 触发答题冷却
            logger.warning('触发答题冷却, 等待30s后自动继续..')
            time.sleep(30)
        else:  # 发现错误, 等待手动处理
            logger.error(f'发现未知回复文本: {res_submit}')
            input()
    logger.success('运行完毕。')


if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception:
            logger.exception('发现错误')
