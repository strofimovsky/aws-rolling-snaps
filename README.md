# aws-rolling-snaps
aws-rolling-snaps is a Python/boto3 script to maintain ZFS-like rolling snapshots for EBS volumes

Features:
========
- No external dependencies (except boto3)
- Simple tag based selection, only snapshots volumes that carry [preconfigured] EC2 tag
- Run anywhere, even outside of AWS (running from cron)
- Or run it serverless, in AWS Lambda
- Configurable retention policy with reasonable defaults
- SNS notifications

Quick start (cron):
=========
1. First, install boto3 and set a default region:

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
2. Mark EBS volumes that you wish to snapshot with a tag ('MakeSnapshot': 'true' by default)

3. Configure cron to run the script

```sh

    $ chmod +x makesnap3.py
    $ crontab 
    30 1 * * 1-6  /path-to/makesnap3.py day
    30 2 * * 7    /path-to/makesnap3.py week
    30 3 1 * *    /path-to/makesnap3.py month
    # optional hourly run
    #15 */8 * * * /path-to/makesnap3.py hour
```

If you need hourly snaps, just uncomment the line

Credits:
=========
This script started as a boto3 rewrite of excellent makesnapshot tool (https://github.com/evannuil/aws-snapshot-tool)
