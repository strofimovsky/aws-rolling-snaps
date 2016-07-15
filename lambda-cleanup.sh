#!/bin/sh
if [[ ! -x /usr/local/bin/jq ]]; then
  echo "this script requires jq"
else
  ebspolicyarn="$(aws iam list-policies|jq -r '.Policies[]|select((.PolicyName == "makesnap3-policy"))|.Arn')"
  functionarn="$(aws events list-targets-by-rule --rule makesnap-daily|jq -r '.Targets[].Arn')"

  aws iam detach-role-policy --role-name ebs-snapshot --policy-arn "$ebspolicyarn"
  aws iam detach-role-policy --role-name ebs-snapshot --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

  aws iam delete-role --role-name ebs-snapshot

  aws iam delete-policy --policy-arn "$ebspolicyarn"

  aws lambda delete-function --function-name makesnap3

  for period in hourly daily weekly monthly; do
    aws events remove-targets --rule "makesnap-${period}" --ids 1
    aws events delete-rule --name "makesnap-${period}"
  done
fi
