"""Clippy bulk import: the Lambda function behind the S3 inbox.

S3 calls lambda_handler(event, context) when an object is created in the bucket. The event looks like:

  {"Records": [{"s3": {"bucket": {"name": "clippy-inbox-123456789012"},
                       "object": {"key": "inbox/my+file%2B1.csv", "size": 123}}}]}

Careful: the key in the event is URL-encoded ("+" is a space, "%2B" is a plus sign).

What the function must do for every record whose key is  inbox/<name>.csv :

  1. Read the object (UTF-8 text).
  2. process() it (below).
  3. Write the result back to the SAME bucket:
       good file  ->  processed/<name>.json   (the JSON report from process())
       bad file   ->  rejected/<name>.error.txt   (one line: the reason)
     <name> is the file name without the inbox/ folder and without .csv.
  Records for any other key (not inbox/, not .csv) are ignored without error.
"""
import csv
import io
import json
import re
import urllib.parse

import boto3

CODE = re.compile(r"^[a-z0-9-]{3,20}$")
HEADER = ["short_code", "url"]


def process(text):
    """Validate the CSV text. Return a dict.

    A rejected file returns   {"ok": False, "error": "<reason>"}   with exactly these reasons:
        "empty file"           nothing but whitespace
        "unexpected header"    the first line is not exactly short_code,url
        "no data rows"         a correct header and nothing else (blank lines do not count)
    An accepted file returns  {"ok": True, "source_rows": N, "valid": V, "invalid": [{"line": L, "reason": R}, ...]}
        N = number of non-blank data rows, V = how many are valid
        a row is valid when it has exactly 2 columns, short_code matches CODE and url starts with http:// or https://
        L is the line number in the file (the header is line 1), R is one of
        "wrong number of columns", "bad short_code", "bad url"  (check in that order)
    """
    # TODO 1: write it. Use the csv module (a url may contain commas inside quotes), not str.split.
    raise NotImplementedError("write me")


def lambda_handler(event, context, s3=None):
    s3 = s3 or boto3.client("s3")
    done = 0
    # TODO 2: for every record: decode the key, ignore it unless it is inbox/<name>.csv,
    #         read the object, call process(), write processed/<name>.json or rejected/<name>.error.txt.
    #         Print one log line per file (what you read, what you wrote).
    return {"processed": done}
