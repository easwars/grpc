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

from framework import xds_k8s_testcase
from framework.helpers import skips

logger = logging.getLogger(__name__)
flags.adopt_module_key_flags(xds_k8s_testcase)

# Test specific flags.
# TODO: performs some validation of `td_bootstrap_images` cannot be empty.
# https://abseil.io/docs/python/guides/flags#flags-validators
TD_BOOTSTRAP_IMAGES = flags.DEFINE_list(
    'td_bootstrap_images',
    default=None,
    help='List of bootstrap generator images to test against')

# Type aliases
_XdsTestServer = xds_k8s_testcase.XdsTestServer
_XdsTestClient = xds_k8s_testcase.XdsTestClient


class BootstrapGeneratorTest(xds_k8s_testcase.RegularXdsKubernetesTestCase):
    #TODO: implement this to ensure that this is run
    # only on the latest version and one language
    @staticmethod
    def isSupported(config: skips.TestConfig) -> bool:
        return True

    def test_baseline_across_bootstrap_versions_for_client(self):

        with self.subTest('0_create_health_check'):
            self.td.create_health_check()

        with self.subTest('1_create_backend_service'):
            self.td.create_backend_service()

        with self.subTest('2_create_url_map'):
            self.td.create_url_map(self.server_xds_host, self.server_xds_port)

        with self.subTest('3_create_target_proxy'):
            self.td.create_target_proxy()

        with self.subTest('4_create_forwarding_rule'):
            self.td.create_forwarding_rule(self.server_xds_port)

        with self.subTest('5_start_test_server'):
            test_server: _XdsTestServer = self.startTestServers()[0]

        with self.subTest('6_add_server_backends_to_backend_service'):
            self.setupServerBackends()

        bootstrap_image: str
        for bootstrap_image in TD_BOOTSTRAP_IMAGES.value:
            # Reset td_bootstrap_image on parent. This is required when starting
            # the client runner below. This is originally read in the parent
            # class' setupClass() method.
            self.td_bootstrap_image = bootstrap_image

            # Reinitialize the test client runner. This will end up using the
            # bootstrap generator image set in the previous line, while creating
            # the client deployment spec.
            self.client_runner = self.initKubernetesClientRunner()

            with self.subTest('7_start_test_client_%s' % bootstrap_image):
                test_client: _XdsTestClient = self.startTestClient(test_server)

            with self.subTest('8_test_client_xds_config_exists_%s' %
                              bootstrap_image):
                self.assertXdsConfigExists(test_client)

            with self.subTest(
                    '9_test_server_received_rpcs_from_test_client_%s' %
                    bootstrap_image):
                self.assertSuccessfulRpcs(test_client)
                self.client_runner.cleanup(force=self.force_cleanup)


if __name__ == '__main__':
    absltest.main(failfast=True)
