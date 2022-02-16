import os

from tornado.test.util import unittest
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from service_main import HealthzHandler

class BaseTest(AsyncHTTPTestCase):
    def setUp(self):
        pass
        super(BaseTest, self).setUp()


class WebHandlerTest(BaseTest):

    def get_app(self):
        return Application([
            ('/healthz', HealthzHandler),
        ])

    def test_sub(self):
        response = self.fetch('/healthz', method='GET')
        self.assertEqual(response.code, 400)

if __name__ == '__main__':
    unittest.main()

