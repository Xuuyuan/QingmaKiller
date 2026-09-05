"""auth 模块纯逻辑部分的单元测试, 运行方式: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth  # noqa: E402
import requests  # noqa: E402

ERROR_PAGE_BODY = ('<body class="error"> <div class="mui-content">'
                   '<div class="mui-popup-text">请文明上网</div></div>')
NORMAL_PAGE_BODY = '<!doctype html> <html> <head><title>青马易战</title></head> <body></body>'


class ExtractJsessionidTest(unittest.TestCase):
    def test_extracts_site_cookie(self):
        session = requests.Session()
        session.cookies.set('JSESSIONID', 'ABC123', domain='sdyb.fjhdrs.com', path='/yiban-web')
        self.assertEqual(auth._extract_jsessionid(session), 'JSESSIONID=ABC123')

    def test_ignores_other_domains(self):
        session = requests.Session()
        session.cookies.set('JSESSIONID', 'XYZ789', domain='oauth.yiban.cn', path='/')
        self.assertIsNone(auth._extract_jsessionid(session))

    def test_missing_cookie(self):
        self.assertIsNone(auth._extract_jsessionid(requests.Session()))


class SiteErrorPageTest(unittest.TestCase):
    def test_error_page_detected(self):
        self.assertTrue(auth._is_site_error_page(ERROR_PAGE_BODY))

    def test_normal_page_not_detected(self):
        self.assertFalse(auth._is_site_error_page(NORMAL_PAGE_BODY))


class SessionPersistenceTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._origin_file = auth.session_file
        auth.session_file = os.path.join(self._tmpdir.name, 'session.json')

    def tearDown(self):
        auth.session_file = self._origin_file
        self._tmpdir.cleanup()

    def test_round_trip(self):
        self.assertIsNone(auth.load_saved_session())
        auth.save_session('JSESSIONID=ABC123')
        jsessionid, saved_at = auth.load_saved_session()
        self.assertEqual(jsessionid, 'JSESSIONID=ABC123')
        self.assertIsInstance(saved_at, int)
        auth.clear_saved_session()
        self.assertIsNone(auth.load_saved_session())

    def test_legacy_file_without_saved_at(self):
        with open(auth.session_file, 'w', encoding='utf-8') as fp:
            json.dump({'jsessionid': 'JSESSIONID=ABC123'}, fp)
        self.assertEqual(auth.load_saved_session(), ('JSESSIONID=ABC123', None))

    def test_non_integer_saved_at_ignored(self):
        with open(auth.session_file, 'w', encoding='utf-8') as fp:
            json.dump({'jsessionid': 'JSESSIONID=ABC123', 'saved_at': 'yesterday'}, fp)
        self.assertEqual(auth.load_saved_session(), ('JSESSIONID=ABC123', None))

    def test_corrupted_file_returns_none(self):
        with open(auth.session_file, 'w', encoding='utf-8') as fp:
            fp.write('not-json{')
        self.assertIsNone(auth.load_saved_session())

    def test_malformed_cookie_rejected(self):
        auth.save_session('garbage-without-prefix')
        self.assertIsNone(auth.load_saved_session())


if __name__ == '__main__':
    unittest.main()
