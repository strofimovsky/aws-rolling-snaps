#!/bin/sh

echo
echo 'First, create IAM policy with necessary permissons '
echo 'sample policy in [makesnapshot-policy.json]:'
echo

makesnap_policy_arn=`\
aws iam create-policy \
    --policy-name makesnap3-policy \
    --policy-document file://makesnapshot-policy.json \
    --query 'Policy.Arn' --output text \
`
echo Policy: $makesnap_policy_arn
[ -z $makesnap_policy_arn ] && read -p "press ^C to stop ..." null

echo
echo 'Create IAM role for the function to assume ([trust-policy.json]),'
echo 'attach our policy and basic Lambda execution policy to it'
echo

ebs_snap_role_arn=`\
aws iam create-role \
    --role-name ebs-snapshot \
    --assume-role-policy-document file://trust-policy.json \
    --query 'Role.Arn' --output text \
`
echo Role: $ebs_snap_role_arn
[ -z $ebs_snap_role_arn ] && read -p "press ^C to stop ..." null

aws iam attach-role-policy \
    --role-name ebs-snapshot \
    --policy-arn $makesnap_policy_arn

aws iam attach-role-policy \
    --role-name ebs-snapshot \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole    

echo
echo Create zip file with the script and config file,
echo

zip deployment.zip makesnap3.py config.json

echo
echo "... and upload it to Lambda to create function"
echo "(IAM policy application lags sometimes, we'll sleep for 15 seconds)"
echo 
sleep 15

function_arn=` \
aws lambda create-function \
    --function-name makesnap3 \
    --zip-file fileb://deployment.zip \
    --role "$ebs_snap_role_arn"  \
    --handler makesnap3.lambda_handler \
    --runtime python2.7 \
    --timeout 180 \
    --memory-size 128 \
    --query 'FunctionArn' --output text \
`
echo Function: $function_arn
[ -z $function_arn ] && read -p "press ^C to stop ..." null

echo
echo Now, create CloudWatch rules to schedule the function to run:
echo

create_rule () {
    echo - $1: "$2"
    rule_arn=`aws events put-rule \
        --name $1 \
        --schedule-expression "$2" \
        --query RuleArn --output text \
    `
    echo Rule: $rule_arn
    [ -z $rule_arn ] && read -p "press ^C to stop ..." null

    aws events put-targets \
        --rule $1 \
        --targets '{"Id" : "1", "Arn": "'$function_arn'", "Input": "{\"period\": \"day\"}" }' \
        --query FailedEntries --output text

    aws lambda add-permission \
        --function-name makesnap3 \
        --action 'lambda:InvokeFunction' \
        --principal events.amazonaws.com \
        --statement-id $3 \
        --source-arn $rule_arn \
        --query Statement.Effect --output text
}

create_rule makesnap-daily   "cron(30 1 ? * MON-SAT *)" 1
create_rule makesnap-weekly  "cron(30 2 ? * SUN *)" 2 
create_rule makesnap-monthly "cron(30 3 1 * ? *)" 3

# Uncomment next line to create optional hourly run
#create_rule makesnap-hourly  "cron(15 */8 * * ? *)" 4

echo
echo "Profit!"
echo
