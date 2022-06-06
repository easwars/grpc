# Copyright 2022 gRPC authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

from absl import flags
from absl.testing import absltest
from absl.testing import parameterized

from framework import xds_k8s_testcase
from framework.helpers import skips
from framework.infrastructure import k8s
from framework.infrastructure import traffic_director
from framework.test_app import client_app
from framework.test_app import server_app

logger = logging.getLogger(__name__)
flags.adopt_module_key_flags(xds_k8s_testcase)

# Type aliases
TrafficDirectorManager = traffic_director.TrafficDirectorManager
XdsTestServer = xds_k8s_testcase.XdsTestServer
XdsTestClient = xds_k8s_testcase.XdsTestClient
KubernetesServerRunner = server_app.KubernetesServerRunner
KubernetesClientRunner = client_app.KubernetesClientRunner

class BootstrapGeneratorClientTest(xds_k8s_testcase.XdsKubernetesTestCase):
    """Client-side bootstrap generator tests."""
    test_server: XdsTestServer

    #TODO: implement this to ensure that this is run
    # only on the latest version and one language
    @staticmethod
    def isSupported(config: skips.TestConfig) -> bool:
        return True


    @classmethod
    def setUpClass(cls):
        """Hook method for setting up class fixture before running tests in
        the class.
        """
        super().setUpClass()
        if cls.server_maintenance_port is None:
            cls.server_maintenance_port = \
                KubernetesServerRunner.DEFAULT_MAINTENANCE_PORT


    def setUp(self):
        """Hook method for setting up the test fixture before exercising it."""
        super().setUp()
        self.td.create_health_check()
        self.td.create_backend_service()
        self.td.create_url_map(self.server_xds_host, self.server_xds_port)
        self.td.create_target_proxy()
        self.td.create_forwarding_rule(self.server_xds_port)
        self.test_server = self.startTestServer()
        self.setupServerBackends()


    def initTrafficDirectorManager(self) -> TrafficDirectorManager:
        return TrafficDirectorManager(
            self.gcp_api_manager,
            project=self.project,
            resource_prefix=self.resource_prefix,
            resource_suffix=self.resource_suffix,
            network=self.network,
            compute_api_version=self.compute_api_version)


    def initKubernetesServerRunner(self) -> KubernetesServerRunner:
        return KubernetesServerRunner(
            k8s.KubernetesNamespace(self.k8s_api_manager,
                                    self.server_namespace),
            deployment_name=self.server_name,
            image_name=self.server_image,
            td_bootstrap_image=self.td_bootstrap_image,
            gcp_project=self.project,
            gcp_api_manager=self.gcp_api_manager,
            gcp_service_account=self.gcp_service_account,
            xds_server_uri=self.xds_server_uri,
            network=self.network,
            debug_use_port_forwarding=self.debug_use_port_forwarding,
            enable_workload_identity=self.enable_workload_identity)


    def initKubernetesClientRunner(self, td_bootstrap_image=None) -> KubernetesClientRunner:
        if td_bootstrap_image == None:
            td_bootstrap_image = self.td_bootstrap_image
        return KubernetesClientRunner(
            k8s.KubernetesNamespace(self.k8s_api_manager,
                                    self.client_namespace),
            deployment_name=self.client_name,
            image_name=self.client_image,
            td_bootstrap_image=td_bootstrap_image,
            gcp_project=self.project,
            gcp_api_manager=self.gcp_api_manager,
            gcp_service_account=self.gcp_service_account,
            xds_server_uri=self.xds_server_uri,
            network=self.network,
            debug_use_port_forwarding=self.debug_use_port_forwarding,
            enable_workload_identity=self.enable_workload_identity,
            stats_port=self.client_port,
            reuse_namespace=self.server_namespace == self.client_namespace)


    def startTestServer(self,
                         replica_count=1,
                         server_runner=None,
                         **kwargs) -> XdsTestServer:
        if server_runner is None:
            server_runner = self.server_runner
        test_server = server_runner.run(
            replica_count=replica_count,
            test_port=self.server_port,
            maintenance_port=self.server_maintenance_port,
            **kwargs)[0]
        test_server.set_xds_address(self.server_xds_host, self.server_xds_port)
        return test_server


    def startTestClient(self, test_server: XdsTestServer,
                        **kwargs) -> XdsTestClient:
        test_client = self.client_runner.run(server_target=test_server.xds_uri,
                                             **kwargs)
        test_client.wait_for_active_server_channel()
        return test_client


    @parameterized.named_parameters(
        ('Version v0.14.0', 'v0.14.0', 'gcr.io/grpc-testing/td-grpc-bootstrap:d6baaf7b0e0c63054ac4d9bedc09021ff261d599'))
    def test_baseline_across_bootstrap_versions(self, version, image):
        """Runs the baseline test for multiple versions of the bootstrap
        generator on the client. Server uses the version of the bootstrap
        generator as configured via the --td_bootstrap_image flag.
        """
        self.client_runner = self.initKubernetesClientRunner(td_bootstrap_image=image)
        test_client: XdsTestClient = self.startTestClient(test_server)
        self.assertXdsConfigExists(test_client)
        self.assertSuccessfulRpcs(test_client)
        self.client_runner.cleanup(force=self.force_cleanup)


if __name__ == '__main__':
    absltest.main(failfast=True)

