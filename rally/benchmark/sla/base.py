# Copyright 2014: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


"""
SLA (Service-level agreement) is set of details for determining compliance
with contracted values such as maximum error rate or minimum response time.
"""

import abc

import jsonschema
import six

from rally.benchmark.processing import utils as putils
from rally.openstack.common.gettextutils import _
from rally import utils


class SLAResult(object):

    def __init__(self, success=True, msg=None):
        self.success = success
        self.msg = msg


@six.add_metaclass(abc.ABCMeta)
class SLA(object):
    """Factory for criteria classes."""

    @staticmethod
    def validate(config):
        properties = dict([(c.OPTION_NAME, c.CONFIG_SCHEMA)
                           for c in utils.itersubclasses(SLA)])
        schema = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        jsonschema.validate(config, schema)

    @staticmethod
    @abc.abstractmethod
    def check(criterion_value, result):
        """Check if task succeeded according to criterion.

        :param criterion_value: Criterion value specified in configuration
        :param result: result object
        :returns: True if success
        """

    @staticmethod
    def check_all(config, result):
        """Check all SLA criteria.

        :param config: sla related config for a task
        :param result: Result of a task
        :returns: A list of sla results
        """

        results = []
        opt_name_map = dict([(c.OPTION_NAME, c)
                             for c in utils.itersubclasses(SLA)])

        for name, criterion in config.get("sla", {}).iteritems():
            check_result = opt_name_map[name].check(criterion, result)
            results.append({'criterion': name,
                            'success': check_result.success,
                            'detail': check_result.msg})
        return results


class FailureRate(SLA):
    """Failure rate in percents."""
    OPTION_NAME = "max_failure_percent"
    CONFIG_SCHEMA = {"type": "number", "minimum": 0.0, "maximum": 100.0}

    @staticmethod
    def check(criterion_value, result):
        errors = len(filter(lambda x: x['error'], result))
        if criterion_value < errors * 100.0 / len(result):
            success = False
        else:
            success = True
        msg = (_("Maximum failure percent %s%% failures, actually %s%%") %
                (criterion_value * 100.0, errors * 100.0 / len(result)))
        return SLAResult(success, msg)


class IterationTime(SLA):
    """Maximum time for one iteration in seconds."""
    OPTION_NAME = "max_seconds_per_iteration"
    CONFIG_SCHEMA = {"type": "number", "minimum": 0.0,
                     "exclusiveMinimum": True}

    @staticmethod
    def check(criterion_value, result):
        duration = 0
        success = True
        for i in result:
            if i['duration'] >= duration:
                duration = i['duration']
            if i['duration'] > criterion_value:
                success = False
        msg = (_("Maximum seconds per iteration %ss, found with %ss") %
                (criterion_value, duration))
        return SLAResult(success, msg)


class MaxAverageDuration(SLA):
    """Maximum average duration for one iteration in seconds."""
    OPTION_NAME = "max_avg_duration"
    CONFIG_SCHEMA = {"type": "number", "minimum": 0.0,
                     "exclusiveMinimum": True}

    @staticmethod
    def check(criterion_value, result):
        durations = [r["duration"] for r in result if not r.get("error")]
        avg = putils.mean(durations)
        success = avg < criterion_value
        msg = (_("Maximum average duration per iteration %ss, found with %ss")
               % (criterion_value, avg))
        return SLAResult(success, msg)
