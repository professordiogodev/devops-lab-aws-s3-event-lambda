#!/usr/bin/env bash
# Proves the lab left nothing in AWS. Run with: ./verify-teardown.sh
set -u
ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || { echo "No working AWS credentials." >&2; exit 1; }
H=$(bash "$(dirname "$0")/.lab/handle.sh") || exit 1
echo "Checking account $ACCOUNT (handle $H), region $(aws configure get region)"
pass=0; failn=0
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS  $d"; pass=$((pass+1)); else echo "FAIL  $d"; failn=$((failn+1)); fi; }
check "no bucket clippy-inbox-$H-$ACCOUNT" bash -c "! aws s3api head-bucket --bucket clippy-inbox-$H-$ACCOUNT"
check "no Lambda function clippy-inbox-$H" bash -c "! aws lambda get-function --function-name clippy-inbox-$H"
check "no log group /aws/lambda/clippy-inbox-$H" bash -c "[ -z \"\$(aws logs describe-log-groups --log-group-name-prefix /aws/lambda/clippy-inbox-$H --query \"logGroups[].logGroupName\" --output text)\" ]"
check "no IAM role clippy-inbox-role-$H" bash -c "! aws iam get-role --role-name clippy-inbox-role-$H"
echo
if [ "$failn" -eq 0 ]; then echo "TEARDOWN VERIFIED ($pass/$pass) in account $ACCOUNT"; else echo "NOT CLEAN: $failn leftover(s). Remove them and run this again."; fi
exit "$failn"
