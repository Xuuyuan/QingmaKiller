"""内置网络题库: 多源并发搜题与答案聚合, 移植自 MIT 项目 tikuAdapter(https://github.com/DokiDoki1103/tikuAdapter)"""
import base64
import json
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

import requests

from config import (aidian_api, aidian_free_api, banks_config_filename, buguake_api,
                    enncy_api, icodef_api, lemon_api, tikuhai_api, wanneng_api, wanneng_free_api)
from logger import logger
from paths import get_app_dir

BANKS_FILE = os.path.join(get_app_dir(), banks_config_filename)

# 各题库源默认配置: 免费源默认启用; 付费源默认禁用, 在 banks.json 中把对应源置 enable 为 true 并填入 token 后开启
SOURCE_DEFAULTS = {
    'buguake': {'enable': True},
    'icodef': {'enable': True, 'token': ''},
    'wanneng': {'enable': True, 'token': ''},
    'tikuhai': {'enable': True, 'key': ''},
    'enncy': {'enable': False, 'token': ''},
    'aidian': {'enable': False, 'token': ''},
    'lemon': {'enable': False, 'token': ''},
}

_ANSWER_SEP = '**=====^_^======^_^======**'  # 投票计数时组合答案的拼接分隔符(与tikuAdapter保持一致)
_BUGUAKE_MIN_SIMILARITY = 0.8  # 不挂科候选题干的最低相似度(difflib与原实现算法不同, 命中率异常时可微调)
_FUZZY_SIMILARITY = 0.7  # 多选题模糊匹配的最低相似度

source_config = None  # 进程内缓存的题库源配置, 由 enabled_sources 首次调用时载入


def _similarity(left, right):  # 字符串相似度(0~1)
    return SequenceMatcher(None, left, right).ratio()


def _full_to_half_width(text):  # 全角字符转半角, 转换后越界的字符保持原样
    converted = []
    for index, code in enumerate(map(ord, text)):
        code = 32 if code == 12288 else code - 65248
        converted.append(chr(code) if 32 <= code <= 126 else text[index])
    return ''.join(converted)


def _format_string(text):  # 文本归一化: 全角转半角、中文标点转英文、去末尾标点与首尾空白(移植util.FormatString)
    text = _full_to_half_width(text)
    for old, new in (('“', '"'), ('”', '"'), ('‘', "'"), ('’', "'"), ('。', '.'), ('&nbsp;', ' ')):
        text = text.replace(old, new)
    return text.rstrip(',.?:!;').strip()


_OPTION_PREFIX = re.compile(r'^[A-Z][.．:：、]\s?')


def _format_options(options):  # 去除选项的"A."类前缀并归一化(移植util.FormatOptions, 本站点无判断题故省略该分支)
    return [_format_string(_OPTION_PREFIX.sub('', option)) for option in options]


def _dig(node, *path):  # 沿嵌套dict/list按路径取值, 任一层缺失返回None
    try:
        for key in path:
            node = node[key]
        return node
    except (KeyError, IndexError, TypeError):
        return None


def _buguake_decrypt(text, actk):  # 不挂科响应解密(移植search.decrypt, 复刻其把字节值当码点重新编码的兼容行为)
    key = '34cab29ef956d78afd' + actk
    try:
        raw = base64.b64decode(text)
    except ValueError:
        return ''
    xored = bytes(byte ^ ord(key[index % len(key)]) for index, byte in enumerate(raw))
    # Go的string(rune(d))会把0~255的字节值当作码点重新按UTF-8编码, 此处还原同样的字节流后再解%XX转义
    regrouped = b''.join(chr(xored[p] ^ xored[p + 1]).encode('utf-8') for p in range(0, len(xored) - 1, 2))
    return urllib.parse.unquote_to_bytes(regrouped).decode('utf-8', 'replace').replace('+', ' ')


