"""青马易战站点 HTTP 接口: 获取课程列表、取题与提交答案"""
import json
import re

import requests
from bs4 import BeautifulSoup

from config import base_host, base_url, oauth_host, options_list, user_agent
from logger import logger
from utils import decrypt, gettime, text_format

def build_headers(cookie, referer):  # 站点JSON接口的通用请求头
    return {
        'Referer': referer,
        'User-Agent': user_agent,
        'Cookie': cookie,
        'Accept': 'application/json',
        'Origin': base_url,
        'Host': base_host
    }


def get_course_list(cookie) -> dict:  # 获取课程列表
    headers = build_headers(cookie, f'{base_url}/yiban-web/stu/toCourse.jhtml')
    response = requests.get(f"{base_url}/yiban-web/stu/toCourse.jhtml",
                            data="", headers=headers, allow_redirects=False)
    if response.status_code == 302:
        return {"isSuccess": False}
    soup = BeautifulSoup(response.text, 'html.parser')
    courses = {}
    for li in soup.find_all('li', class_='mui-table-view-cell mui-media mui-col-xs-6 mui-col-sm-6 course-li'):
        a_tag = li.find('a', class_='ahref')
        course_id = re.search(r'courseId=(\d+)', a_tag['href']).group(1)
        course_name = li.find('div', class_='mui-media-body').text.strip()
        courses[course_id] = course_name
    return {"isSuccess": True, "courses": courses}


def _parse_site_json(response, action):  # 解析站点JSON响应, 会话失效被跳转到授权页时给出明确错误
    if oauth_host in response.url or response.text.strip().startswith('<'):
        raise RuntimeError(f'{action}时站点会话已失效, 请重新运行程序完成认证! ')
    return json.loads(response.text)


def fetch_question(headers, subject_id) -> dict:  # 获取下一题并解密, 返回字段化的字典, 失败时返回None
    req = requests.post(
        f'{base_url}/yiban-web/stu/nextSubject.jhtml?_={gettime()}', headers=headers, data={'courseId': subject_id})
    # TODO
    if 'document.location=\'/host_not_found_error\'' in req.text:
        logger.error('该URL已过期, 请根据指引重新获取URL! ')
        return None
    html = _parse_site_json(req, '获取题目')
    if 'uuid' not in html['data']:
        logger.error(f'题目获取失败! 返回信息: {html}')
        return None
    data = html['data']['nextSubject']
    description = decrypt(data['subDescript'])
    options = [text_format(decrypt(data[f'option{i}'])) for i in range(
        data['optionCount']) if f'option{i}' in data]
    text_options = ' '.join(
        options_list[i] + '. ' + options[i] + ' ' for i in range(len(options)))
    return {
        'uuid': html['data']['uuid'],
        'question': text_format(description),
        'description': description,
        'type': 1 if data['subType'] == '多选题' else 0,
        # 0为单选 1为多选
        'options': options,
        'text_options': text_options,
    }


def submit_answer(headers, subject_id, uuid, answer):  # 提交答案, 返回响应JSON
    data_submit = {'answer': answer,
                   'courseId': subject_id, 'uuid': uuid, 'deviceUuid': ""}
    req_submit = requests.post(
        f'{base_url}/yiban-web/stu/changeSituation.jhtml?_={gettime()}', headers=headers, data=data_submit)
    return _parse_site_json(req_submit, '提交答案')
