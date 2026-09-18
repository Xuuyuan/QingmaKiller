"""内置网络题库: 源配置、搜题协议、解密与答案聚合的离线回归测试。"""
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import tiku

FIXTURE_BUGUAKE = os.path.join(os.path.dirname(__file__), 'fixtures', 'buguake_sample.json')


def _json_response(payload, status_code=200):
    response = Mock(status_code=status_code)
    response.json.return_value = payload
    response.text = json.dumps(payload, ensure_ascii=False)
    return response


class SourceConfigTest(unittest.TestCase):
    """banks.json 源配置的载入与容错。"""

    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.config_path = os.path.join(tmp_dir.name, 'banks.json')
        patcher = patch.object(tiku, 'BANKS_FILE', self.config_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(setattr, tiku, 'source_config', None)
        tiku.source_config = None

    def _write(self, data):
        with open(self.config_path, 'w', encoding='utf-8') as fp:
            json.dump(data, fp, ensure_ascii=False)

    def test_missing_file_uses_defaults(self):
        config = tiku.enabled_sources()
        self.assertEqual(set(config), set(tiku.SOURCE_DEFAULTS))
        self.assertTrue(config['buguake']['enable'])
        self.assertTrue(config['icodef']['enable'])
        self.assertTrue(config['wanneng']['enable'])
        self.assertTrue(config['tikuhai']['enable'])
        self.assertFalse(config['enncy']['enable'])
        self.assertFalse(config['aidian']['enable'])
        self.assertFalse(config['lemon']['enable'])

    def test_broken_file_is_backed_up_and_defaults_used(self):
        with open(self.config_path, 'w', encoding='utf-8') as fp:
            fp.write('{broken json')
        config = tiku.enabled_sources()
        self.assertEqual(config, {name: dict(d) for name, d in tiku.SOURCE_DEFAULTS.items()})
        self.assertTrue(os.path.exists(self.config_path + '.broken'))

    def test_paid_source_enabled_via_config(self):
        self._write({'enncy': {'enable': True, 'token': 'T1'}, 'lemon': {'enable': True}})
        config = tiku.enabled_sources()
        self.assertEqual(config['enncy'], {'enable': True, 'token': 'T1'})
        self.assertEqual(config['lemon']['token'], '')  # 未填token时客户端自动跳过
        self.assertFalse(config['aidian']['enable'])  # 未提及的源保持默认

    def test_unknown_sources_and_fields_are_ignored(self):
        self._write({'icodef': {'token': 'T2', 'unknown': 1}, 'nonsense': {'enable': True}, 'version': 9})
        config = tiku.enabled_sources()
        self.assertEqual(config['icodef'], {'enable': True, 'token': 'T2'})
        self.assertNotIn('nonsense', config)

    def test_non_boolean_enable_keeps_default(self):
        self._write({'buguake': {'enable': 'false'}, 'enncy': {'enable': 1}})
        config = tiku.enabled_sources()
        self.assertTrue(config['buguake']['enable'])
        self.assertFalse(config['enncy']['enable'])


class BuguakeDecryptTest(unittest.TestCase):
    """不挂科响应解密, 使用真实接口抓取的样本fixture。"""

    def test_real_sample(self):
        with open(FIXTURE_BUGUAKE, encoding='utf-8') as fp:
            sample = json.load(fp)
        detail = json.loads(tiku._buguake_decrypt(sample['bdjson'], sample['actk']))
        self.assertEqual(tiku._dig(detail, 'que_stem', 0, 'c', 0, 'c'), '中国的首都是哪里?')
        self.assertEqual(tiku._buguake_answer_texts(detail), ['北京'])
        self.assertEqual(tiku._buguake_correct_options(detail), [])

    def test_invalid_base64_returns_empty(self):
        self.assertEqual(tiku._buguake_decrypt('A', 'actk'), '')


class BuguakeSearchTest(unittest.TestCase):
    """不挂科源的相似度过滤与答案提取。"""

    def test_low_similarity_candidates_are_dropped(self):
        dissimilar = json.dumps({'que_stem': [{'c': [{'c': '完全无关的其他题目内容'}]}],
                                 'que_answer': [{'c': [{'c': '错误答案'}]}]}, ensure_ascii=False)
        similar = json.dumps({'que_stem': [{'c': [{'c': '中国的首都是哪里'}]}],
                              'que_answer': [{'c': [{'c': '北京'}]}]}, ensure_ascii=False)
        response = Mock(status_code=200)
        response.json.return_value = {'data': {'list': [{'bdjson': 'x'}, {'bdjson': 'y'}]}}
        with patch.object(tiku, '_buguake_decrypt', side_effect=[dissimilar, similar]), \
                patch.object(tiku.requests, 'get', return_value=response) as get:
            sets = tiku._search_buguake('中国的首都是哪里', [], 0, {})
        self.assertEqual(sets, [['北京']])
        get.assert_called_once_with(tiku.buguake_api,
                                    params={'query': '中国的首都是哪里', 'rn': '10', 'pn': '0'}, timeout=3)

    def test_correct_options_take_priority_over_answer_texts(self):
        detail = {'que_options': [[{'yes': True, 'ret': [{'c': [{'c': '北京'}]}]},
                                   {'yes': False, 'ret': [{'c': [{'c': '上海'}]}]}]],
                  'que_answer': [{'c': [{'c': '其他'}]}]}
        self.assertEqual(tiku._buguake_correct_options(detail), ['北京'])
        self.assertEqual(tiku._buguake_answer_texts(detail), ['其他'])


class ClientProtocolTest(unittest.TestCase):
    """各题库源的请求构造与响应解析。"""

    def test_icodef_rejects_non_text_answers(self):
        for value in (42, True, ['甲'], {'answer': '甲'}, None):
            with self.subTest(value=value), patch.object(tiku.requests, 'post',
                    return_value=_json_response({'code': 1, 'data': value})):
                self.assertEqual(tiku._search_icodef('q', ['甲'], 0, {}), [])

    def test_aidian_preserves_valid_candidate_after_malformed_ones(self):
        payload = {'qlist': [None, {'options': [42], 'answer': ['A']},
                            {'options': ['甲'], 'answer': [{'text': '甲'}]},
                            {'options': ['甲'], 'answer': 'A'},
                            {'options': ['甲'], 'answer': ['A']}]}
        with patch.object(tiku.requests, 'post', return_value=_json_response(payload)):
            self.assertEqual(tiku._search_aidian('q', ['甲'], 0, {}), [['甲']])

    def test_buguake_preserves_valid_candidate_after_bad_nested_data(self):
        stem = {'que_stem': [{'c': [{'c': 'q'}]}]}
        details = [dict(stem, que_options=[42]),
                   dict(stem, que_answer=[{'c': [{'c': 42}]}]),
                   dict(stem, que_answer=[{'c': [{'c': '甲'}]}])]
        payload = {'data': {'list': [{'bdjson': 'x'} for _ in details]}}
        with patch.object(tiku.requests, 'get', return_value=_json_response(payload)), \
                patch.object(tiku, '_buguake_decrypt', side_effect=map(json.dumps, details)):
            self.assertEqual(tiku._search_buguake('q', ['甲'], 0, {}), [['甲']])

    def test_icodef_retries_on_flow_control_and_parses(self):
        flow_control = Mock(status_code=200, text='触发流控限制')
        good = _json_response({'code': 1, 'data': '甲#乙'})
        with patch.object(tiku.requests, 'post', side_effect=[flow_control, good]) as post, \
                patch.object(tiku.time, 'sleep') as sleep:
            sets = tiku._search_icodef('q', ['甲', '乙'], 0, {'token': 'T1'})
        self.assertEqual(sets, [['甲', '乙']])
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once()
        self.assertEqual(post.call_args.kwargs['headers'], {'Authorization': 'T1'})

    def test_icodef_no_answer(self):
        response = _json_response({'code': 0, 'data': ''})
        with patch.object(tiku.requests, 'post', return_value=response):
            self.assertEqual(tiku._search_icodef('q', [], 0, {}), [])

    def test_wanneng_maps_index_answers_and_weights_votes(self):
        payload = {'code': 0, 'result': {'success': True, 'answers': [1, '丙']}}
        with patch.object(tiku.requests, 'post', return_value=_json_response(payload)) as post:
            sets = tiku._search_wanneng('q', ['甲', '乙', '丙'], 1, {})
        self.assertEqual(sets, [['乙', '丙']] * 10)  # 原实现重复10份以加权投票
        call = post.call_args
        self.assertEqual(call.args[0], tiku.wanneng_free_api)
        self.assertEqual(call.kwargs['json']['options'], ['甲', '乙', '丙'])
        self.assertEqual(call.kwargs['headers'], {'plat': '0'})

    def test_wanneng_uses_paid_url_with_ten_char_token(self):
        payload = {'code': 0, 'result': {'success': False, 'answers': []}}
        with patch.object(tiku.requests, 'post', return_value=_json_response(payload)) as post:
            self.assertEqual(tiku._search_wanneng('q', [], 0, {'token': '0123456789'}), [])
        self.assertEqual(post.call_args.args[0], tiku.wanneng_api.format('0123456789'))

    def test_wanneng_out_of_range_index_is_dropped(self):
        payload = {'code': 0, 'result': {'success': True, 'answers': [9, '甲']}}
        with patch.object(tiku.requests, 'post', return_value=_json_response(payload)):
            self.assertEqual(tiku._search_wanneng('q', ['甲'], 0, {}), [['甲']] * 10)

    def test_wanneng_rejects_non_integer_indexes(self):
        payload = {'code': 0, 'result': {'success': True, 'answers': [1.5, True, '甲']}}
        with patch.object(tiku.requests, 'post', return_value=_json_response(payload)):
            self.assertEqual(tiku._search_wanneng('q', ['甲', '乙'], 0, {}), [['甲']] * 10)

    def test_tikuhai_retries_on_server_error(self):
        bad = Mock(status_code=500)
        bad.json.return_value = {}
        good = _json_response({'code': 200, 'data': {'answer': ['甲', '乙']}})
        with patch.object(tiku.requests, 'post', side_effect=[bad, good]) as post, \
                patch.object(tiku.time, 'sleep'):
            sets = tiku._search_tikuhai('q', ['甲', '乙'], 1, {'key': 'K1'})
        self.assertEqual(sets, [['甲', '乙']])
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.kwargs['json']['key'], 'K1')
        self.assertEqual(post.call_args.kwargs['headers']['User-Agent'], 'tikuhaiAdapter/0.1.0')

    def test_tikuhai_accepts_string_data(self):
        response = _json_response({'code': 200, 'data': json.dumps({'answer': ['甲']})})
        with patch.object(tiku.requests, 'post', return_value=response):
            self.assertEqual(tiku._search_tikuhai('q', ['甲'], 0, {}), [['甲']])

    def test_enncy_requires_token(self):
        with patch.object(tiku.requests, 'get') as get:
            self.assertEqual(tiku._search_enncy('q', [], 0, {'token': ''}), [])
        get.assert_not_called()

    def test_enncy_parses_answer(self):
        with patch.object(tiku.requests, 'get', return_value=_json_response(
                {'code': 1, 'data': {'question': 'q', 'answer': '甲#乙'}})) as get:
            sets = tiku._search_enncy('q', [], 0, {'token': 'T1'})
        self.assertEqual(sets, [['甲', '乙']])
        self.assertEqual(get.call_args.kwargs['params'], {'token': 'T1', 'title': 'q'})

    def test_aidian_maps_letter_answers_to_option_texts(self):
        payload = {'code': 0, 'qlist': [{'options': ['A. 甲', 'B. 乙', 'C. 丙'], 'answer': ['AB', '丁']}]}
        with patch.object(tiku.requests, 'post', return_value=_json_response(payload)) as post:
            sets = tiku._search_aidian('q', [], 1, {})
        self.assertEqual(sets, [['甲', '乙', '丁']])
        self.assertEqual(post.call_args.args[0], tiku.aidian_free_api)  # 无token走免费接口

    def test_aidian_uses_paid_url_with_token(self):
        payload = {'code': 0, 'qlist': []}
        with patch.object(tiku.requests, 'post', return_value=_json_response(payload)) as post:
            self.assertEqual(tiku._search_aidian('q', [], 1, {'token': 'T1'}), [])
        self.assertEqual(post.call_args.args[0], tiku.aidian_api)

    def test_lemon_requires_token_and_parses(self):
        with patch.object(tiku.requests, 'post') as post:
            self.assertEqual(tiku._search_lemon('q', [], 0, {'token': ''}), [])
        post.assert_not_called()
        with patch.object(tiku.requests, 'post', return_value=_json_response(
                {'code': 1000, 'data': {'answer': '甲#乙'}})) as post:
            sets = tiku._search_lemon('q', [], 0, {'token': 'T1'})
        self.assertEqual(sets, [['甲', '乙']])
        self.assertEqual(post.call_args.kwargs['headers'], {'Authorization': 'Bearer T1'})
        self.assertEqual(post.call_args.kwargs['json']['uid'], '703382225')