def _buguake_correct_options(detail):  # 候选中标记为正确的选项文本(对应gjson路径 que_options.0.#(yes=true).ret.0.c.0.c)
    texts = []
    for option in (_dig(detail, 'que_options', 0) or []):
        if isinstance(option, dict) and option.get('yes'):
            text = _dig(option, 'ret', 0, 'c', 0, 'c')
            if text is not None:
                texts.append(text)
    return texts


def _buguake_answer_texts(detail):  # 候选中直接给出的答案文本(对应gjson路径 que_answer.0.c.#.c)
    node = _dig(detail, 'que_answer', 0)
    if not isinstance(node, dict):
        return []
    return [item['c'] for item in (node.get('c') or []) if isinstance(item, dict) and 'c' in item]


def _search_buguake(question, options, question_type, spec):  # 不挂科(百度教育)题库, 题干相似度过低的候选直接丢弃
    response = requests.get(buguake_api, params={'query': question, 'rn': '10', 'pn': '0'}, timeout=3)
    answer_sets = []
    for item in (_dig(response.json(), 'data', 'list') or []):
        try:
            detail = json.loads(_buguake_decrypt(item.get('bdjson', ''), item.get('actk', '')))
        except json.JSONDecodeError:
            continue
        stem = _dig(detail, 'que_stem', 0, 'c', 0, 'c')
        if not isinstance(stem, str) or _similarity(question, stem) < _BUGUAKE_MIN_SIMILARITY:
            continue
        texts = _buguake_correct_options(detail) or _buguake_answer_texts(detail)
        if texts:
            answer_sets.append(texts)
    return answer_sets


def _search_icodef(question, options, question_type, spec):  # icodef题库, 触发流控时自动重试一次
    headers = {'Authorization': spec['token']} if spec.get('token') else {}
    for _ in range(2):
        response = requests.post(icodef_api, data={'question': question}, headers=headers, timeout=5)
        if '触发流控限制' not in response.text or 'IP超出每日限额' in response.text:
            break
        time.sleep(1)
    result = response.json()
    if result.get('code') != 1:
        return []
    answer = str(result.get('data') or '')
    return [answer.split('#')] if answer else []


def _search_wanneng(question, options, question_type, spec):  # 万能题库, 配置10位token时走付费接口, 限流时自动重试一次
    token = spec.get('token', '')
    url = wanneng_api.format(token) if token and len(token) == 10 else wanneng_free_api
    body = {'qid': '', 'plat': 0, 'question': question, 'options': options,
            'type': question_type, 'courseName': '', 'extra': ''}
    for _ in range(2):
        response = requests.post(url, json=body, headers={'plat': '0'}, timeout=5)
        if '已限流,正在重新请求...' not in response.text:
            break
        time.sleep(1)
    result = response.json()
    if result.get('code') != 0:
        return []
    data = result.get('result') or {}
    if not data.get('success'):
        return []
    answers = []
    for value in data.get('answers') or []:
        if isinstance(value, (int, float)):  # 数字答案为选项下标
            if 0 <= int(value) < len(options):
                answers.append(options[int(value)])
        else:
            answers.append(str(value))
    return [answers] * 10 if answers else []  # 原实现重复10份, 使该源在多源投票中权重更高


def _search_tikuhai(question, options, question_type, spec):  # 题库海题库, 服务端异常时自动重试一次
    body = {'question': question, 'options': options, 'type': question_type,
            'key': spec.get('key', ''), 'questionData': ''}
    headers = {'User-Agent': 'tikuhaiAdapter/0.1.0', 'v': '0.1.0'}
    for _ in range(2):
        response = requests.post(tikuhai_api, json=body, headers=headers, timeout=5)
        if response.status_code < 500:
            break
        time.sleep(2)
    result = response.json()
    if result.get('code') != 200:
        return []
    data = result.get('data')
    if isinstance(data, str):
        data = json.loads(data)
    answers = (data or {}).get('answer') or []
    return [answers] if answers else []


