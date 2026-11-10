#!/usr/bin/env bash
# Empties and deletes the bucket, the function, its log group and the role. Run with: ./teardown.sh
set -u
aws sts get-caller-identity >/dev/null 2>&1 || { echo "No working AWS credentials." >&2; exit 1; }
ACCT=$(aws sts get-caller-identity --query Account --output text)
B=clippy-inbox-$ACCT
if aws s3api head-bucket --bucket $B 2>/dev/null; then
  aws s3api put-bucket-notification-configuration --bucket $B --notification-configuration '{}' 2>/dev/null
  # delete every version and delete marker, then the bucket
  python3 - "$B" <<'PY'
import json, subprocess, sys
b = sys.argv[1]
def run(*a):
    return subprocess.run(("aws",) + a, capture_output=True, text=True)
while True:
    r = run("s3api", "list-object-versions", "--bucket", b, "--max-items", "500", "--output", "json")
    d = json.loads(r.stdout or "{}") if r.returncode == 0 else {}
    objs = [{"Key": x["Key"], "VersionId": x["VersionId"]} for x in (d.get("Versions") or []) + (d.get("DeleteMarkers") or [])]
    if not objs:
        break
    run("s3api", "delete-objects", "--bucket", b, "--delete", json.dumps({"Objects": objs, "Quiet": True}))
PY
  aws s3api delete-bucket --bucket $B && echo "deleted bucket $B"
fi
aws lambda delete-function --function-name clippy-inbox >/dev/null 2>&1 && echo "deleted function clippy-inbox"
aws logs delete-log-group --log-group-name /aws/lambda/clippy-inbox 2>/dev/null && echo "deleted log group"
R=clippy-inbox-role
for p in $(aws iam list-role-policies --role-name $R --query 'PolicyNames' --output text 2>/dev/null); do aws iam delete-role-policy --role-name $R --policy-name $p; done
for p in $(aws iam list-attached-role-policies --role-name $R --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null); do aws iam detach-role-policy --role-name $R --policy-arn $p; done
aws iam delete-role --role-name $R 2>/dev/null && echo "deleted role $R"
echo "Now run ./verify-teardown.sh"
