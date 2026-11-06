import hashlib
import io
import json
import unittest
from unittest.mock import patch

import web_proxy


class AdminAccessTests(unittest.TestCase):
    def setUp(self):
        web_proxy.SESSIONS.clear()
        self.handler = object.__new__(web_proxy.Handler)
        self.responses = []
        self.handler.respond = lambda *args: self.responses.append(args)
        self.handler.headers = {}
        self.handler.rfile = io.BytesIO()

    def login(self, password):
        body = json.dumps({'username': 'emanuele', 'password': password}).encode()
        self.handler.headers = {'Content-Length': str(len(body))}
        self.handler.rfile = io.BytesIO(body)
        self.handler.login()
        return self.responses[-1]

    def test_login_job_access_and_logout(self):
        with patch.object(web_proxy, 'ADMIN_HASH', hashlib.sha256(b'test-password').hexdigest()):
            self.assertEqual(self.login('wrong')[0], 401)
            self.handler.path = '/api/wefix/jobs'
            self.handler.proxy('GET')
            self.assertEqual(self.responses[-1][0], 401)
            response = self.login('test-password')
            self.assertEqual(response[0], 200)
            self.handler.headers = {'Cookie': response[2].split(';')[0]}
            self.assertTrue(self.handler.is_admin())
            self.handler.logout()
            self.assertFalse(self.handler.is_admin())
            self.handler.proxy('POST')
            self.assertEqual(self.responses[-1][0], 401)

    def test_missing_password_configuration_denies_login(self):
        with patch.object(web_proxy, 'ADMIN_HASH', ''):
            self.assertEqual(self.login('anything')[0], 401)


if __name__ == '__main__':
    unittest.main()