def _search_enncy(question, options, question_type, spec):  # 言溪题库(付费)
    token = spec.get('token', '')
    if not token:
        return []
    response = requests.get(enncy_api, params={'token': token, 'title': question}, timeout=5)
    result = response.json()
    if result.get('code') != 1:
        return []
    answer = (result.get('data') or {}).get('answer') or ''
    return [answer.split('#')] if answer else []


def _search_aidian(question, options, question_type, spec):  # 爱点题库(无token时走免费限流接口), 字母答案映射为选项文本
    token = spec.get('token', '')
    response = requests.post(aidian_api if token else aidian_free_api,
                             json={'question': question, 'token': token}, timeout=3)
    answer_sets = []
    for item in (response.json().get('qlist') or []):
        item_options = _format_options(item.get('options') or [])
        answers = []
        for value in (item.get('answer') or []):
            value = str(value)
            if re.fullmatch(r'[A-Z]+', value):  # "ABC"形式的字母答案按下标映射为选项文本
                answers.extend(item_options[ord(letter) - 65] for letter in value
                               if 0 <= ord(letter) - 65 < len(item_options))
            else:
                answers.append(value)
        if answers:
            answer_sets.append(answers)
    return answer_sets


def _search_lemon(question, options, question_type, spec):  # 柠檬题库(付费)
    token = spec.get('token', '')
    if not token:
        return []
    response = requests.post(lemon_api, json={'v': '1.0', 'question': question, 'uid': '703382225'},
                             headers={'Authorization': f'Bearer {token}'}, timeout=5)
    result = response.json()
    if result.get('code') != 1000:
        return []
    answer = (result.get('data') or {}).get('answer') or ''
    return [answer.split('#')] if answer else []


_SOURCE_CLIENTS = {
    'buguake': _search_buguake, 'icodef': _search_icodef, 'wanneng': _search_wanneng,
    'tikuhai': _search_tikuhai, 'enncy': _search_enncy, 'aidian': _search_aidian,
    'lemon': _search_lemon,
}


