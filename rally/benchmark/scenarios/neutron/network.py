# Copyright 2014: Intel Inc.
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

from rally.benchmark.scenarios import base
from rally.benchmark.scenarios.neutron import utils
from rally.benchmark import validation
from rally import consts


class NeutronNetworks(utils.NeutronScenario):

    @validation.required_services(consts.Service.NEUTRON)
    @validation.required_openstack(users=True)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_list_networks(self, network_create_args=None):
        """Create a network and then listing all networks.

        This scenario is a very useful tool to measure
        the "neutron net-list" command performance.

        If you have only 1 user in your context, you will
        add 1 network on every iteration. So you will have more
        and more networks and will be able to measure the
        performance of the "neutron net-list" command depending on
        the number of networks owned by users.

        :param network_create_args: dict, POST /v2.0/networks request options
        """
        self._create_network(network_create_args or {})
        self._list_networks()

    @validation.required_services(consts.Service.NEUTRON)
    @validation.required_openstack(users=True)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_update_networks(self,
                                   network_update_args,
                                   network_create_args=None):
        """Create a network and then update network.

        This scenario is a very useful tool to measure
        the "neutron net-create and net-update" command performance.

        :param network_update_args: dict, PUT /v2.0/networks update request
        :param network_create_args: dict, POST /v2.0/networks request options
        """
        network = self._create_network(network_create_args or {})
        self._update_network(network, network_update_args)

    @validation.required_services(consts.Service.NEUTRON)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_delete_networks(self, network_create_args=None):
        """Create a network and then deleting it.

        This scenario is a very useful tool to measure
        the "neutron net-create" and "net-delete" command performance.

        :param network_create_agrs: dict, POST /v2.0/networks request options
        """
        network = self._create_network(network_create_args or {})
        self._delete_network(network['network'])

    @validation.number("subnets_per_network", minval=1, integer_only=True)
    @validation.required_services(consts.Service.NEUTRON)
    @validation.required_openstack(users=True)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_list_subnets(self,
                                network_create_args=None,
                                subnet_create_args=None,
                                subnet_cidr_start=None,
                                subnets_per_network=None):
        """Test creating and listing a given number of subnets.

        The scenario creates a network, a given number of subnets and then
        lists subnets.

        :param network_create_args: dict, POST /v2.0/networks request options
        :param subnet_create_args: dict, POST /v2.0/subnets request options
        :param subnet_cidr_start: str, start value for subnets CIDR
        :param subnets_per_network: int, number of subnets for one network
        """
        self._create_network_and_subnets(network_create_args or {},
                                         subnet_create_args or {},
                                         subnets_per_network,
                                         subnet_cidr_start)
        self._list_subnets()

    @validation.number("subnets_per_network", minval=1, integer_only=True)
    @validation.required_services(consts.Service.NEUTRON)
    @validation.required_openstack(users=True)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_update_subnets(self,
                                  subnet_update_args,
                                  network_create_args=None,
                                  subnet_create_args=None,
                                  subnet_cidr_start=None,
                                  subnets_per_network=None):
        """Create a subnet and then update subnet.

        The scenario creates a network, a given number of subnets
        and then updates the subnet. This scenario measure the
        "neutron subnet-update" command performance.

        :param subnet_update_args: dict, PUT /v2.0/subnets update options
        :param network_create_args: dict, POST /v2.0/networks request options
        :param subnet_create_args: dict, POST /v2.0/subnets request options
        :param subnet_cidr_start: str, start value for subnets CIDR
        :param subnets_per_network: int, number of subnets for one network
        """
        network, subnets = self._create_network_and_subnets(
                              network_create_args or {},
                              subnet_create_args or {},
                              subnets_per_network,
                              subnet_cidr_start)

        for subnet in subnets:
            self._update_subnet(subnet, subnet_update_args)

    @validation.required_parameters("subnets_per_network")
    @validation.required_services(consts.Service.NEUTRON)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_delete_subnets(self,
                                  network_create_args=None,
                                  subnet_create_args=None,
                                  subnet_cidr_start=None,
                                  subnets_per_network=None):
        """Test creating and deleting a given number of subnets.

        The scenario creates a network, a given number of subnets and then
        deletes subnets.

        :param network_create_args: dict, POST /v2.0/networks request options
        :param subnet_create_args: dict, POST /v2.0/subnets request options
        :param subnet_cidr_start: str, start value for subnets CIDR
        :param subnets_per_network: int, number of subnets for one network
        """
        network, subnets = self._create_network_and_subnets(
                              network_create_args or {},
                              subnet_create_args or {},
                              subnets_per_network,
                              subnet_cidr_start)

        for subnet in subnets:
            self._delete_subnet(subnet)

    @validation.number("subnets_per_network", minval=1, integer_only=True)
    @validation.required_services(consts.Service.NEUTRON)
    @validation.required_openstack(users=True)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_list_routers(self,
                                network_create_args=None,
                                subnet_create_args=None,
                                subnet_cidr_start=None,
                                subnets_per_network=None,
                                router_create_args=None):
        """Test creating and listing a given number of routers.

        Create a network, a given number of subnets and routers
        and then list all routers.

        :param network_create_args: dict, POST /v2.0/networks request options
        :param subnet_create_args: dict, POST /v2.0/subnets request options
        :param subnet_cidr_start: str, start value for subnets CIDR
        :param subnets_per_network: int, number of subnets for one network
        :param router_create_args: dict, POST /v2.0/routers request options
        """
        network, subnets = self._create_network_and_subnets(
                              network_create_args or {},
                              subnet_create_args or {},
                              subnets_per_network,
                              subnet_cidr_start)

        for subnet in subnets:
            router = self._create_router(router_create_args or {})
            self.clients("neutron").add_interface_router(
                router["router"]["id"],
                {"subnet_id": subnet["subnet"]["id"]})

        self._list_routers()

    @validation.number("subnets_per_network", minval=1, integer_only=True)
    @validation.required_parameters("subnets_per_network")
    @validation.required_services(consts.Service.NEUTRON)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_update_routers(self,
                                  router_update_args,
                                  network_create_args=None,
                                  subnet_create_args=None,
                                  subnet_cidr_start=None,
                                  subnets_per_network=None,
                                  router_create_args=None):
        """Test creating and updating a given number of routers.

        Create a network, a given number of subnets and routers
        and then updating all routers.

        :param router_update_args: dict, PUT /v2.0/routers update options
        :param network_create_args: dict, POST /v2.0/networks request options
        :param subnet_create_args: dict, POST /v2.0/subnets request options
        :param subnet_cidr_start: str, start value for subnets CIDR
        :param subnets_per_network: int, number of subnets for one network
        :param router_create_args: dict, POST /v2.0/routers request options
        """
        network, subnets = self._create_network_and_subnets(
                              network_create_args or {},
                              subnet_create_args or {},
                              subnets_per_network,
                              subnet_cidr_start)

        for subnet in subnets:
            router = self._create_router(router_create_args or {})
            self.clients("neutron").add_interface_router(
                router["router"]["id"],
                {"subnet_id": subnet["subnet"]["id"]})
            self._update_router(router, router_update_args)

    @validation.number("ports_per_network", minval=1, integer_only=True)
    @validation.required_services(consts.Service.NEUTRON)
    @validation.required_openstack(users=True)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_list_ports(self,
                              network_create_args=None,
                              port_create_args=None,
                              ports_per_network=None):
        """Test creating and listing a given number of ports.

        :param network_create_args: dict, POST /v2.0/networks request options
        :param port_create_args: dict, POST /v2.0/ports request options
        :param ports_per_network: int, number of ports for one network
        """
        network = self._create_network(network_create_args or {})
        for i in range(ports_per_network):
            self._create_port(network, port_create_args or {})

        self._list_ports()

    @validation.number("ports_per_network", minval=1, integer_only=True)
    @validation.required_services(consts.Service.NEUTRON)
    @validation.required_openstack(users=True)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_update_ports(self,
                                port_update_args,
                                network_create_args=None,
                                port_create_args=None,
                                ports_per_network=None):
        """Test creating and updating a given number of ports.

        This scenario is a very useful tool to measure
        the "neutron port-create" and
        "neutron port-update" command performance.

        :param port_update_args: dict, PUT /v2.0/ports update request options
        :param network_create_args: dict, POST /v2.0/networks request options
        :param port_create_args: dict, POST /v2.0/ports request options
        :param ports_per_network: int, number of ports for one network
        """
        network = self._create_network(network_create_args or {})
        for i in range(ports_per_network):
            port = self._create_port(network, port_create_args or {})
            self._update_port(port, port_update_args)

    @validation.required_parameters("ports_per_network")
    @validation.required_services(consts.Service.NEUTRON)
    @base.scenario(context={"cleanup": ["neutron"]})
    def create_and_delete_ports(self,
                                network_create_args=None,
                                port_create_args=None,
                                ports_per_network=None):
        """Create a port and then deleting it.

        This scenario is a very useful tool to measure
        the "neutron port-create" and
        "neutron port-delete" command performance.

        :param network_create_args: dict, POST /v2.0/networks request options
        :param port_create_args: dict, POST /v2.0/ports request options
        :param ports_per_network: int, number of ports for one network
        """
        network = self._create_network(network_create_args or {})
        for i in range(ports_per_network):
            port = self._create_port(network, port_create_args or {})
            self._delete_port(port)
