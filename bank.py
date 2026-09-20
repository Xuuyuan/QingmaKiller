"""本地题库(tiku.json)的载入与记录"""
import json
import os

from logger import logger
from paths import get_app_dir
from utils import text_format

BANK_FILE = os.path.join(get_app_dir(), 'tiku.json')


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
        # 保留最后一条答案优先的行为, 并索引所有同题记录以便纠错。
        self.questions = {}
        self._question_records = {}
        for item in self.question_list:
            question = text_format(item['question'])
            self.questions[question] = item['answer']
            self._question_records.setdefault(question, []).append(item)

    def record(self, question, text_options, answer, right_answer=None):  # 新增题目, 或根据站点反馈纠正已有答案
        if question in self.questions:
            # 只有站点在答错后返回的正确答案才能修正已有记录。
            if right_answer is not None and answer and self.questions[question] != answer:
                for item in self._question_records.get(question, ()):
                    item.update(options=text_options, answer=answer, answer_text=right_answer)
                save_bank(self.bank)
                self.questions[question] = answer
                logger.info('已根据站点返回的正确答案修正本地题库')
            return
        self.questions[question] = answer
        item = {
            'question': question,
            'options': text_options,
            'answer': answer,
            'answer_text': right_answer,
        }
        self.question_list.append(item)
        self._question_records.setdefault(text_format(question), []).append(item)
        save_bank(self.bank)
