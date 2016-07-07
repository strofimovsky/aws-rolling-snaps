# aws-rolling-snaps
aws-rolling-snaps is a Python/boto3 script to maintain ZFS-like rolling snapshots for EBS volumes

Features
========
- No external dependencies (except boto3)
- Simple tag based selection, only snapshots volumes that carry [preconfigured] EC2 tag
- Run anywhere, even outside of AWS (running from cron)
- Or run it serverless, in AWS Lambda
- Configurable retention policy with reasonable defaults
- SNS notifications

Quick start (cron)
=========
- First, install boto3

```sh

    $ pip install boto3
```
Next, set up credentials (in e.g. ``~/.aws/credentials``):

```ini

    [default]
    aws_access_key_id = YOUR_KEY
    aws_secret_access_key = YOUR_SECRET
```
Then, set up a default region (in e.g. ``~/.aws/config``):

```ini

    [default]
    region=us-east-1
```

- Mark EBS volumes that you wish to snapshot with a tag ('MakeSnapshot': 'true' by default)

- Configure cron to run the script

```sh

    $ chmod +x makesnap3.py
    $ crontab -e
    30 1 * * 1-6  /path-to/makesnap3.py day
    30 2 * * 7    /path-to/makesnap3.py week
    30 3 1 * *    /path-to/makesnap3.py month
    # optional hourly run
    #15 */8 * * * /path-to/makesnap3.py hour
```


Quick start (AWS Lambda)
=========
- First, create IAM policy with necessary permissons (sample policy in [makesnapshot-policy.json](makesnapshot-policy.json))

```sh
export makesnap_policy_arn=`\
aws iam create-policy \
    --policy-name makesnap3-policy \
    --policy-document file://makesnapshot-policy.json \
    --query 'Policy.Arn' --output text \
` && echo $makesnap_policy_arn
```

- Create IAM role for the function to assume ([trust-policy.json](trust-policy.json)), attach our policy and basic Lambda execution policy to it

```sh
export ebs_snap_role_arn=`\
aws iam create-role \
    --role-name ebs-snapshot \
    --assume-role-policy-document file://trust-policy.json \
    --query 'Role.Arn' --output text \
` && echo $ebs_snap_role_arn

aws iam attach-role-policy \
    --role-name ebs-snapshot \
    --policy-arn $makesnap_policy_arn

aws iam attach-role-policy \
    --role-name ebs-snapshot \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole    
```

- Create zip file with the script and config file and upload it to Lambda to create function

```sh
zip deployment.zip makesnap3.py config.json
export function_arn=` \
aws lambda create-function \
    --function-name makesnap3 \
    --zip-file fileb://deployment.zip \
    --role $ebs_snap_role_arn  \
    --handler makesnap3.lambda_handler \
    --runtime python2.7 \
    --timeout 15 \
    --memory-size 128 \
    --query 'FunctionArn' --output text \
` && echo $function_arn
```

- Now, create rules to schedule the function to run:

```sh
aws events put-rule \
    --name makesnap-daily \
    --schedule-expression "cron(30 1 * * ? 1-6)"
aws events put-targets \
    --rule makesnap-daily \
    --targets '{"Id" : "1", "Arn": "'$function_arn'", "Input": "{\"period\": \"day\"}" }'

aws events put-rule \
    --name makesnap-weekly \
    --schedule-expression "cron(30 2 * * ? 7)"
aws events put-targets \
    --rule makesnap-weekly \
    --targets '{"Id" : "1", "Arn": "'$function_arn'", "Input": "{\"period\": \"week\"}" }'

aws events put-rule \
    --name makesnap-monthly \
    --schedule-expression "cron(30 3 1 * ? *)"
aws events put-targets \
    --rule makesnap-monthly \
    --targets '{"Id" : "1", "Arn": "'$function_arn'", "Input": "{\"period\": \"month\"}" }'
```
(even the optional hourly run):
```sh
aws events put-rule \
    --name makesnap-hourly \
    --schedule-expression "cron(15 */8 * * ? *)"
aws events put-targets \
    --rule makesnap-hourly \
    --targets '{"Id" : "1", "Arn": "'$function_arn'", "Input": "{\"period\": \"hour\"}" }'
```

- Profit

Credits
=========
This script started as a boto3 rewrite of the excellent makesnapshot tool (https://github.com/evannuil/aws-snapshot-tool)
