import unittest
from unittest import mock

from services import ai


class R:
    def __init__(self, code, body=None, text=""):
        self.status_code, self._b, self.text = code, body, text

    def json(self):
        return self._b


def ok(text="OK"):
    return R(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})


class GeminiFallbackTests(unittest.TestCase):
    def run_it(self, post):
        ai._gemini_ok.clear()
        with mock.patch.object(ai, "load_config", return_value={}), mock.patch.object(ai, "api_key", return_value="k"), \
                mock.patch.object(ai.requests, "post", post):
            return ai._gemini("s", [{"role": "user", "content": "hi"}], 20)

    def test_retired_model_falls_back_to_next(self):
        seen = []

        def post(url, **kw):
            seen.append(url)
            return R(404, text="gone") if "gemini-3.5-flash:" in url else ok("hello")
        self.assertEqual(self.run_it(post), "hello")
        self.assertEqual(len(seen), 2)

    def test_bad_key_is_reported_as_auth(self):
        with self.assertRaises(ai.AIError) as cm:
            self.run_it(lambda url, **kw: R(400, text="API key not valid"))
        self.assertEqual(cm.exception.code, "auth")


if __name__ == "__main__":
    unittest.main()
