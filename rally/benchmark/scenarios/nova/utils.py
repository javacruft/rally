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

import time

from oslo.config import cfg

from rally.benchmark.scenarios import base
from rally.benchmark import utils as bench_utils


nova_benchmark_opts = []
option_names_and_defaults = [
    # action, prepoll delay, timeout, poll interval
    ('start', 0, 300, 1),
    ('stop', 0, 300, 2),
    ('boot', 1, 300, 1),
    ('delete', 2, 300, 2),
    ('reboot', 2, 300, 2),
    ('rescue', 2, 300, 2),
    ('unrescue', 2, 300, 2),
    ('suspend', 2, 300, 2),
    ('image_create', 0, 300, 2),
    ('image_delete', 0, 300, 2),
    ('resize', 2, 400, 5),
    ('resize_confirm', 0, 200, 2),
    ('resize_revert', 0, 200, 2),
]

for action, prepoll, timeout, poll in option_names_and_defaults:
    nova_benchmark_opts.extend([
        cfg.FloatOpt(
            "nova_server_%s_prepoll_delay" % action,
            default=float(prepoll),
            help='Time to sleep after %s before polling for status' % action
        ),
        cfg.FloatOpt(
            "nova_server_%s_timeout" % action,
            default=float(timeout),
            help='Server %s timeout' % action
        ),
        cfg.FloatOpt(
            "nova_server_%s_poll_interval" % action,
            default=float(poll),
            help='Server %s poll interval' % action
        )
    ])

CONF = cfg.CONF
benchmark_group = cfg.OptGroup(name='benchmark',
                               title='benchmark options')
CONF.register_group(benchmark_group)
CONF.register_opts(nova_benchmark_opts, group=benchmark_group)


