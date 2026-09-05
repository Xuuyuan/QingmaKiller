"""站点会话获取: URL握手与会话持久化

经真实链路追踪确认: 青马易战(iapp76127)被易班网关限制为"仅限在易班APP内使用"。
新鲜verify_request只能由易班APP原生客户端换取——
  APP登录(mobile.yiban.cn, WAF拦截非APP客户端且需要X-AK/X-SG/X-TL/X-TP/X-KD签名头)
  -> f.yiban.cn/iapp/index?act=iapp76127&v=<APP access_token> -> 302携带verify_request。
Web端OAuth账号验证(oauth.yiban.cn)拿到的yiban_user_token被网关拒绝, 因此
本工具不提供账号密码登录, 只支持URL握手 + 会话持久化复用。
"""
import json
import os
import re
import time

import requests

from config import base_host, oauth_host, user_agent
from logger import logger
from paths import get_app_dir

session_file = os.path.join(get_app_dir(), 'session.json')

# URL失效时站点直接返回错误页(200 + 弹窗), 以此与正常主页区分
site_error_markers = ('<body class="error"', '请文明上网')
oauth_error_marker = oauth_host  # 未认证会话被302到的授权页域名


def _new_session():  # 站点请求会话
    session = requests.Session()
    session.headers['User-Agent'] = user_agent
    return session


def _extract_jsessionid(session):  # 从会话cookie中提取站点JSESSIONID, 返回 'JSESSIONID=xxx' 或 None
    for cookie in session.cookies:
        if cookie.name == 'JSESSIONID' and base_host in (cookie.domain or ''):
            return f'JSESSIONID={cookie.value}'
    return None


def _is_site_error_page(body):  # 判断响应体是否为站点错误页(URL失效/被拒绝)
    return any(marker in body for marker in site_error_markers)


def handshake_from_url(url):  # 通过APP复制的URL建立会话, 返回 (cookie, 失败原因), 成功时失败原因为None
    session = _new_session()
    try:
        res = session.get(url, timeout=15)
    except requests.RequestException as exc:
        logger.debug(f'URL握手请求异常: {exc}')
        return None, '网络请求失败'
    if oauth_error_marker in res.url:
        return None, 'URL已被引导至授权页'
    if res.status_code != 200:
        return None, f'站点返回异常状态{res.status_code}'
    if _is_site_error_page(res.text):
        return None, 'URL已失效或被站点拒绝'
    cookie = _extract_jsessionid(session)
    if cookie is None:
        return None, '未取得站点会话'
    return cookie, None


def load_saved_session():  # 读取本地持久化会话, 无效返回None
    if not os.path.exists(session_file):
        return None
    try:
        with open(session_file, 'r', encoding='utf-8') as fp:
            jsessionid = json.load(fp).get('jsessionid')
        if jsessionid and re.match(r'^JSESSIONID=\w+$', jsessionid):
            return jsessionid
    except (OSError, ValueError):
        pass
    return None


def save_session(cookie):  # 持久化会话供下次运行复用
    try:
        with open(session_file, 'w', encoding='utf-8') as fp:
            json.dump({'jsessionid': cookie, 'saved_at': int(time.time())}, fp)
    except OSError as exc:
        logger.warning(f'会话保存失败: {exc}')


def clear_saved_session():  # 清除已失效的本地会话
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
        except OSError as exc:
            logger.warning(f'会话清理失败: {exc}')
