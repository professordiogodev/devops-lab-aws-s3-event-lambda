"""Local tests. No AWS account needed: S3 is replaced by a tiny fake.  Run:  python3 -m unittest discover -s tests -v"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import handler  # noqa: E402


class FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.puts = []

    def get_object(self, Bucket, Key):
        class B:
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data

        return {"Body": B(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, **kw):
        self.puts.append(Key)
        self.objects[Key] = Body if isinstance(Body, bytes) else Body.encode()


def event(*keys):
    return {"Records": [{"s3": {"bucket": {"name": "b"}, "object": {"key": k}}} for k in keys]}


GOOD = "short_code,url\nabc-1,https://ironhack.com\nxyz,http://example.com/a,b\n"


class ProcessTests(unittest.TestCase):
    def test_good_file(self):
        r = handler.process("short_code,url\nabc-1,https://ironhack.com\ndocs,http://example.com/x\n")
        self.assertEqual(r, {"ok": True, "source_rows": 2, "valid": 2, "invalid": []})

    def test_empty(self):
        self.assertEqual(handler.process("  \n\n"), {"ok": False, "error": "empty file"})

    def test_bad_header(self):
        self.assertEqual(handler.process("code,link\na,b\n")["error"], "unexpected header")

    def test_no_rows(self):
        self.assertEqual(handler.process("short_code,url\n\n\n"), {"ok": False, "error": "no data rows"})

    def test_invalid_rows_are_listed_with_line_numbers(self):
        text = "short_code,url\nok-1,https://a.io\nBAD CODE,https://a.io\nab,https://a.io\nfine,ftp://a.io\nonly-one\n\nlast,https://z.io\n"
        r = handler.process(text)
        self.assertTrue(r["ok"])
        self.assertEqual((r["source_rows"], r["valid"]), (6, 2))
        self.assertEqual(r["invalid"], [
            {"line": 3, "reason": "bad short_code"},
            {"line": 4, "reason": "bad short_code"},
            {"line": 5, "reason": "bad url"},
            {"line": 6, "reason": "wrong number of columns"},
        ])

    def test_quoted_commas_are_one_column(self):
        r = handler.process('short_code,url\nabc,"https://a.io/x,y"\n')
        self.assertEqual((r["valid"], r["invalid"]), (1, []))

    def test_windows_line_endings(self):
        self.assertEqual(handler.process("short_code,url\r\nabc,https://a.io\r\n")["valid"], 1)


class HandlerTests(unittest.TestCase):
    def test_good_file_gets_a_report(self):
        s3 = FakeS3({"inbox/links.csv": GOOD.encode()})
        out = handler.lambda_handler(event("inbox/links.csv"), None, s3=s3)
        self.assertEqual(s3.puts, ["processed/links.json"])
        rep = json.loads(s3.objects["processed/links.json"])
        self.assertEqual((rep["source_rows"], rep["valid"]), (2, 1))
        self.assertEqual(out, {"processed": 1})

    def test_bad_file_gets_an_error_note(self):
        s3 = FakeS3({"inbox/bad.csv": b"x,y\n1,2\n"})
        handler.lambda_handler(event("inbox/bad.csv"), None, s3=s3)
        self.assertEqual(s3.puts, ["rejected/bad.error.txt"])
        self.assertIn("unexpected header", s3.objects["rejected/bad.error.txt"].decode())

    def test_not_utf8_is_rejected_not_a_crash(self):
        s3 = FakeS3({"inbox/b.csv": b"\xff\xfe\x00bad"})
        handler.lambda_handler(event("inbox/b.csv"), None, s3=s3)
        self.assertEqual(s3.puts, ["rejected/b.error.txt"])

    def test_the_key_is_url_decoded(self):
        s3 = FakeS3({"inbox/my file+1.csv": GOOD.encode()})
        handler.lambda_handler(event("inbox/my+file%2B1.csv"), None, s3=s3)
        self.assertEqual(s3.puts, ["processed/my file+1.json"])

    def test_other_keys_are_ignored(self):
        s3 = FakeS3({"processed/x.json": b"{}", "inbox/note.txt": b"hi", "other/a.csv": GOOD.encode()})
        out = handler.lambda_handler(event("processed/x.json", "inbox/note.txt", "other/a.csv"), None, s3=s3)
        self.assertEqual((s3.puts, out), ([], {"processed": 0}))

    def test_several_records(self):
        s3 = FakeS3({"inbox/a.csv": GOOD.encode(), "inbox/b.csv": GOOD.encode()})
        out = handler.lambda_handler(event("inbox/a.csv", "inbox/b.csv"), None, s3=s3)
        self.assertEqual((sorted(s3.puts), out), (["processed/a.json", "processed/b.json"], {"processed": 2}))

    def test_same_event_twice_is_harmless(self):
        s3 = FakeS3({"inbox/a.csv": GOOD.encode()})
        handler.lambda_handler(event("inbox/a.csv"), None, s3=s3)
        first = s3.objects["processed/a.json"]
        handler.lambda_handler(event("inbox/a.csv"), None, s3=s3)
        self.assertEqual(s3.objects["processed/a.json"], first)


if __name__ == "__main__":
    unittest.main()
