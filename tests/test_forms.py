from webtest import TestApp

from webapp2 import Request, uri_for
from agar.test import BaseTest, WebTest

from api import application


class JsonWebTestCase(BaseTest):
    def assertOK(self, response):
        self.assertValidResponse(response)
        super(JsonWebTestCase, self).assertOK(response)
        result = response.json
        self.assertEqual(result['status_code'], 200)
        self.assertEqual(result['status_text'], 'OK')

    def assertValidResponse(self, response):
        try:
            result = response.json
            self.assertEqual(len(result), 4)
            self.assertIsNotNone(result['status_code'])
            self.assertIsNotNone(result['status_text'])
            self.assertIsNotNone(result['timestamp'])
            self.assertIsNotNone(result['data'])
        except ValueError:
            self.fail('Not a valid JSON response (status_code: %s): %s' % (response.status_int, response.body))

    def assertErrorResponse(self, response):
        try:
            result = response.json
            self.assertEqual(len(result), 5)
            self.assertIsNotNone(result['status_code'])
            self.assertIsNotNone(result['status_text'])
            self.assertIsNotNone(result['timestamp'])
            self.assertIsNotNone(result['data'])
            self.assertIsNotNone(result['errors'])
        except ValueError:
            self.fail('Not a valid JSON response (status_code: %s): %s' % (response.status_int, response.body))

    def assertBadRequest(self, response, message='', errors=None):
        self.assertErrorResponse(response)
        self.assertEqual(response.status_int, 400)
        result = response.json
        self.assertEqual(result['status_code'], 400)
        status_text = "BAD_REQUEST"
        if message:
            status_text = "%s: %s" % (status_text, message)
        self.assertEqual(result['status_text'], status_text)
        self.assertEqual(result['errors'], errors)


class FormTest(JsonWebTestCase, WebTest):
    APPLICATION = application

    def setUp(self):
        self.test_app = TestApp(self.APPLICATION)
        super(FormTest, self).setUp()

    def test_get(self):
        uri = self.APPLICATION.router.build(None, 'api-v1', None, {})
        response = self.test_app.get(uri)
        self.assertOK(response)
        data = response.json['data']
        self.assertEqual(len(data), 2)
        models = data[0]
        self.assertEqual(len(models), 10)
        cursor = data[1]
        self.assertIsNotNone(cursor)

    def test_get_page_size(self):
        uri = self.APPLICATION.router.build(None, 'api-v1', None, {'page_size': 5})
        response = self.test_app.get(uri)
        self.assertOK(response)
        data = response.json['data']
        self.assertEqual(len(data), 2)
        models = data[0]
        self.assertEqual(len(models), 5)
        cursor = data[1]
        self.assertIsNotNone(cursor)

    def test_invalid_param(self):
        uri = self.APPLICATION.router.build(None, 'api-v1', None, {'foo': 'bar'})
        response = self.test_app.get(uri, status=400)
        self.assertBadRequest(response, errors={u'foo': u'* Not a recognized parameter'})
