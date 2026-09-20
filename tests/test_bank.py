"""bank 模块的单元测试, 运行方式: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bank  # noqa: E402


class BankTestBase(unittest.TestCase):
    def setUp(self):  # 在独立的临时目录中运行, 避免触碰真实题库文件
        self._old_bank_file = bank.BANK_FILE
        self._tmp_dir = tempfile.TemporaryDirectory()
        bank.BANK_FILE = os.path.join(self._tmp_dir.name, 'tiku.json')

    def tearDown(self):
        bank.BANK_FILE = self._old_bank_file
        self._tmp_dir.cleanup()


class LoadAndRecordTest(BankTestBase):
    def test_missing_file_starts_empty(self):
        question_bank = bank.QuestionBank(1)
        self.assertEqual(question_bank.questions, {})

    def test_record_appends_and_persists(self):
        question_bank = bank.QuestionBank(1)
        question_bank.record('题目一', 'A. 甲 B. 乙', 'A', '甲')
        question_bank.record('题目二', 'A. 甲 B. 乙 C. 丙', 'BC')
        self.assertEqual(question_bank.questions, {'题目一': 'A', '题目二': 'BC'})
        with open(bank.BANK_FILE, encoding='utf-8') as fp:
            data = json.load(fp)
        self.assertEqual(data['version'], 1)
        self.assertEqual(len(data['subjects']['1']), 2)
        self.assertEqual(data['subjects']['1'][0]['answer_text'], '甲')
        self.assertIsNone(data['subjects']['1'][1]['answer_text'])  # 未知答案文本保存为null
        # 重新载入后题目与答案一致
        reloaded = bank.QuestionBank(1)
        self.assertEqual(reloaded.questions, {'题目一': 'A', '题目二': 'BC'})

    def test_record_ignores_known_question(self):
        question_bank = bank.QuestionBank(1)
        question_bank.record('题目一', 'A. 甲 B. 乙', 'A', '甲')
        question_bank.record('题目一', 'A. 甲 B. 乙', 'A', '甲')
        self.assertEqual(len(question_bank.question_list), 1)

    def test_wrong_known_answer_is_corrected_and_persisted(self):
        question_bank = bank.QuestionBank(1)
        question_bank.record('题目一', 'A. 甲 B. 乙', 'A')
        question_bank.record('题目一', 'A. 甲 B. 乙', 'B', '乙')
        self.assertEqual(question_bank.questions['题目一'], 'B')
        self.assertEqual(len(question_bank.question_list), 1)
        self.assertEqual(bank.QuestionBank(1).questions['题目一'], 'B')
        self.assertEqual(question_bank.question_list[0]['answer_text'], '乙')

    def test_submitted_answer_cannot_overwrite_known_answer(self):
        question_bank = bank.QuestionBank(1)
        question_bank.record('题目一', 'A. 甲 B. 乙', 'A')
        question_bank.record('题目一', 'A. 甲 B. 乙', 'B')
        self.assertEqual(question_bank.questions['题目一'], 'A')

    def test_loaded_normalized_duplicates_are_all_corrected(self):
        data = {'version': 1, 'subjects': {'1': [
            {'question': '题 目．一', 'answer': 'A'},
            {'question': '题目一', 'answer': 'B'},
            {'question': '其他题目', 'answer': 'A'},
        ]}}
        bank.save_bank(data)
        question_bank = bank.QuestionBank(1)
        self.assertEqual(question_bank.questions['题目一'], 'B')
        question_bank.record('题目一', 'A. 甲 B. 乙 C. 丙', 'C', '丙')
        reloaded = bank.QuestionBank(1)
        self.assertEqual(reloaded.questions['题目一'], 'C')
        for item in reloaded.question_list[:2]:
            self.assertEqual(item['answer'], 'C')
            self.assertEqual(item['options'], 'A. 甲 B. 乙 C. 丙')
            self.assertEqual(item['answer_text'], '丙')
        self.assertEqual(reloaded.question_list[2], data['subjects']['1'][2])


class SubjectIsolationTest(BankTestBase):
    def test_same_question_in_different_subjects(self):
        bank.QuestionBank(1).record('同题', 'A. 甲 B. 乙', 'A', '甲')
        bank.QuestionBank(2).record('同题', 'A. 甲 B. 乙', 'B', '乙')
        self.assertEqual(bank.QuestionBank(1).questions['同题'], 'A')
        self.assertEqual(bank.QuestionBank(2).questions['同题'], 'B')


class LoadBankTest(BankTestBase):
    def test_broken_file_backed_up(self):
        with open(bank.BANK_FILE, 'w', encoding='utf-8') as fp:
            fp.write('{"subjects": oops')
        question_bank = bank.QuestionBank(1)
        self.assertEqual(question_bank.questions, {})
        self.assertTrue(os.path.exists(bank.BANK_FILE + '.broken'))


if __name__ == '__main__':
    unittest.main()
