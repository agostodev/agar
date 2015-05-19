from env_setup import setup_django; setup_django()

from unittest import TestCase

from agar.django.templates import render_template_to_string


class DjangoTemplatesTest(TestCase):

    def test_render_template_to_string(self):
        self.assertEqual("<strong>hello world</strong>\n",
                         render_template_to_string("test_template.html",
                                                   context={'message': 'hello world'}))
