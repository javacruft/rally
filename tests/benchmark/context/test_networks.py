# Copyright 2014: Huawei
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


import mock

import rally.benchmark.context.networks as networks
import tests.test as test

NET_CONTEXT = "rally.benchmark.context.networks.Network"
SCENARIO = "rally.benchmark.scenarios"


class NetworkContextTestCase(test.TestCase):
    def setUp(self):
        super(NetworkContextTestCase, self).setUp()
        self.tenants_num = 2
        self.users_per_tenant = 5
        task = mock.MagicMock()
        self.users = [{'id': i, 'tenant_id': j, 'endpoint': 'endpoint'}
                      for j in range(self.tenants_num)
                      for i in range(self.users_per_tenant)]
        self.nets = [{'network_id': 'net_uuid_%s' % i,
                      'network': {'network': {'name': 'network',
                                              'deployment_uuid': 'uuid',
                                              'id': 'net_uuid_%s' % i}},
                      'endpoint': 'endpoint',
                      'tenant_id': i}
                     for i in range(self.tenants_num)]
        self.ctx_with_nets = {
            "users": self.users,
            "task": task,
            "admin": {"endpoint": "endpoint"},
            "nets": self.nets
        }
        self.ctx_without_nets = {
            "users": self.users,
            "task": task,
            "admin": {"endpoint": "endpoint"}
        }

    @mock.patch('rally.osclients.Clients')
    def test__nova_network_available(self, mock_clients):
        clients = mock_clients.return_value
        mock_nova = clients.nova.return_value

        class FakeService(object):
            def __init__(self):
                self.binary = "nova-network"

        mock_nova.services.list.return_value = [FakeService()]

        network_ctx = networks.Network(self.ctx_without_nets)

        self.assertEqual(True, network_ctx._nova_network_available())
        self.assertIn(
            mock.call().nova().services.list(),
            mock_clients.mock_calls
        )

    @mock.patch(NET_CONTEXT + "._get_neutron_network",
                return_value=mock.MagicMock())
    @mock.patch(NET_CONTEXT + "._nova_network_available", return_value=False)
    @mock.patch('rally.osclients.Clients')
    def test__ensure_network_with_neutron(self, mock_osclients,
                                          mock_nova_available,
                                          mock_get_network):
        clients = mock_osclients.return_value
        network_ctx = networks.Network(self.ctx_without_nets)
        network_ctx._ensure_network('endpoint', 'tenant_id')
        mock_get_network.assert_called_once_with(clients)

    @mock.patch(SCENARIO + ".nova.utils.NovaScenario._list_networks",
                return_value=[])
    @mock.patch(SCENARIO + ".nova.utils.NovaScenario._create_network")
    @mock.patch(NET_CONTEXT + "._nova_network_available",
                return_value=True)
    def test__ensure_network_with_nova(self, mock_nova_available,
                                       mock_create_network,
                                       mock_list_networks):
        network_ctx = networks.Network(self.ctx_without_nets)
        network_ctx._ensure_network('endpoint', 'tenant_id')
        mock_create_network.assert_called_once_with(project_id='tenant_id')

    @mock.patch(NET_CONTEXT + "._ensure_network")
    def test_network_context_setup(self, mock_ensure):
        def generate_nets(old_mock):
            new_mock = mock.MagicMock()

            def side_effect(endpoint, tenant_id, *args, **kwargs):
                net = {
                    'network': {
                        'name': 'network',
                        'deployment_uuid': 'uuid',
                        'id': 'net_uuid_%s' % tenant_id,
                    }
                }
                new_mock(endpoint, tenant_id, *args, **kwargs)
                old_mock.return_value = net
                return mock.DEFAULT

            old_mock.side_effect = side_effect
            return new_mock

        new_mock = generate_nets(mock_ensure)
        network_ctx = networks.Network(self.ctx_without_nets)
        network_ctx.setup()

        calls = [mock.call('endpoint', i) for i in range(self.tenants_num)]
        new_mock.assert_has_calls(calls)
        self.assertEqual(self.ctx_without_nets, self.ctx_with_nets)

    @mock.patch('rally.osclients.Clients')
    @mock.patch(NET_CONTEXT + "._nova_network_available", return_value=False)
    def test_network_context_cleanup_with_neutron(self,
                                                  mock_nova_available,
                                                  mock_osclients):
        clients = mock_osclients.return_value
        network_ctx = networks.Network(self.ctx_without_nets)
        network_ctx.context['nets'] = [{'network': {'id': 'uuid',
                                                    'router_id': 'router_id',
                                                    'subnet_id': 'subnet_id'},
                                        'endpoint': 'endpoint',
                                        'tenant_id': 'tenant_id'}]
        mock_neutron = clients.neutron.return_value

        network_ctx.cleanup()

        mock_neutron.remove_gateway_router.assert_called_with('router_id')
        mock_neutron.remove_interface_router.assert_called_with(
            'router_id',
            {'subnet_id': 'subnet_id'})
        mock_neutron.delete_router.assert_called_with('router_id')
        mock_neutron.delete_subnet.assert_called_with('subnet_id')
        mock_neutron.delete_network.assert_called_with('uuid')

    @mock.patch(NET_CONTEXT + "._nova_network_available", return_value=True)
    @mock.patch('rally.osclients.Clients')
    def test_network_context_cleanup_with_nova(self, mock_osclients,
                                               mock_nova_available):
        clients = mock_osclients.return_value
        network_ctx = networks.Network(self.ctx_without_nets)
        network_ctx.context['nets'] = self.nets
        mock_nova = clients.nova.return_value

        network_ctx.cleanup()

        calls = [mock.call({'network': {'name': 'network',
                                        'deployment_uuid': 'uuid',
                                        'id': 'net_uuid_%s' % i}})
                 for i in range(self.tenants_num)]
        mock_nova.networks.delete.assert_has_calls(calls)