class AggregateTest(unittest.TestCase):
    """多源答案投票与规整。"""

    def test_majority_vote(self):
        self.assertEqual(tiku._aggregate([['甲'], ['甲'], ['乙']], ['甲', '乙'], 0), ['甲'])

    def test_wanneng_multiple_copies_weight_the_vote(self):
        answer_sets = [['乙']] + [['甲']] * 10
        self.assertEqual(tiku._aggregate(answer_sets, ['甲', '乙'], 0), ['甲'])

    def test_multi_choice_exact_match_needs_two_options(self):
        self.assertEqual(tiku._aggregate([['甲']], ['甲', '乙', '丙'], 1), [])
        self.assertEqual(tiku._aggregate([['甲', '乙']], ['甲', '乙', '丙'], 1), ['甲', '乙'])

    def test_fuzzy_fallback_for_single_choice(self):
        self.assertEqual(tiku._aggregate([['平果']], ['苹果', '香蕉'], 0), ['苹果'])
        self.assertEqual(tiku._aggregate([['完全无关的答案']], ['苹果', '香蕉'], 0), [])

    def test_buguake_skips_malformed_candidates(self):
        response = Mock(status_code=200)
        response.json.return_value = {'data': {'list': [None, {'bdjson': 'valid', 'actk': ''}]}}
        detail = {'que_stem': [{'c': [{'c': '中国的首都是哪里'}]}],
                  'que_answer': [{'c': [{'c': '北京'}]}]}
        with patch.object(tiku, '_buguake_decrypt', return_value=json.dumps(detail)), \
                patch.object(tiku.requests, 'get', return_value=response):
            self.assertEqual(tiku._search_buguake('中国的首都是哪里', [], 0, {}), [['北京']])

    def test_no_options_votes_on_raw_answers(self):
        self.assertEqual(tiku._aggregate([['甲'], ['甲'], ['乙']], [], 0), ['甲'])

    def test_answer_letters(self):
        self.assertEqual(tiku._answer_letters(['乙'], ['甲', '乙', '丙']), 'B')
        self.assertEqual(tiku._answer_letters(['不存在'], ['甲']), '')

    def test_format_helpers(self):
        self.assertEqual(tiku._format_string('ａｂｃ，“北京”。'), 'abc,"北京"')
        self.assertEqual(tiku._format_options(['A. 甲', 'B．乙', 'C、丙']), ['甲', '乙', '丙'])


