#!/usr/bin/env python

# Author: Sergey Trofimovsky <troff@paranoia.ru>
# (c) 2016
#
# License: BSD

"""Maintain rolling snapshots for EBS volumes
Usage::
    $ makesnap3.py {hour|day|week|month|year}
"""

import argparse
import boto3
import sys
import re
import os
import time
import json
import logging
from datetime import datetime
from collections import defaultdict

config_defaults = defaultdict(lambda: None, {
    'aws_profile_name': 'default',
    'ec2_region_name': '',
    'tag_name': 'MakeSnapshot',
    'tag_value': 'true',
    'tag_type': 'volume',
    'running_only': False,
    'keep_hour': 4,
    'keep_day': 3,
    'keep_week': 4,
    'keep_month': 3,
    'keep_year': 10,
    'skip_create': False,
    'skip_delete': False,
    'log_file': '',
    'arn': '',
})

now_format = {
    'hour': '%R',
    'day': '%a',
    'week': '%U',
    'month': '%b',
    'year': '%Y'
}

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
            log.info("Notify SNS: %s", arn)
            sns = boto3.client('sns')
            sns.publish(TopicArn=arn, Subject=subj, Message="\n".join(stat))
        except Exception as err:
            log.error("Can't notify ARN:" + str(sys.exc_info()[0]))
            log.error(err)
            exitcode = 4
            pass

    return exitcode


def read_config(filename, defaults):
    new = defaults.copy()

    log.debug("Reading config file")
    try:
        with open(filename) as cf:
            cfg_data = json.load(cf)
        new.update(cfg_data)
    except IOError:
        log.debug("No config, using defaults")
    except ValueError:
        log.warning("Error parsing config, using defaults")

    log.debug("Reading config overrides from the environment")
    env_data = {}
    for var in os.environ:
        split = var.lower().split("makesnap_")
        if len(split) > 1:
            param = split[1]
        else:
            continue

        if new[param] is not None:
            # casting environment string to the type 
            # of a parameter with the same name
            env_data[param] = type(defaults[param])(os.environ[var])
        else:
            log.warning("Unknown parameter (env): " + param)
    new.update(env_data)

    # some config sanity checks
    if not new['tag_type'] in ['volume', 'instance']:
        log.warning("Unknown tag type: %s, resorting to default" %
                    new['tag_type'])
        new['tag_type'] = defaults['tag_type']

    return new


def get_vols(ec2_resource, tag_name, tag_value, tag_type='volume', running_only=False):
    log.debug("looking for tags of type %s " % tag_type)
    if tag_type == 'volume':
        vols = ec2_resource.volumes.filter(
            Filters=[{'Name': 'tag:' + tag_name, 'Values': [tag_value]}]).all()
        return vols
    elif tag_type == 'instance':
        instance_filters = [{'Name': 'tag:' + tag_name, 'Values': [tag_value]}]
        if running_only:
            instance_filters.append(
                {'Name': 'instance-state-name', 'Values': ['running']})
        instances = ec2_resource.instances.filter(
            Filters=instance_filters).all()

        instance_ids = []
        for instance in instances:
            instance_ids.append(instance.id)
        vols = ec2_resource.volumes.filter(Filters=[
            {'Name': 'attachment.instance-id', 'Values': instance_ids}
        ]).all()
        return vols
    else:
        # reserved for new tag types
        pass


def log_setup(logfile=None):
    """Setup console logging by default
    if logfile is defined, log there too
    """

    if logfile:
        fh = logging.FileHandler(logfile)
        fhf = logging.Formatter(
            '%(asctime)s %(name)s: %(levelname)s %(message)s')
        fh.setFormatter(fhf)
        log.addHandler(fh)
    else:
        log.addHandler(logging.StreamHandler())
        log.setLevel(logging.INFO)


