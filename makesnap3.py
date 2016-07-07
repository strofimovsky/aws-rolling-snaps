#!/usr/bin/env python

# Author: Sergey Trofimovsky <troff@paranoia.ru>
# (c) 2016
#
# License: BSD

"""Maintain rolling snapshots for EBS volumes
Usage::
    $ makesnap3.py {hour|day|week|month}
"""

import boto3
import sys
import re
import time
import json
import logging
from datetime import datetime

config_defaults = {
    'tag_name': 'MakeSnapshot', 'tag_value': 'true',
    'keep_hour': 4, 'keep_day': 3, 'keep_week': 4, 'keep_month': 3
}

now_format = {'hour': '%R', 'day': '%a', 'week': '%U', 'month': '%b'}

log = logging.getLogger('makesnap3')


def dump_stats(stats, arn):
    """ Check and log run statistics, notify SNS if ARN is defined

    Args:
        stats: statistics dict

    Returns:
        int: 0 for success, non-zero otherwise
    """
    total = stats['total_errors'] + stats['snap_errors']
    if total > 0:
        exitcode = 3
        logstats = log.error
        subj = 'Error making snapshots'
    else:
        exitcode = 0
        logstats = log.info
        subj = 'Completed making snapshots'

    stat = ['']
    stat.append("Finished making snapshots at {} for {} volume(s), {} errors".format(
        datetime.today().strftime('%d-%m-%Y %H:%M:%S'), stats['total_vols'], total))
    stat.append("Created: {}, deleted: {}, errors: {}".format(
        stats['snap_creates'], stats['snap_deletes'], stats['snap_errors']))
    for s in stat:
        logstats(s)

    if arn:
        try:
            sns = boto3.client('sns')
            sns.publish(TopicArn=arn, Subject=subj, Message="\n".join(stat))
        except Exception as err:
            log.error("Can't notify ARN:" + str(sys.exc_info()[0]))
            log.error(err)
            raise

    return exitcode


def read_config(filename, defaults):
    new = defaults.copy()
    try:
        with open(filename) as cf:
            cfg_data = json.load(cf)
        new.update(cfg_data)
    except IOError:
        log.info("No config, using defaults")
        pass
    except ValueError:
        log.warning("Error parsing config, using defaults")
        pass
    return new


def log_setup(logfile):
    """Setup console logging by default
    if logfile is defined, log there too
    """
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)
    if logfile:
        fh = logging.FileHandler(logfile)
        fhf = logging.Formatter(
            '%(asctime)s %(name)s: %(levelname)s %(message)s')
        fh.setFormatter(fhf)
        log.addHandler(fh)


def main(period):
    config = read_config('config.json', config_defaults)
    log_setup(config.get('log_file', None))

    stats = {
        'total_vols': 0, 'total_errors': 0,
        'snap_deletes': 0, 'snap_creates': 0, 'snap_errors': 0,
    }

    date_suffix = datetime.today().strftime(now_format[period])
    log.info("Started taking %ss snapshots at %s", period,
             datetime.today().strftime('%d-%m-%Y %H:%M:%S'))
    try:
        ec2 = boto3.resource('ec2')
        for vol in ec2.volumes.filter(Filters=[{
            'Name': 'tag:' + config['tag_name'], 'Values': [config['tag_value']]
        }]).all():
            log.info("Processing volume %s:", vol.id)
            stats['total_vols'] += 1
            description = '%(period)s_snapshot %(vol_id)s_%(period)s_%(date_suffix)s by snapshot script at %(date)s' % {
                'period': period,
                'vol_id': vol.id,
                'date_suffix': date_suffix,
                'date': datetime.today().strftime('%d-%m-%Y %H:%M:%S')
            }
            try:
                log.info(
                    "     Creating snapshot for volume %s: '%s'",
                    vol.id,
                    description)
                current_snap = vol.create_snapshot(Description=description)
                current_snap.create_tags(Tags=vol.tags)
                stats['snap_creates'] += 1
            except Exception as err:
                stats['snap_errors'] += 1
                log.error("Unexpected error making snapshot:" +
                          str(sys.exc_info()[0]))
                log.error(err)
                pass

            deletelist = []
            for snap in vol.snapshots.all():
                if re.findall("^(hour|day|week|month)_snapshot",
                              snap.description) == [period]:
                    deletelist.append(snap)
                    log.debug(
                        "     Added to deletelist: %s '%s'",
                        snap.id,
                        snap.description)
                else:
                    log.debug(
                        "     Skipped, not adding: %s '%s'",
                        snap.id,
                        snap.description)

            deletelist.sort(key=lambda x: x.start_time)
            for i in range(len(deletelist) - config['keep_' + period]):
                log.info(
                    '     Deleting snapshot %s',
                    deletelist[i].description)
                try:
                    deletelist[i].delete()
                    stats['snap_deletes'] += 1
                except Exception as err:
                    stats['snap_errors'] += 1
                    log.error("Unexpected error deleting snapshot:" +
                              str(sys.exc_info()[0]))
                    log.error(err)
                    pass

            time.sleep(3)

    except Exception as err:
        stats['total_errors'] += 1
        log.critical("Can't access volume list:" + str(sys.exc_info()[0]))
        log.critical(err)

    return dump_stats(stats, config.get('arn', None))


def lambda_handler(event, context):
    period = event.get('period', None)
    if now_format.get(period, None):
        return main(period)
    else:
        print("Expecting {'period': '{hour|day|week|month}'} in input event")
        return 1

if __name__ == '__main__':
    if len(sys.argv) > 1 and now_format.get(sys.argv[1], None):
        period = sys.argv[1]
        sys.exit(main(period))
    else:
        print('Usage: {} {{hour|day|week|month}}'.format(sys.argv[0]))
        sys.exit(1)