class SearchContractTest(unittest.TestCase):
    """search() 对外契约: None=网络题库不可用, 空串=未命中, 其余为选项字母串。"""

    def tearDown(self):
        tiku.source_config = None

    def run_search(self, clients, sources=None, question_type=0, options=None):
        tiku.source_config = sources if sources is not None else {'x': {'enable': True}}
        with patch.dict(tiku._SOURCE_CLIENTS, clients, clear=True):
            return tiku.search('test', question_type, options if options is not None else ['甲', '乙', '丙'])

    def test_no_enabled_sources_returns_none(self):
        def client(*args):
            self.fail('禁用的源不应被调用')

        self.assertIsNone(self.run_search({'x': client}, sources={'x': {'enable': False}}))

    def test_all_sources_failed_returns_none(self):
        def client(*args):
            raise OSError('network down')

        self.assertIsNone(self.run_search({'x': client}))

    def test_no_answer_returns_empty_string(self):
        self.assertEqual(self.run_search({'x': lambda *args: []}), '')

    def test_hit_returns_letters_and_single_choice_trims(self):
        self.assertEqual(self.run_search({'x': lambda *args: [['乙']]}), 'B')
        self.assertEqual(self.run_search({'x': lambda *args: [['甲', '乙']]}, options=['甲', '乙']), 'A')

    def test_multi_choice_rejects_single_letter(self):
        self.assertEqual(self.run_search({'x': lambda *args: [['甲']]}, question_type=1), '')

    def test_multi_choice_letters_follow_option_order(self):
        self.assertEqual(self.run_search({'x': lambda *args: [['乙', '甲']]}, question_type=1), 'AB')

    def test_search_passes_options_and_type_to_real_clients(self):
        payloads = {
            'wanneng': {'code': 0, 'result': {'success': True, 'answers': [1]}},
            'tikuhai': {'code': 200, 'data': {'answer': ['乙']}},
        }
        for name, payload in payloads.items():
            with self.subTest(source=name), patch.object(
                    tiku.requests, 'post', return_value=_json_response(payload)) as post:
                result = self.run_search(
                    {name: tiku._SOURCE_CLIENTS[name]},
                    sources={name: {'enable': True}}, options=['甲', '乙'])
                self.assertEqual(result, 'B')
                self.assertEqual(post.call_args.kwargs['json']['options'], ['甲', '乙'])
                self.assertEqual(post.call_args.kwargs['json']['type'], 0)

    def test_malformed_source_does_not_discard_healthy_answer(self):
        malformed = (None, 42, '乙', {'answer': ['乙']}, [42], ['乙'],
                     [[42]], [[None]], [[True]], [[{}]], [[['乙']]])
        for value in malformed:
            with self.subTest(value=value):
                clients = {'bad': lambda *args: value, 'good': lambda *args: [['乙']]}
                sources = {name: {'enable': True} for name in clients}
                self.assertEqual(self.run_search(clients, sources=sources), 'B')
                self.assertIsNone(self.run_search({'x': lambda *args: value}))

    def test_real_client_malformed_answer_is_isolated(self):
        response = _json_response({'code': 200, 'data': {'answer': [42]}})
        clients = {'tikuhai': tiku._search_tikuhai, 'good': lambda *args: [['乙']]}
        sources = {name: {'enable': True} for name in clients}
        with patch.object(tiku.requests, 'post', return_value=response):
            self.assertEqual(self.run_search(clients, sources=sources), 'B')

    def test_source_error_logs_do_not_expose_request_secrets(self):
        token = 'FAKE_REVIEW_TOKEN'
        cases = (
            ('enncy', 'get', f'https://example.test/query?token={token}&title=private_question'),
            ('wanneng', 'post', f'https://example.test/autoAnswer/{token}'),
        )
        for name, method, url in cases:
            with self.subTest(source=name), patch.object(
                    tiku.requests, method,
                    side_effect=tiku.requests.ConnectionError(f'Max retries exceeded: {url}')), \
                    patch.object(tiku.logger, 'warning') as warning:
                self.assertIsNone(self.run_search(
                    {name: tiku._SOURCE_CLIENTS[name]},
                    sources={name: {'enable': True, 'token': token}}))
                message = warning.call_args.args[0]
                self.assertIn(name, message)
                self.assertIn('ConnectionError', message)
                self.assertNotIn(token, message)
                self.assertNotIn(url, message)
                self.assertNotIn('private_question', message)


if __name__ == '__main__':
    unittest.main()