def calc_rotate(config, snaplist, period):
    """ Calculate a list of snapshots to delete in this <period> run
    """
    candidates = []
    for snap in snaplist:
        if re.findall("^(hour|day|week|month|year)_snapshot", snap.description) == [period]:
            candidates.append(snap)
            log.debug("     Added to candidate list: %s '%s'",
                      snap.id, snap.description)
        else:
            log.debug("     Skipped, not adding: %s '%s'",
                      snap.id, snap.description)
    candidates.sort(key=lambda x: x.start_time)

    deletelist = []
    for i in range(len(candidates) - config['keep_' + period]):
        deletelist.append(candidates[i])

    return deletelist


def main(period, config_file='config.json'):
    log_setup()
    config = read_config(config_file, config_defaults)
    if config['log_file']:
        log_setup(config['log_file'])

    # Set profile name only if it's explicitly defined if config file
    # otherwise it messes with the boto's order of credentials search
    # (environment is not checked)
    if config.get('aws_profile_name'):
        boto3.setup_default_session(profile_name=(
            config['aws_profile_name'] or 'default'))

    stats = {
        'total_vols': 0,
        'total_errors': 0,
        'snap_deletes': 0,
        'snap_creates': 0,
        'snap_errors': 0,
    }

    date_suffix = datetime.today().strftime(now_format[period])
    log.info("Started taking %ss snapshots at %s", period,
             datetime.today().strftime('%d-%m-%Y %H:%M:%S'))

    # 'None' resorts to boto default region
    ec2_region = config['ec2_region_name'] or None
    try:
        ec2 = boto3.resource('ec2', region_name=ec2_region)
        vols = get_vols(ec2_resource=ec2, tag_name=config['tag_name'], tag_value=config[
                        'tag_value'], tag_type=config['tag_type'], running_only=config['running_only'])
        for vol in vols:
            log.info("Processing volume %s:", vol.id)
            stats['total_vols'] += 1
            description = '%(period)s_snapshot %(vol_id)s_%(period)s_%(date_suffix)s by snapshot script at %(date)s' % {
                'period': period,
                'vol_id': vol.id,
                'date_suffix': date_suffix,
                'date': datetime.today().strftime('%d-%m-%Y %H:%M:%S')
            }

            if not config['skip_create']:
                try:
                    log.info(
                        ">> Creating snapshot for volume %s: '%s'", vol.id, description)
                    current_snap = vol.create_snapshot(Description=description)
                    if vol.tags is not None:
                        current_snap.create_tags(Tags=vol.tags)
                    stats['snap_creates'] += 1
                except Exception as err:
                    stats['snap_errors'] += 1
                    log.error("Unexpected error making snapshot:" +
                              str(sys.exc_info()[0]))
                    log.error(err)
                    pass

            if not config['skip_delete']:
                for del_snap in calc_rotate(config, vol.snapshots.all(), period):
                    log.info(">> Deleting snapshot %s", del_snap.description)
                    try:
                        del_snap.delete()
                        stats['snap_deletes'] += 1
                    except Exception as err:
                        stats['snap_errors'] += 1
                        log.error(
                            "Unexpected error deleting snapshot:" + str(sys.exc_info()[0]))
                        log.error(err)
                        pass

            time.sleep(3)

    except Exception as err:
        stats['total_errors'] += 1
        log.critical("Can't access volume list:" + str(sys.exc_info()[0]))
        log.critical(err)

    return dump_stats(stats, config['arn'])


def lambda_handler(event, context):
    period = event.get('period', None)
    if now_format.get(period, None):
        return main(period)
    else:
        print("Expecting {'period': '{hour|day|week|month|year}'} in input event")
        return 1

if __name__ == '__main__':
    # period = sys.argv[1]

    # Command Line Args
    arg_parser = argparse.ArgumentParser(description='')
    arg_parser.add_argument(
        '-c', '--config', help='configuration file to load', type=str, default='config.json')
    arg_parser.add_argument('period', choices=['hour', 'day', 'week', 'month', 'year'])
    args = arg_parser.parse_args()

    config_file = str(args.config)
    period = str(args.period)

    sys.exit(main(period, config_file=config_file))
