# Copyright 2014: Rackspace UK
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

from rally.benchmark.context import base
from rally.benchmark.scenarios.neutron import utils as neutron_utils
from rally.benchmark.scenarios.nova import utils as nova_utils
from rally.openstack.common.gettextutils import _
from rally.openstack.common import log as logging
from rally import osclients
from rally import utils


LOG = logging.getLogger(__name__)


class Network(base.Context):
    __ctx_name__ = "network"
    __ctx_order__ = 500
    __ctx_hidden__ = False

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": utils.JSON_SCHEMA,
        "properties": {
            "start_cidr": {
                "type": "string"
            },
            "networks_per_tenant": {
                "type": "integer",
                "minimum": 1
            }
        },
        "additionalProperties": False
    }

    def __init__(self, context):
        super(Network, self).__init__(context)
        self.config.setdefault("start_cidr", "10.1.0.0/16")
        self.config.setdefault("networks_per_tenant", 1)
        self.context["nets"] = []

    def _nova_network_available(self):
        nova = osclients.Clients(self.context["admin"]["endpoint"]).nova()
        for service in nova.services.list():
            if service.binary == "nova-network":
                return True
        return False

    def _get_neutron_network(self, clients, tenant_id, start_cidr):
        # create neutron network, subnet and router for tenant
        admin_clients = osclients.Clients(self.context["admin"]["endpoint"])
        neutron_scenario = neutron_utils.NeutronScenario(clients=admin_clients)

        network = neutron_scenario._create_network({"tenant_id": tenant_id})
        subnet = neutron_scenario._create_subnet(network, {}, start_cidr)
        router = neutron_scenario._create_router({"tenant_id": tenant_id},
                                                 True)
        neutron_scenario._add_interface_router(subnet['subnet'],
                                               router['router'])
        network['subnet_id'] = subnet['subnet']['id']
        network['router_id'] = router['router']['id']
        return network

    def _get_nova_network(self, clients, tenant_id, start_cidr):
        nova_scenario = nova_utils.NovaScenario(clients=clients)
        if not nova_scenario._list_networks():
            # create nova network for tenant
            admin_clients = osclients.Clients(
                self.context["admin"]["endpoint"])
            nova_scenario_admin = nova_utils.NovaScenario(
                clients=admin_clients)
            return nova_scenario_admin._create_network(
                project_id=tenant_id, start_cidr=start_cidr)

    def _ensure_network(self, endpoint, tenant_id, start_cidr):
        """Ensure that there is at least one valid network for tenant.

        Notice: for neutron, extenal network must be excluded; For nova, only
        admin has access to create network.

        :param endpoint: the Endpoint object
        :param tenant_id: tenant uuid

        :returns: None if tenant has private network, or new network created
                  for the tenant
        """
        clients = osclients.Clients(endpoint)

        if not self._nova_network_available():
            return self._get_neutron_network(clients, tenant_id, start_cidr)
        else:
            return self._get_nova_network(clients, tenant_id, start_cidr)

    @utils.log_task_wrapper(LOG.info, _("Enter context: `network`"))
    def setup(self):
        current_tenants = set()
        networks_per_tenant = int(self.config["networks_per_tenant"])

        for user in self.context.get('users', []):
            if user["tenant_id"] not in current_tenants:
                for i in xrange(networks_per_tenant):
                    current_tenants.add(user["tenant_id"])
                    network = self._ensure_network(user["endpoint"],
                                                   user["tenant_id"],
                                                   self.config["start_cidr"])
                    if network:
                        self.context["nets"].append(
                            {"network": network,
                             "endpoint": user["endpoint"],
                             "tenant_id": user["tenant_id"]})

    @utils.log_task_wrapper(LOG.info, _("Exit context: `network`"))
    def cleanup(self):
        clients = osclients.Clients(self.context["admin"]["endpoint"])

        use_nova = self._nova_network_available()

        for net in self.context["nets"]:
            try:
                if not use_nova:
                    neutron = clients.neutron()
                    neutron.remove_gateway_router(net['network']['router_id'])
                    neutron.remove_interface_router(
                        net['network']['router_id'],
                        {"subnet_id": net['network']['subnet_id']})
                    neutron.delete_router(net['network']['router_id'])
                    neutron.delete_subnet(net['network']['subnet_id'])
                    neutron.delete_network(net['network']['id'])
                else:
                    clients.nova.networks.delete(net["network"])
            except Exception as e:
                LOG.error("Failed to delete network for tenant "
                          "%(tenant_id)s\n"
                          " reason: %(exc)s"
                          % {"tenant_id": net["tenant_id"], "exc": e})
