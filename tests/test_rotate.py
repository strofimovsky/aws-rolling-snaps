#!/usr/bin/env python

from collections import namedtuple
from nose.tools import assert_equal, assert_greater, assert_true, assert_raises
from makesnap3 import read_config, config_defaults, calc_rotate

# default values only
config = read_config('', config_defaults)

Snap = namedtuple('Snap', ['description', 'id', 'start_time'])
snaplist = [
    Snap("hour_snapshot vol-12345678_hour_18:05 by snapshot script at 13-10-2016 18:05:52", "snap-12345678a", "2016-10-13T18:05:03.000Z"),
    Snap("hour_snapshot vol-12345678_hour_17:05 by snapshot script at 13-10-2016 17:05:32", "snap-12345678b", "2016-10-13T17:05:03.000Z"),
    Snap("hour_snapshot vol-12345678_hour_16:02 by snapshot script at 13-10-2016 16:02:13", "snap-12345678c", "2016-10-13T16:05:03.000Z"),
    Snap("hour_snapshot vol-12345678_hour_15:01 by snapshot script at 13-10-2016 15:01:24", "snap-12345678d", "2016-10-13T15:01:25.000Z"),
    Snap("hour_snapshot vol-12345678_hour_14:01 by snapshot script at 13-10-2016 14:01:24", "snap-12345678e", "2016-10-13T14:01:25.000Z"),
    Snap("hour_snapshot vol-12345678_hour_13:01 by snapshot script at 13-10-2016 13:01:24", "snap-12345678f", "2016-10-13T13:01:25.000Z"),
]

def test_calc_rotate():
    period = 'hour' # any period would do

    # > keep# + 1
    config['keep_hour'] = 3
    assert_equal([i.id for i in calc_rotate(config, snaplist, period)], ['snap-12345678f', 'snap-12345678e', 'snap-12345678d'])

    # keep# + 1
    config['keep_hour'] = 5
    assert_equal([i.id for i in calc_rotate(config, snaplist, period)], ['snap-12345678f'])

    # keep#
    config['keep_hour'] = 6
    assert_equal([i.id for i in calc_rotate(config, snaplist, period)], [])

    # keep# - 1
    config['keep_hour'] = 7
    assert_equal([i.id for i in calc_rotate(config, snaplist, period)], [])

    # empty list
    config['keep_hour'] = 4
    assert_equal([i.id for i in calc_rotate(config, [], period)], [])

    # small lists ( < keep#)
    config['keep_hour'] = 4
    assert_equal([i.id for i in calc_rotate(config, [snaplist[i] for i in range(3)], period)], [])
    assert_equal([i.id for i in calc_rotate(config, [snaplist[i] for i in range(1)], period)], [])


if __name__ == '__main__':
    import nose
    nose.runmodule() 
