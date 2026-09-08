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
    def test_request_retries_then_succeeds(self):
        response = Mock(text='{"message": "回答正确！"}', url='http://example.test')
        with patch.object(api.session, 'post', side_effect=[api.requests.Timeout(), api.requests.ConnectionError(), response]) as post, patch.object(api.time, 'sleep'):
            self.assertEqual(api.submit_answer({}, '7', 'same-uuid', 'A')['message'], '回答正确！')
        self.assertEqual(post.call_count, 3)
        self.assertTrue(all(call.kwargs['data']['uuid'] == 'same-uuid' for call in post.call_args_list))

    def test_request_failure_escapes_after_three_attempts(self):
        with patch.object(api.session, 'get', side_effect=api.requests.Timeout()) as get, patch.object(api.time, 'sleep'):
            with self.assertRaises(api.requests.Timeout):
                main.validate_cookie('test')
        self.assertEqual(get.call_count, 3)

    def test_http_error_is_retried(self):
        response = Mock()
        response.raise_for_status.side_effect = api.requests.HTTPError()
        with patch.object(api.session, 'get', return_value=response) as get, patch.object(api.time, 'sleep'):
            with self.assertRaises(api.requests.HTTPError):
                api.get_course_list('test')
        self.assertEqual(get.call_count, 3)

    def test_empty_courses_end_before_input_or_adapter_start(self):
        response = Mock(status_code=200, text='<html></html>')
        with patch.object(api.session, 'get', return_value=response):
            course_list = api.get_course_list('test')
        with patch.object(main, 'acquire_session', return_value=('test', course_list)), patch.object(main, 'ensure_tiku_adapter') as adapter, patch('builtins.input') as user_input:
            main.main()
        adapter.assert_not_called()
        user_input.assert_not_called()

    def test_quit_before_start_does_not_start_adapter(self):
        with patch.object(main, 'acquire_session', return_value=('test', {'courses': {'7': 'test'}})), patch.object(main, 'select_subject', return_value='7'), patch.object(main, 'collect_config', return_value=cli.RunConfig(0, 0, 0, 1, .6, .9)), patch.object(main, 'ensure_tiku_adapter') as adapter, patch('builtins.input', return_value='q'):
            with self.assertRaises(main.UserQuit):
                main.main()
        adapter.assert_not_called()

    def test_adapter_timeout_skips_without_retry(self):
        with patch.object(tiku.session, 'post', side_effect=tiku.requests.Timeout()) as post:
            self.assertIsNone(tiku.search('test', 0, ['a', 'b']))
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs['timeout'], 5)

    def test_session_confirmation_is_not_repeated(self):
        with patch.object(main, 'session_confirmed', False), patch.object(main, 'load_saved_session', return_value=('test', None)), patch.object(main, 'validate_cookie', return_value={'courses': {}}), patch.object(main, '_ask_use_saved_session', return_value=True) as ask:
            self.assertEqual(main.acquire_session(), ('test', {'courses': {}}))
            self.assertEqual(main.acquire_session(), ('test', {'courses': {}}))
            ask.assert_called_once_with(None)

    def test_correct_wrong_and_cooldown_statistics(self):
        question = dict(question='test', description='test', text_options='A. test', type=0, options=['test'], uuid='test')
        responses = [
            {'message': '回答错误！', 'data': {'rightOption': 'encrypted'}},
            {'message': '您的答题速度过快，请认真答题，30s后可继续答题.'},
            {'message': '回答正确！'},
            {'message': '回答正确！'},
        ]
        with ExitStack() as stack:
            for name in ('ensure_tiku_adapter', 'countdown'):
                stack.enter_context(patch.object(main, name))
            stack.enter_context(patch.object(main.time, 'sleep'))
            stack.enter_context(patch.object(main, 'acquire_session', return_value=('test', {'courses': {'7': 'test'}})))
            stack.enter_context(patch.object(main, 'select_subject', return_value='7'))
            stack.enter_context(patch.object(main, 'collect_config', return_value=cli.RunConfig(0, 0, 0, 1, 0.6, 0.9)))
            bank_class = stack.enter_context(patch.object(main, 'QuestionBank'))
            stack.enter_context(patch('builtins.input', return_value=''))
            stack.enter_context(patch.object(main, 'fetch_question', return_value=question))
            stack.enter_context(patch.object(main, 'decide_answer', return_value=(True, 'A', None)))
            stack.enter_context(patch.object(main, 'decrypt', return_value='B'))
            submit = stack.enter_context(patch.object(main, 'submit_answer', side_effect=responses))
            summary = stack.enter_context(patch.object(main, 'print_run_summary'))
            main.main()
            self.assertEqual(submit.call_count, 4)
            args = summary.call_args.args
            self.assertEqual(args[0], dict(correct=2, wrong=1, anti=0, no_answer=0, adapter=0, cooldown=1))
            self.assertEqual(args[2:5], (3, 2, 2 / 3))
            bank_class.return_value.record.assert_any_call('test', 'A. test', 'B', 'B')

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
            with self.subTest(answer=answer), patch.object(tiku.session, 'post', return_value=Mock(
                    text=json.dumps({'answer': {'answerKeyText': answer}}), status_code=200)):
                self.assertIsNone(tiku.search('test', 1, ['a', 'b']))

    def test_adapter_empty_and_valid_answers(self):
        for answer, expected in ((None, ''), ('', ''), ('A', 'A'), ('AB', 'A')):
            with self.subTest(answer=answer), patch.object(tiku.session, 'post', return_value=Mock(
                    text=json.dumps({'answer': {'answerKeyText': answer}}), status_code=200)):
                self.assertEqual(tiku.search('test', 0, ['a', 'b']), expected)

    def test_site_requests_have_five_second_timeout(self):
        response = Mock(status_code=302, text='{"data": {}, "message": "test"}', url='http://example.test')
        with patch.object(api.session, 'get', return_value=response) as get:
            api.get_course_list('test')
            self.assertEqual(get.call_args.kwargs['timeout'], 5)
        with patch.object(api.session, 'post', return_value=response) as post:
            api.fetch_question({}, '7')
            api.submit_answer({}, '7', 'test', 'A')
            self.assertEqual([c.kwargs['timeout'] for c in post.call_args_list], [5, 5])
        session = Mock()
        session.get.side_effect = auth.requests.Timeout()
        with patch.object(auth, '_new_session', return_value=session):
            self.assertEqual(auth.handshake_from_url('http://example.test'), (None, '网络请求失败'))
            self.assertEqual(session.get.call_args.kwargs['timeout'], 5)
