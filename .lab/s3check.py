#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
passed = failed = 0
H = sys.argv[1]
LAB, FN, ROLE = "aws-s3-event-lambda", "clippy-inbox-" + H, "clippy-inbox-role-" + H


def check(desc, ok, hint=""):
    global passed, failed
    if ok:
        passed += 1; print("PASS  " + desc)
    else:
        failed += 1; print("FAIL  " + desc + (("   -> " + hint) if hint else ""))


def aws(*a, raw=False):
    try:
        out = subprocess.check_output(("aws",) + a + (() if raw else ("--output", "json")), stderr=subprocess.DEVNULL, timeout=90)
        return out.decode() if raw else json.loads(out or "null")
    except Exception:
        return None


def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def finish():
    print()
    print(("ALL CHECKS PASSED (%d/%d)" % (passed, passed)) if failed == 0 else ("%d check(s) failed, %d passed" % (failed, passed)))
    sys.exit(1 if failed else 0)


acct = aws("sts", "get-caller-identity")["Account"]
B = "clippy-inbox-" + H + "-" + acct
print("Account %s" % acct)
print("== Your code ==")
src = open("handler.py").read()
check("handler.py is no longer the starter", "NotImplementedError" not in src)
check("the local tests pass (python3 -m unittest discover -s tests)", sh("python3 -m unittest discover -s tests")[0] == 0)
check("no AWS keys in the repository", sh("git grep -lE 'AKIA[0-9A-Z]{16}' -- . ':!.lab' ")[1].strip() == "")

print("== The bucket ==")
head = aws("s3api", "head-bucket", "--bucket", B)
check("the bucket %s exists" % B, head is not None)
if head is None:
    finish()
pab = (aws("s3api", "get-public-access-block", "--bucket", B) or {}).get("PublicAccessBlockConfiguration", {})
check("all four 'block public access' settings are on", len(pab) == 4 and all(pab.values()))
tg = {t["Key"]: t["Value"] for t in (aws("s3api", "get-bucket-tagging", "--bucket", B) or {}).get("TagSet", [])}
check("the bucket is tagged lab=%s and student=%s" % (LAB, H), tg.get("lab") == LAB and tg.get("student") == H)

print("== The function ==")
fn = (aws("lambda", "get-function", "--function-name", FN) or {})
conf = fn.get("Configuration", {})
check("function %s exists on Python 3.11 or newer" % FN, bool(conf) and conf.get("Runtime", "").startswith("python3.") and int(conf["Runtime"].split(".")[1]) >= 11)
check("handler is handler.lambda_handler", conf.get("Handler") == "handler.lambda_handler")
check("timeout 30 s or less and memory 256 MB or less", bool(conf) and conf.get("Timeout", 99) <= 30 and conf.get("MemorySize", 9999) <= 256)
check("the function is tagged lab=%s and student=%s" % (LAB, H), fn.get("Tags", {}).get("lab") == LAB and fn.get("Tags", {}).get("student") == H)
lgs = (aws("logs", "describe-log-groups", "--log-group-name-prefix", "/aws/lambda/" + FN) or {}).get("logGroups", [])
check("the log group keeps logs for a set number of days", bool(lgs) and "retentionInDays" in lgs[0], "create /aws/lambda/%s and set a retention" % FN)

print("== The role: least privilege ==")
role = (aws("iam", "get-role", "--role-name", ROLE) or {}).get("Role")
check("role %s exists and only Lambda can assume it" % ROLE, bool(role) and "lambda.amazonaws.com" in json.dumps(role["AssumeRolePolicyDocument"]) and conf.get("Role", "").endswith("/" + ROLE))
if role:
    att = [p["PolicyArn"].split("/")[-1] for p in (aws("iam", "list-attached-role-policies", "--role-name", ROLE) or {}).get("AttachedPolicies", [])]
    check("the only managed policy is AWSLambdaBasicExecutionRole", att == ["AWSLambdaBasicExecutionRole"], str(att))
    arn = role["Arn"]

    def can(action, resource):
        r = aws("iam", "simulate-principal-policy", "--policy-source-arn", arn, "--action-names", action, "--resource-arns", resource)
        return bool(r) and r["EvaluationResults"][0]["EvalDecision"] == "allowed"
    ba = "arn:aws:s3:::" + B
    check("it can read objects in inbox/", can("s3:GetObject", ba + "/inbox/x.csv"))
    check("it can write reports to processed/ and error notes to rejected/", can("s3:PutObject", ba + "/processed/x.json") and can("s3:PutObject", ba + "/rejected/x.error.txt"))
    check("it can NOT write to inbox/ (this is what stops an infinite loop)", not can("s3:PutObject", ba + "/inbox/x.csv"))
    check("it can NOT read processed/ or delete or list anything", not can("s3:GetObject", ba + "/processed/x.json") and not can("s3:DeleteObject", ba + "/inbox/x.csv") and not can("s3:ListBucket", ba))
    check("it can NOT touch another bucket", not can("s3:GetObject", "arn:aws:s3:::some-other-bucket-" + acct + "/inbox/x.csv"))

