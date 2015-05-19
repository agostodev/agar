from env_setup import setup_django; setup_django()

from unittest import TestCase

from django.template import Context, Template, TemplateSyntaxError
from django.template import add_to_builtins
add_to_builtins('agar.django.templatetags')


class DjangoTemplatesTest(TestCase):
    def test_login_url_tag(self):
        out = Template("{% create_login_url index %}").render(Context())
        self.assertEqual(out, u'/_ah/login?continue=http%3A//localhost/index')

    def test_login_url_tag_missing_path(self):
        with self.assertRaises(TemplateSyntaxError):
            Template("{% create_login_url %}").render(Context())

    def test_logout_url_tag(self):
        out = Template("{% create_logout_url index %}").render(Context())
        self.assertEqual(out, u'/_ah/login?continue=http%3A//localhost/index&action=Logout')

    def test_logout_url_tag_missing_path(self):
        with self.assertRaises(TemplateSyntaxError):
            Template("{% create_logout_url %}").render(Context())