class NovaScenario(base.Scenario):

    @base.atomic_action_timer('nova.list_servers')
    def _list_servers(self, detailed=True):
        """Returns user servers list."""

        return self.clients("nova").servers.list(detailed)

    @base.atomic_action_timer('nova.boot_server')
    def _boot_server(self, server_name, image_id, flavor_id,
                     auto_assign_nic=False, **kwargs):
        """Boots one server.

        Returns when the server is actually booted and is in the "Active"
        state.

        If multiple networks are present, the first network found that
        isn't associated with a floating IP pool is used.

        :param server_name: String used to name the server
        :param image_id: ID of the image to be used for server creation
        :param flavor_id: ID of the flavor to be used for server creation
        :param auto_assign_nic: Boolean for whether or not to assign NICs
        :param **kwargs: Other optional parameters to initialize the server

        :returns: Created server object
        """
        allow_ssh_secgroup = self.context().get("allow_ssh")
        if allow_ssh_secgroup:
            if 'security_groups' not in kwargs:
                kwargs['security_groups'] = [allow_ssh_secgroup]
            elif allow_ssh_secgroup not in kwargs['security_groups']:
                kwargs['security_groups'].append(allow_ssh_secgroup)

        nics = kwargs.get('nics', False)

        if auto_assign_nic and nics is False:
            nets = self.clients("nova").networks.list()
            fip_pool = [
                        pool.name
                        for pool in
                        self.clients("nova").floating_ip_pools.list()
                       ]
            for net in nets:
                if net.label not in fip_pool:
                    kwargs['nics'] = [{'net-id': net.id}]
                    break

        server = self.clients("nova").servers.create(server_name, image_id,
                                                     flavor_id, **kwargs)

        time.sleep(CONF.benchmark.nova_server_boot_prepoll_delay)
        server = bench_utils.wait_for(
            server,
            is_ready=bench_utils.resource_is("ACTIVE"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_boot_timeout,
            check_interval=CONF.benchmark.nova_server_boot_poll_interval
        )
        return server

    def _do_server_reboot(self, server, reboottype):
        server.reboot(reboot_type=reboottype)
        time.sleep(CONF.benchmark.nova_server_reboot_prepoll_delay)
        bench_utils.wait_for(
            server, is_ready=bench_utils.resource_is("ACTIVE"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_reboot_timeout,
            check_interval=CONF.benchmark.nova_server_reboot_poll_interval
        )

    @base.atomic_action_timer('nova.soft_reboot_server')
    def _soft_reboot_server(self, server):
        """Reboots the given server using soft reboot.

        A soft reboot will be issued on the given server upon which time
        this method will wait for the server to become active.

        :param server: The server to reboot.
        """
        self._do_server_reboot(server, "SOFT")

    @base.atomic_action_timer('nova.reboot_server')
    def _reboot_server(self, server):
        """Reboots the given server using hard reboot.

        A reboot will be issued on the given server upon which time
        this method will wait for the server to become active.

        :param server: The server to reboot.
        """
        self._do_server_reboot(server, "HARD")

    @base.atomic_action_timer('nova.start_server')
    def _start_server(self, server):
        """Starts the given server.

        A start will be issued for the given server upon which time
        this method will wait for it to become ACTIVE.

        :param server: The server to start and wait to become ACTIVE.
        """
        server.start()
        bench_utils.wait_for(
            server, is_ready=bench_utils.resource_is("ACTIVE"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_start_timeout,
            check_interval=CONF.benchmark.nova_server_start_poll_interval
        )

    @base.atomic_action_timer('nova.stop_server')
    def _stop_server(self, server):
        """Stop the given server.

        Issues a stop on the given server and waits for the server
        to become SHUTOFF.

        :param server: The server to stop.
        """
        server.stop()
        bench_utils.wait_for(
            server, is_ready=bench_utils.resource_is("SHUTOFF"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_stop_timeout,
            check_interval=CONF.benchmark.nova_server_stop_poll_interval
        )

    @base.atomic_action_timer('nova.rescue_server')
    def _rescue_server(self, server):
        """Rescue the given server.

        Returns when the server is actually rescue and is in the "Rescue"
        state.

        :param server: Server object
        """
        server.rescue()
        time.sleep(CONF.benchmark.nova_server_rescue_prepoll_delay)
        bench_utils.wait_for(
            server, is_ready=bench_utils.resource_is("RESCUE"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_rescue_timeout,
            check_interval=CONF.benchmark.nova_server_rescue_poll_interval
        )

    @base.atomic_action_timer('nova.unrescue_server')
    def _unrescue_server(self, server):
        """Unrescue the given server.

        Returns when the server is unrescue and waits to become ACTIVE

        :param server: Server object
        """
        server.unrescue()
        time.sleep(CONF.benchmark.nova_server_unrescue_prepoll_delay)
        bench_utils.wait_for(
            server, is_ready=bench_utils.resource_is("ACTIVE"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_unrescue_timeout,
            check_interval=CONF.benchmark.nova_server_unrescue_poll_interval
        )

    @base.atomic_action_timer('nova.suspend_server')
    def _suspend_server(self, server):
        """Suspends the given server.

        Returns when the server is actually suspended and is in the "Suspended"
        state.

        :param server: Server object
        """
        server.suspend()
        time.sleep(CONF.benchmark.nova_server_suspend_prepoll_delay)
        bench_utils.wait_for(
            server, is_ready=bench_utils.resource_is("SUSPENDED"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_suspend_timeout,
            check_interval=CONF.benchmark.nova_server_suspend_poll_interval
        )

    @base.atomic_action_timer('nova.delete_server')
    def _delete_server(self, server):
        """Deletes the given server.

        Returns when the server is actually deleted.

        :param server: Server object
        """
        server.delete()
        bench_utils.wait_for_delete(
            server,
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_delete_timeout,
            check_interval=CONF.benchmark.nova_server_delete_poll_interval
        )

    @base.atomic_action_timer('nova.delete_all_servers')
    def _delete_all_servers(self):
        """Deletes all servers in current tenant."""
        servers = self.clients("nova").servers.list()
        for server in servers:
            self._delete_server(server)

    @base.atomic_action_timer('nova.delete_image')
    def _delete_image(self, image):
        """Deletes the given image.

        Returns when the image is actually deleted.

        :param image: Image object
        """
        image.delete()
        check_interval = CONF.benchmark.nova_server_image_delete_poll_interval
        bench_utils.wait_for_delete(
            image,
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_image_delete_timeout,
            check_interval=check_interval
        )

    @base.atomic_action_timer('nova.create_image')
    def _create_image(self, server):
        """Creates an image of the given server

        Uses the server name to name the created image. Returns when the image
        is actually created and is in the "Active" state.

        :param server: Server object for which the image will be created

        :returns: Created image object
        """
        image_uuid = self.clients("nova").servers.create_image(server,
                                                               server.name)
        image = self.clients("nova").images.get(image_uuid)
        check_interval = CONF.benchmark.nova_server_image_create_poll_interval
        image = bench_utils.wait_for(
            image,
            is_ready=bench_utils.resource_is("ACTIVE"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_image_create_timeout,
            check_interval=check_interval
        )
        return image

    @base.atomic_action_timer('nova.boot_servers')
    def _boot_servers(self, name_prefix, image_id, flavor_id,
                      requests, instances_amount=1, **kwargs):
        """Boots multiple servers.

        Returns when all the servers are actually booted and are in the
        "Active" state.

        :param name_prefix: The prefix to use while naming the created servers.
                            The rest of the server names will be '_No.'
        :param image_id: ID of the image to be used for server creation
        :param flavor_id: ID of the flavor to be used for server creation
        :param requests: Number of booting requests to perform
        :param instances_amount: Number of instances to boot per each request

        :returns: List of created server objects
        """
        for i in range(requests):
            self.clients("nova").servers.create('%s_%d' % (name_prefix, i),
                                                image_id, flavor_id,
                                                min_count=instances_amount,
                                                max_count=instances_amount,
                                                **kwargs)
        # NOTE(msdubov): Nova python client returns only one server even when
        #                min_count > 1, so we have to rediscover all the
        #                created servers manyally.
        servers = filter(lambda server: server.name.startswith(name_prefix),
                         self.clients("nova").servers.list())
        time.sleep(CONF.benchmark.nova_server_boot_prepoll_delay)
        servers = [bench_utils.wait_for(
            server,
            is_ready=bench_utils.resource_is("ACTIVE"),
            update_resource=bench_utils.
            get_from_manager(),
            timeout=CONF.benchmark.nova_server_boot_timeout,
            check_interval=CONF.benchmark.nova_server_boot_poll_interval
        ) for server in servers]
        return servers

    @base.atomic_action_timer('nova.list_floating_ip_pools')
    def _list_floating_ip_pools(self):
        """Returns user floating ip pools list."""
        return self.clients("nova").floating_ip_pools.list()

    @base.atomic_action_timer('nova.list_floating_ips')
    def _list_floating_ips(self):
        """Returns user floating ips list."""
        return self.clients("nova").floating_ips.list()

    @base.atomic_action_timer('nova.create_floating_ip')
    def _create_floating_ip(self, pool):
        """Create (allocate) a floating ip from the given pool

        :param pool: Name of the floating ip pool or external network

        :returns: The created floating ip
        """
        return self.clients("nova").floating_ips.create(pool)

    @base.atomic_action_timer('nova.delete_floating_ip')
    def _delete_floating_ip(self, floating_ip):
        """Delete (deallocate) a  floating ip for a tenant

        :param floating_ip: The floating ip address to delete.
        """
        self.clients("nova").floating_ips.delete(floating_ip)
        bench_utils.wait_for_delete(
            floating_ip,
            update_resource=bench_utils.get_from_manager()
        )

    @base.atomic_action_timer('nova.associate_floating_ip')
    def _associate_floating_ip(self, server, address, fixed_address=None):
        """Add floating IP to an instance

        :param server: The :class:`Server` to add an IP to.
        :param address: The ip address or FloatingIP to add to the instance
        :param fixed_address: The fixedIP address the FloatingIP is to be
               associated with (optional)
        """
        server.add_floating_ip(address, fixed_address=fixed_address)
        bench_utils.wait_for(
            server,
            is_ready=self.check_ip_address(address),
            update_resource=bench_utils.get_from_manager()
        )
        # Update server data
        server.addresses = server.manager.get(server.id).addresses

    @base.atomic_action_timer('nova.dissociate_floating_ip')
    def _dissociate_floating_ip(self, server, address):
        """Remove floating IP from an instance

        :param server: The :class:`Server` to add an IP to.
        :param address: The ip address or FloatingIP to remove
        """
        server.remove_floating_ip(address)
        bench_utils.wait_for(
            server,
            is_ready=self.check_ip_address(address, must_exist=False),
            update_resource=bench_utils.get_from_manager()
        )
        # Update server data
        server.addresses = server.manager.get(server.id).addresses

    @staticmethod
    def check_ip_address(address, must_exist=True):
        ip_to_check = getattr(address, "ip", address)

        def _check_addr(resource):
            for network, addr_list in resource.addresses.items():
                for addr in addr_list:
                        if ip_to_check == addr["addr"]:
                            return must_exist
                return not must_exist
        return _check_addr

    @base.atomic_action_timer('nova.list_networks')
    def _list_networks(self):
        """Returns user networks list."""
        return self.clients("nova").networks.list()

    @base.atomic_action_timer('nova.resize')
    def _resize(self, server, flavor):
        server.resize(flavor)
        bench_utils.wait_for(
            server,
            is_ready=bench_utils.resource_is("VERIFY_RESIZE"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_resize_timeout,
            check_interval=CONF.benchmark.nova_server_resize_poll_interval
        )

    @base.atomic_action_timer('nova.resize_confirm')
    def _resize_confirm(self, server):
        server.confirm_resize()
        bench_utils.wait_for(
            server,
            is_ready=bench_utils.resource_is("ACTIVE"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_resize_confirm_timeout,
            check_interval=(
                CONF.benchmark.nova_server_resize_confirm_poll_interval)
        )

    @base.atomic_action_timer('nova.resize_revert')
    def _resize_revert(self, server):
        server.revert_resize()
        bench_utils.wait_for(
            server,
            is_ready=bench_utils.resource_is("ACTIVE"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_resize_revert_timeout,
            check_interval=(
                    CONF.benchmark.nova_server_resize_revert_poll_interval)
        )

    @base.atomic_action_timer('nova.attach_volume')
    def _attach_volume(self, server, volume):
        server_id = server.id
        volume_id = volume.id
        self.clients("nova").volumes.create_server_volume(server_id,
                                                          volume_id,
                                                          None)
        bench_utils.wait_for(
            volume,
            is_ready=bench_utils.resource_is("in-use"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_resize_revert_timeout,
            check_interval=(
                    CONF.benchmark.nova_server_resize_revert_poll_interval)
        )

    @base.atomic_action_timer('nova.detach_volume')
    def _detach_volume(self, server, volume):
        server_id = server.id
        volume_id = volume.id
        self.clients("nova").volumes.delete_server_volume(server_id,
                                                          volume_id)
        bench_utils.wait_for(
            volume,
            is_ready=bench_utils.resource_is("available"),
            update_resource=bench_utils.get_from_manager(),
            timeout=CONF.benchmark.nova_server_resize_revert_timeout,
            check_interval=(
                    CONF.benchmark.nova_server_resize_revert_poll_interval)
        )

    @base.atomic_action_timer('nova.create_network')
    def _create_network(self, network_create_args={}, start_cidr=None):
        """Create nova network by admin.

        The default policy for nova network-create is admin only.

        :param network_create_args: dict, POST /os-networks request options
        :returns: Nova network dict
        """
        cidr = bench_utils.generate_cidr(start_cidr)
        network_name = self._generate_random_name()
        network_create_args.setdefault("label", network_name)
        network_create_args.setdefault("cidr", cidr)
        return self.admin_clients("nova").networks.create(
            **network_create_args)
