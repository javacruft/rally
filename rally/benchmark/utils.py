# Copyright 2013: Mirantis Inc.
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

import itertools
import logging
import multiprocessing
import time
import traceback

import netaddr
from novaclient.v1_1 import servers

from rally import exceptions


LOG = logging.getLogger(__name__)


def chunks(data, step):
    """Split collection into chunks.

    :param data: collection to split, only list or tuple are allowed
    :param step: int chunk size
    :returns: list of collection chunks

    >>> chunks([1,2,3,4,5,6,7,8,9,10], 3)
    [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]
    """
    return [data[x:x + step] for x in xrange(0, len(data), step)]


def resource_is(status):
    return lambda resource: resource.status.upper() == status.upper()


def get_status(resource):
    # workaround for heat resources - using stack_status instead of status
    if ((hasattr(resource, "stack_status") and
         isinstance(resource.stack_status, basestring))):
        return resource.stack_status.upper()
    return resource.status.upper()


def get_from_manager(error_statuses=None):
    error_statuses = error_statuses or ["ERROR"]
    error_statuses = map(lambda str: str.upper(), error_statuses)

    def _get_from_manager(resource):
        # catch client side errors
        try:
            res = resource.manager.get(resource.id)
        except Exception as e:
            if getattr(e, 'code', 400) == 404:
                raise exceptions.GetResourceNotFound(resource=resource)
            raise exceptions.GetResourceFailure(resource=resource, err=e)

        # catch abnormal status, such as "no valid host" for servers
        status = get_status(res)

        if status in ("DELETED", "DELETE_COMPLETE"):
            raise exceptions.GetResourceNotFound(resource=res)
        if status in error_statuses:
            if isinstance(res.manager, servers.ServerManager):
                msg = res.fault['message']
            else:
                msg = ''
            raise exceptions.GetResourceErrorStatus(resource=res,
                                                    status=status, fault=msg)

        return res

    return _get_from_manager


def manager_list_size(sizes):
    def _list(mgr):
        return len(mgr.list()) in sizes
    return _list


def wait_for(resource, is_ready, update_resource=None, timeout=60,
             check_interval=1):
    """Waits for the given resource to come into the desired state.

    Uses the readiness check function passed as a parameter and (optionally)
    a function that updates the resource being waited for.

    :param is_ready: A predicate that should take the resource object and
                     return True iff it is ready to be returned
    :param update_resource: Function that should take the resource object
                          and return an 'updated' resource. If set to
                          None, no result updating is performed
    :param timeout: Timeout in seconds after which a TimeoutException will be
                    raised
    :param check_interval: Interval in seconds between the two consecutive
                           readiness checks

    :returns: The "ready" resource object
    """

    start = time.time()
    while True:
        # NOTE(boden): mitigate 1st iteration waits by updating immediately
        if update_resource:
            resource = update_resource(resource)
        if is_ready(resource):
            break
        time.sleep(check_interval)
        if time.time() - start > timeout:
            raise exceptions.TimeoutException()
    return resource


def wait_for_delete(resource, update_resource=None, timeout=60,
                    check_interval=1):
    """Wait for the full deletion of resource.

    :param update_resource: Function that should take the resource object
                            and return an 'updated' resource, or raise
                            exception rally.exceptions.GetResourceNotFound
                            that means that resource is deleted.

    :param timeout: Timeout in seconds after which a TimeoutException will be
                    raised
    :param check_interval: Interval in seconds between the two consecutive
                           readiness checks
    """
    start = time.time()
    while True:
        try:
            resource = update_resource(resource)
        except exceptions.GetResourceNotFound:
            break
        time.sleep(check_interval)
        if time.time() - start > timeout:
            raise exceptions.TimeoutException()


def format_exc(exc):
    return [str(type(exc)), str(exc), traceback.format_exc()]


def infinite_run_args_generator(args_func):
    for i in itertools.count():
        yield args_func(i)


def run_concurrent_helper(args):
    cls, method, fn_args = args
    return getattr(cls, method)(fn_args)


def run_concurrent(concurrent, cls, fn, fn_args):
    """Run given function using pool of threads.

    :param concurrent: number of threads in the pool
    :param cls: class to be called in the pool
    :param fn: class method to be called in the pool
    :param fn_args: list of arguments for function fn() in the pool
    :returns: iterator from Pool.imap()
    """

    pool = multiprocessing.Pool(concurrent)
    iterator = pool.imap(run_concurrent_helper,
                         [(cls, fn, args) for args in fn_args])
    pool.close()
    pool.join()

    return iterator


def check_service_status(client, service_name):
    """Check if given openstack service is enabled and state is up."""
    for service in client.services.list():
        if service_name in str(service):
            if service.status == 'enabled' and service.state == 'up':
                return True
    return False


_network_cidr = None
_subnet_cidrs = {}


def generate_cidr(network=None, start_cidr="1.1.0.0/30"):
    """Generate next CIDR for network or subnet, without IP overlapping.

    :param network: None for generating cidr for network,
                    network UUID for generating for subnet.
    :returns: str, next available CIDR.
    """
    with multiprocessing.Lock():
        if network:
            if network in _subnet_cidrs:
                crnt_cidr = _subnet_cidrs[network]
                cidr = str(netaddr.IPNetwork(crnt_cidr).next())
            else:
                cidr = str(netaddr.IPNetwork(start_cidr))
            _subnet_cidrs[network] = cidr
        else:
            global _network_cidr
            if _network_cidr is None:
                _network_cidr = start_cidr

            cidr = str(netaddr.IPNetwork(_network_cidr).next())
            _network_cidr = cidr
    return cidr
