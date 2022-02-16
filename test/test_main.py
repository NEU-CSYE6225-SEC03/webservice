import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Add path of cwd to sys
from tornado.test.util import unittest
from tornado.testing import AsyncHTTPTestCase
from service.service_main import make_app


class BaseTest(AsyncHTTPTestCase):
    def setUp(self):
        pass
        super(BaseTest, self).setUp()


class HealthzTest(BaseTest):
    def get_app(self):
        return make_app()

    def test(self):
        response = self.fetch('/healthz', method='GET')
        self.assertEqual(response.code, 400)


if __name__ == '__main__':
    unittest.main()