def _load_sources():  # 读取banks.json, 缺失按默认配置; 损坏时备份为.broken后按默认配置, 不中断运行
    config = {name: dict(defaults) for name, defaults in SOURCE_DEFAULTS.items()}
    try:
        with open(BANKS_FILE, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
    except FileNotFoundError:
        return config
    except json.JSONDecodeError:
        broken_path = BANKS_FILE + '.broken'
        try:
            os.replace(BANKS_FILE, broken_path)
            logger.error(f'网络题库配置 {BANKS_FILE} 已损坏! 原文件备份为 {broken_path}, 本次按默认配置运行')
        except OSError:
            logger.error(f'网络题库配置 {BANKS_FILE} 已损坏且备份失败, 本次按默认配置运行')
        return config
    if not isinstance(data, dict):
        logger.error(f'网络题库配置 {BANKS_FILE} 结构异常, 本次按默认配置运行')
        return config
    for name, source in config.items():  # 仅接受已知源的已知字段, 未知内容一律忽略
        override = data.get(name)
        if isinstance(override, dict):
            source.update({key: value for key, value in override.items() if key in source})
    return config


def enabled_sources():  # 已启用的题库源配置, 进程内只在首次调用时读取文件并输出摘要
    global source_config
    if source_config is None:
        source_config = _load_sources()
        active = [name for name, spec in source_config.items() if spec.get('enable')]
        if active:
            logger.info('已启用网络题库源: ' + ', '.join(active))
        else:
            logger.warning('未启用任何网络题库源, 在线搜题不可用! 可在同目录 banks.json 中配置(付费题库需填入token)。')
    return source_config


def _vote(answer_sets):  # 相同答案组合计数取众数, 平票取先出现者(移植SearchRightAnswer)
    counts = {}
    for answer_set in answer_sets:
        key = _ANSWER_SEP.join(answer_set)
        counts[key] = counts.get(key, 0) + 1
    best_key, best_count = None, 0
    for key, count in counts.items():
        if count > best_count:
            best_key, best_count = key, count
    return best_key.split(_ANSWER_SEP) if best_key is not None else []


def _aggregate(answer_sets, options, question_type):  # 移植FillAnswerResponse: 投票选出最佳答案(选项文本列表, 可能为空)
    norm_options = _format_options(options)
    normalized = [[_format_string(answer) for answer in answer_set] for answer_set in answer_sets]
    if not options:  # 无选项时只能对答案原文投票
        return _vote(normalized)
    need = 2 if question_type == 1 else 1  # 多选题至少命中两个选项才视为有效答案
    exact_sets = []
    for answer_set in normalized:
        exact = [option for option in norm_options if option in answer_set]
        if len(exact) >= need:
            exact_sets.append(exact)
    best = _vote(exact_sets)
    if best:
        return best
    fuzzy_sets = []  # 精确匹配失败时的模糊兜底
    for answer_set in normalized:
        if not answer_set:
            continue
        if question_type != 1:  # 单选: 取与答案整体最相似的选项
            joined = ''.join(answer_set)
            fuzzy_sets.append([max(norm_options, key=lambda option: _similarity(option, joined))])
        else:
            matched = [option for option in norm_options
                       if any(_similarity(option, answer) >= _FUZZY_SIMILARITY for answer in answer_set)]
            if len(matched) > 1:
                fuzzy_sets.append(matched)
    return _vote(fuzzy_sets)


def _answer_letters(best, options):  # 最佳答案文本映射为选项字母串(移植fillAnswer), 无匹配时返回空串
    norm_options = _format_options(options)
    letters = []
    for answer in best:
        for index, option in enumerate(norm_options):
            if option == answer:
                letters.append(chr(65 + index))
                break
    return ''.join(letters)


def search(question, question_type, options):  # 并发搜题: 整体不可用返回None, 未命中返回空串, 命中返回选项字母串
    logger.info('正在搜索网络题库…')
    sources = enabled_sources()
    workers = [(name, _SOURCE_CLIENTS[name]) for name, spec in sources.items() if spec.get('enable')]
    if not workers:
        return None

    def _query(worker):  # 单源搜题, 任何异常都降级为该源无结果, 不影响其余源
        name, client = worker
        try:
            sets = client(question, options, question_type, sources[name])
            # 在单源异常边界内校验完整结构, 避免畸形答案进入公共聚合流程。
            if not isinstance(sets, list) or any(
                    not isinstance(answer_set, list)
                    or any(not isinstance(answer, str) for answer in answer_set)
                    for answer_set in sets):
                raise TypeError('题库答案必须为字符串列表的列表')
            return name, sets, True
        except Exception as exc:
            # requests 异常文本可能包含带 token 的完整 URL, 仅记录异常类型。
            logger.warning(f'题库源 {name} 搜索失败, 已跳过该源: {type(exc).__name__}')
            return name, [], False

    with ThreadPoolExecutor(max_workers=len(workers)) as pool:
        results = list(pool.map(_query, workers))

    answer_sets, hit_sources, failed = [], [], 0
    for name, sets, ok in results:
        if not ok:
            failed += 1
        for answer_set in sets:
            if answer_set:
                answer_sets.append(answer_set)
                if name not in hit_sources:
                    hit_sources.append(name)
    if failed == len(workers):
        logger.error('所有网络题库源均不可用, 本题跳过! ')
        return None
    if not answer_sets:
        return ''
    my_answer = _answer_letters(_aggregate(answer_sets, options, question_type), options)
    if not my_answer:
        logger.warning('网络题库候选答案与本题选项不匹配, 本题跳过! ')
        return ''
    if question_type == 0 and len(my_answer) > 1:  # 避免单选题提交多选
        my_answer = my_answer[0]
    elif question_type == 1 and len(my_answer) == 1:  # 避免多选题提交单选
        return ''
    if question_type == 1:  # 多选题答案按选项顺序去重
        my_answer = ''.join(sorted(set(my_answer)))
    logger.info(f'网络题库命中({", ".join(hit_sources)}), 搜索结果: {my_answer}')
    return my_answer
