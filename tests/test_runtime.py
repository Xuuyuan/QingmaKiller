"""答题边界与外部响应的离线回归测试。"""
import json
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

import api
import auth
import cli
import main
import tiku


class RuntimeTest(unittest.TestCase):
    def test_full_target_rate_is_reprompted(self):
        with patch('builtins.input', side_effect=['0', '0', '1', '1', '0.6', '1']):
            config = cli.collect_config()
        self.assertEqual(config.target_right_rate, 0.6)
        self.assertEqual(config.max_right_rate, 1)

    def test_reached_target_does_not_fetch(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(main, 'ensure_tiku_adapter'))
            stack.enter_context(patch.object(main, 'acquire_session', return_value=('test', {'courses': {'7': 'test'}})))
            stack.enter_context(patch.object(main, 'select_subject', return_value='7'))
            stack.enter_context(patch.object(main, 'collect_config', return_value=cli.RunConfig(10, 6, 0.6, 6, 0.6, 0.9)))
            stack.enter_context(patch.object(main, 'QuestionBank'))
            stack.enter_context(patch('builtins.input', return_value=''))
            fetch = stack.enter_context(patch.object(main, 'fetch_question'))
            main.main()
            fetch.assert_not_called()

    def test_malformed_adapter_answers_are_skipped(self):
        for answer in (42, True, [], ['A'], {}, {'A': 1}):
            with self.subTest(answer=answer), patch.object(tiku.requests, 'post', return_value=Mock(
                    text=json.dumps({'answer': {'answerKeyText': answer}}), status_code=200)):
                self.assertIsNone(tiku.search('test', 1, ['a', 'b']))

    def test_adapter_empty_and_valid_answers(self):
        for answer, expected in ((None, ''), ('', ''), ('A', 'A'), ('AB', 'A')):
            with self.subTest(answer=answer), patch.object(tiku.requests, 'post', return_value=Mock(
                    text=json.dumps({'answer': {'answerKeyText': answer}}), status_code=200)):
                self.assertEqual(tiku.search('test', 0, ['a', 'b']), expected)

    def test_site_requests_have_five_second_timeout(self):
        response = Mock(status_code=302, text='{"data": {}, "message": "test"}', url='http://example.test')
        with patch.object(api.requests, 'get', return_value=response) as get:
            api.get_course_list('test')
            self.assertEqual(get.call_args.kwargs['timeout'], 5)
        with patch.object(api.requests, 'post', return_value=response) as post:
            api.fetch_question({}, '7')
            api.submit_answer({}, '7', 'test', 'A')
            self.assertEqual([c.kwargs['timeout'] for c in post.call_args_list], [5, 5])
        session = Mock()
        session.get.side_effect = auth.requests.Timeout()
        with patch.object(auth, '_new_session', return_value=session):
            self.assertEqual(auth.handshake_from_url('http://example.test'), (None, '网络请求失败'))
            self.assertEqual(session.get.call_args.kwargs['timeout'], 5)
