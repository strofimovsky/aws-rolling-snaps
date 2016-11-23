#!/bin/sh

ebspolicyarn=`aws iam list-policies --query "Policies[?PolicyName=='makesnap3-policy'].Arn" --output text`
echo Policy: $ebspolicyarn
[ -z $ebspolicyarn ] && read -p "press ^C to stop ..." null

functionarn=`aws events list-targets-by-rule --rule makesnap-daily --query "Targets[0].Arn" --output=text`
echo Function: $functionarn
[ -z $functionarn ] && read -p "press ^C to stop ..." null

echo
echo Deleting roles, policies, function..
echo

aws iam detach-role-policy --role-name ebs-snapshot --policy-arn "$ebspolicyarn"
aws iam detach-role-policy --role-name ebs-snapshot --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

aws iam delete-role --role-name ebs-snapshot

aws iam delete-policy --policy-arn "$ebspolicyarn"

aws lambda delete-function --function-name makesnap3

echo
echo Deleting rules
echo

for period in hourly daily weekly monthly yearly; do
    echo "makesnap-${period}"
    aws events list-targets-by-rule --rule makesnap-${period}
    if [ $? != 0 ]; then
        echo No makesnap-${period} rule
    else
        aws events remove-targets --rule "makesnap-${period}" --ids 1 --query FailedEntryCount --output text
        aws events delete-rule --name "makesnap-${period}" --query FailedEntries --output text
    fi
done

echo Done
