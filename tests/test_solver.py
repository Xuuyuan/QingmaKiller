import unittest
from unittest.mock import patch

from solver import decide_answer


class DecisionTest(unittest.TestCase):
    def test_priority_and_skip_reasons(self):
        cases = [
            ('请选择', {'请选择': 'B'}, 1, 'A', (False, '', 'anti')),
            ('题目', {'题目': 'B'}, 1, 'A', (True, 'C', None)),
            ('题目', {}, 1, 'A', (True, 'C', None)),
            ('题目', {'题目': 'B'}, 0.9, 'A', (True, 'B', None)),
            ('题目', {}, 0.5, None, (False, '', 'adapter')),
            ('题目', {}, 0.5, '', (False, '', 'no_answer')),
            ('题目', {}, 0.5, 'A', (True, 'A', None)),
        ]
        for question, bank, rate, answer, expected in cases:
            with self.subTest(expected=expected), patch('solver.search', return_value=answer) as search, patch('solver._random_answer', return_value='C'):
                self.assertEqual(decide_answer(question, 0, ['甲', '乙', '丙'], bank, rate, 0.9), expected)
                self.assertEqual(search.call_count, int(question == '题目' and not bank and rate <= 0.9))

    def test_last_special_option_wins_only_for_single_choice(self):
        with patch('solver.search', return_value='AB') as search:
            options = ['以下都是', '以上都是']
            self.assertEqual(decide_answer('题目', 0, options, {}, 0, 0.9), (True, 'B', None))
            search.assert_not_called()
            self.assertEqual(decide_answer('题目', 1, options, {}, 0, 0.9), (True, 'AB', None))