print("== The trigger ==")
nc = aws("s3api", "get-bucket-notification-configuration", "--bucket", B) or {}
cfgs = nc.get("LambdaFunctionConfigurations", [])
check("exactly one Lambda notification, for ObjectCreated events, on this function", len(cfgs) == 1 and any(e.startswith("s3:ObjectCreated") for e in cfgs[0].get("Events", [])) and cfgs[0].get("LambdaFunctionArn", "").endswith(":function:" + FN))
rules = {r["Name"].lower(): r["Value"] for r in (cfgs[0].get("Filter", {}).get("Key", {}).get("FilterRules", []) if cfgs else [])}
check("the notification is filtered: prefix inbox/ and suffix .csv", rules.get("prefix") == "inbox/" and rules.get("suffix") == ".csv", str(rules))
pol = aws("lambda", "get-policy", "--function-name", FN)
st = json.loads(pol["Policy"])["Statement"] if pol else []
okp = any(s.get("Principal", {}).get("Service") == "s3.amazonaws.com" and s.get("Condition", {}).get("ArnLike", {}).get("AWS:SourceArn") == "arn:aws:s3:::" + B and s.get("Condition", {}).get("StringEquals", {}).get("AWS:SourceAccount") == acct for s in st)
check("only this bucket, in this account, may invoke the function (SourceArn and SourceAccount)", okp)

print("== Live: upload real files ==")
t0 = int(time.time() * 1000)
tag = str(int(time.time()))
files = {
    "inbox/ver-%s-good.csv" % tag: "short_code,url\nlaunch,https://ironhack.com\nBad Code,https://x.io\nnews,ftp://x.io\n",
    "inbox/ver-%s-bad.csv" % tag: "name,link\nlaunch,https://ironhack.com\n",
    "inbox/ver-%s my file+1.csv" % tag: "short_code,url\nabc,https://a.io\n",
    "inbox/ver-%s-note.txt" % tag: "not a csv\n",
}
tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
for k, v in files.items():
    open(tmp.name, "w").write(v)
    aws("s3api", "put-object", "--bucket", B, "--key", k, "--body", tmp.name)
os.unlink(tmp.name)


def get(key):
    rc, out = sh("aws s3 cp 's3://%s/%s' - 2>/dev/null" % (B, key))
    return out if rc == 0 else None


def wait(key, secs=90):
    end = time.time() + secs
    while time.time() < end:
        v = get(key)
        if v is not None:
            return v
        time.sleep(4)
    return None


rep = wait("processed/ver-%s-good.json" % tag)
try:
    j = json.loads(rep) if rep else {}
except Exception:
    j = {}
check("good.csv produced processed/...-good.json with 3 rows, 1 valid, 2 invalid lines (3 and 4)", j.get("source_rows") == 3 and j.get("valid") == 1 and [i.get("line") for i in j.get("invalid", [])] == [3, 4], (rep or "no report after 90 s")[:100])
err = wait("rejected/ver-%s-bad.error.txt" % tag)
check("bad.csv produced rejected/...-bad.error.txt saying 'unexpected header'", err is not None and "unexpected header" in err, "no error note after 90 s" if err is None else err[:60])
sp = wait("processed/ver-%s my file+1.json" % tag)
check("a file name with a space and a plus sign works (the key was decoded)", sp is not None and '"valid": 1' in sp)
time.sleep(25)
check("the .txt file in inbox/ was ignored (no report, no error note)", get("processed/ver-%s-note.json" % tag) is None and get("rejected/ver-%s-note.error.txt" % tag) is None)
starts = 0
r = aws("logs", "filter-log-events", "--log-group-name", "/aws/lambda/" + FN, "--filter-pattern", '"START RequestId"', "--start-time", str(t0))
starts = len((r or {}).get("events", []))
check("the function ran exactly 3 times for 3 CSV uploads (no loop on its own output, nothing for the .txt)", starts == 3, "%d invocations" % starts)
for k in list(files) + ["processed/ver-%s-good.json" % tag, "rejected/ver-%s-bad.error.txt" % tag, "processed/ver-%s my file+1.json" % tag]:
    aws("s3api", "delete-object", "--bucket", B, "--key", k)
finish()
