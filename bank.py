"""本地题库(tiku.json)的载入与记录"""
import json
import os

from logger import logger
from utils import text_format

BANK_FILE = 'tiku.json'


def empty_bank():  # 空题库结构
    return {'version': 1, 'subjects': {}}


def load_bank():  # 读取题库文件, 缺失时返回空结构, 损坏时备份为.broken后返回空结构
    try:
        with open(BANK_FILE, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
    except FileNotFoundError:
        return empty_bank()
    except json.JSONDecodeError:
        broken_path = BANK_FILE + '.broken'
        os.replace(BANK_FILE, broken_path)
        logger.error(f'题库文件 {BANK_FILE} 已损坏! 原文件备份为 {broken_path}, 本次以空题库启动')
        return empty_bank()
    data.setdefault('version', 1)
    data.setdefault('subjects', {})
    return data


def save_bank(bank):  # 原子写回题库文件(先写临时文件再替换, 避免写入中断损坏题库)
    tmp_path = BANK_FILE + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as fp:
        json.dump(bank, fp, ensure_ascii=False, indent=2)
    os.replace(tmp_path, BANK_FILE)


class QuestionBank:
    def __init__(self, subject_id):  # 载入题库文件, 取出指定科目的题目
        self.bank = load_bank()
        self.subject_key = str(subject_id)
        self.question_list = self.bank['subjects'].setdefault(self.subject_key, [])
        # 加载科目题库到变量questions
        self.questions = {text_format(q['question']): q['answer'] for q in self.question_list}

    def record(self, question, text_options, answer, right_answer):  # 若题目不在本地题库中则加入本地题库
        if question in self.questions:
            return
        self.questions[question] = answer
        self.question_list.append({
            'question': question,
            'options': text_options,
            'answer': answer,
            # 正确答案文本未知时以'?'占位(main.py), 存储时统一归一化为null
            'answer_text': None if right_answer == '?' else right_answer,
        })
        save_bank(self.bank)
