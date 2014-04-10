# Copyright 2012 OpenStack Foundation
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

import testtools
import time

from tempest.common.utils import data_utils
from tempest.test import attr
from tempest.api.volume import base


class NetAppSSCTest(base.BaseVolumeV1AdminTest):
    _interface = "json"

    def _delete_volume(self, volume_id):
        # Delete a volume and wait for deletion to complete
        resp, _ = self.volumes_client.delete_volume(volume_id)
        self.assertEqual(202, resp.status)
        self.volumes_client.wait_for_resource_deletion(volume_id)

    def _delete_volume_type(self, volume_type_id):
        # Delete a volume type
        resp, _ = self.client.delete_volume_type(volume_type_id)
        self.assertEqual(202, resp.status)

    def _ssc_test(self, name, **kwargs):
        """ Base ssc test method

        @param name: String, name of the volume-type
        @param expected_vol: String, name of the NetApp volume you expect the
            cinder volume to be created on
        @param **kwargs: Dict, the extra specs for the volume type,
            in ssc's case, the NetApp attributes
        """

        volume = {}
        # Generate a random name for the volume
        vol_name = data_utils.rand_name("volume-")
        extra_specs = kwargs
        resp, body = self.client.create_volume_type(name,
                                                    extra_specs=extra_specs)
        # Verify good response
        self.assertEqual(200, resp.status)
        self.assertIn('id', body)
        # Add automatic cleanup for volume type we just created
        self.addCleanup(self._delete_volume_type, body['id'])
        # Create a 1G volume of above volume type
        resp, volume = self.volumes_client.create_volume(
            size=1, display_name=vol_name,
            volume_type=name)
        # Verify good response
        self.assertEqual(200, resp.status)
        self.assertIn('id', volume)
        # Add automatic cleanup for volume we just created
        self.addCleanup(self._delete_volume, volume['id'])
        # Wait for the volume creation to complete successfully
        self.volumes_client.wait_for_volume_status(volume['id'],
                                                   'available')

    def _wait_for_volume_status_change(self, volume_id, status):
        """Waits for a Volume to change a given status."""

        resp, body = self.volumes_client.get_volume(volume_id)
        volume_name = body['display_name']
        volume_status = body['status']
        while volume_status == status:
            time.sleep(self.build_interval)
            resp, body = self.volumes_client.get_volume(volume_id)
            volume_status = body['status']

    @attr(type=['negative', 'gate'])
    def _ssc_test_negative(self, name, **kwargs):
        """ Base ssc test method some negative test

        @param name: String, name of the volume-type
        @param **kwargs: Dict, the extra specs for the volume type,
            in ssc's case, the NetApp attributes
        """
        volume = {}
        # Generate a random name for the volume
        vol_name = data_utils.rand_name("volume-")
        extra_specs = kwargs
        # Create a volume type
        resp, body = self.client.create_volume_type(name,
                                                    extra_specs=extra_specs)
        # Verify good response
        self.assertEqual(200, resp.status)
        self.assertIn('id', body)
        # Add automatic cleanup for volume type we just created
        self.addCleanup(self._delete_volume_type, body['id'])
        # Create a 1G volume of above volume type
        resp, volume = self.volumes_client.create_volume(size=1,
                                                         display_name=vol_name,
                                                         volume_type=name)
        # Verify good response
        self.assertEqual(200, resp.status)
        self.assertIn('id', volume)
        resp, body = self.volumes_client.get_volume(volume['id'])
        volume_status = body['status']
        # add automatic cleanup for volume we just created
        self.addCleanup(self._delete_volume, volume['id'])
        # wait for volume status change from creating
        self._wait_for_volume_status_change(volume['id'],
                                            'creating')
        resp, body = self.volumes_client.get_volume(volume['id'])
        volume_status = body['status']
        self.assertEqual('error', volume_status)


    def test_ssc_netapp_mirrored(self):
        ''' Test netapp_mirrored '''
        self._ssc_test('vol-type-mirrored',
                       **{'netapp_mirrored': 'true'})

    def test_ssc_netapp_mirrored_false(self):
        ''' Test netapp_mirrored_false '''
        self._ssc_test_negative('vol-type-mirrored_false',
                                **{'netapp_mirrored': 'false'})

    def test_ssc_netapp_unmirrored(self):
        ''' Test netapp_unmirrored '''
        self._ssc_test('vol-type-unmirrored',
                       **{'netapp_unmirrored': 'true'})

    def test_ssc_netapp_unmirrored_false(self):
        ''' Test netapp_unmirrored_false '''
        self._ssc_test_negative('vol-type-unmirrored_false',
                                **{'netapp_mirrored': 'false'})

    def test_ssc_netapp_dedup(self):
        ''' Test netapp_dedup '''
        self._ssc_test('vol-type-dedup',
                       **{'netapp_dedup': 'true'})

    def test_ssc_netapp_dedup_false(self):
        ''' Test netapp_dedup_false '''
        self._ssc_test_negative('vol-type-dedup_false',
                                **{'netapp_dedup': 'false'})

    def test_ssc_netapp_nodedup(self):
        ''' Test netapp_nodedup '''
        self._ssc_test('vol-type-nodedup',
                       **{'netapp_nodedup': 'true'})

    def test_ssc_netapp_nodedup_false(self):
        ''' Test netapp_nodedup_false '''
        self._ssc_test_negative('vol-type-nodedup_false',
                                **{'netapp_nodedup': 'false'})

    def test_ssc_netapp_compressed(self):
        ''' Test netapp_compressed '''
        self._ssc_test('vol-type-compressed',
                       **{'netapp_compression': 'true'})

    def test_ssc_netapp_compressed_false(self):
        ''' Test netapp_compressed_false '''
        self._ssc_test_negative('vol-type-compressed_false',
                                **{'netapp_compression': 'false'})

    def test_ssc_netapp_nocompressed(self):
        ''' Test netapp_nocompressed '''
        self._ssc_test('vol-type-nocompressed',
                       **{'netapp_nocompression': 'true'})

    def test_ssc_netapp_nocompressed_false(self):
        ''' Test netapp_nocompressed_false '''
        self._ssc_test_negative('vol-type-nocompressed_false',
                                **{'netapp_nocompression': 'false'})

    def test_ssc_netapp_thin_provisioned(self):
        ''' Test netapp_thin_provisioned '''
        self._ssc_test('vol-type-thin',
                       **{'netapp_thin_provisioned': 'true'})

    def test_ssc_netapp_thin_provisioned_false(self):
        ''' Test netapp_thin_provisioned_false '''
        self._ssc_test_negative('vol-type-thin',
                                **{'netapp_thin_provisioned': 'false'})

    def test_ssc_netapp_thick_provisioned(self):
        ''' Test netapp_thick_provisioned '''
        self._ssc_test('vol-type-thick',
                       **{'netapp_thick_provisioned': 'true'})

    def test_ssc_netapp_thick_provisioned_false(self):
        ''' Test netapp_thick_provisioned_false '''
        self._ssc_test_negative('vol-type-thick',
                                **{'netapp_thick_provisioned': 'false'})

    def test_ssc_netapp_raid_dp(self):
        ''' Test netapp_raidDP '''
        self._ssc_test('vol-type-raid_dp',
                       **{'netapp:raid_type': 'raid_dp'})

    @testtools.skip("No aggr present which support raid4")
    def test_ssc_netapp_raid4(self):
        ''' Test netapp_raid4 '''
        self._ssc_test('vol-type-raid4',
                       **{'netapp:raid_type': 'raid4'})

    def test_ssc_netapp_sas_disk(self):
        ''' Test netapp_sas_disk '''
        self._ssc_test('vol-type-sas',
                       **{'netapp:disk_type': 'SATA'})

    def test_ssc_netapp_sata_disk(self):
        ''' Test netapp_sata_disk '''
        self._ssc_test('vol-type-sata',
                       **{'netapp:disk_type': 'SATA'})

    @testtools.skip("Ssd disk isnot available at back end")
    def test_ssc_netapp_ssd_disk(self):
        ''' Test netapp_ssd_disk '''
        self._ssc_test('vol-type-ssd',
                       **{'netapp:disk_type': 'SSD'})

    def test_ssc_netapp_qos_policy(self):
        ''' Test netapp_qos_policy '''
        self._ssc_test('vol-type-qos',
                       **{'netapp:qos_policy_group': 'p2'})

    def test_ssc_netapp_mixed_unqualified(self):
        ''' Test test_ssc_netapp_mixed_unqualified '''
        self._ssc_test('vol-type-mixunqual',
                       **{'netapp_compression': 'true',
                          'netapp_dedup': 'true'})

    def test_ssc_netapp_mixed_qualified(self):
        ''' Test test_ssc_netapp_mixed_qualified '''
        self._ssc_test('vol-type-mixqual',
                       **{'netapp:disk_type': 'SATA',
                          'netapp:raid_type': 'raid_dp'})

    def test_ssc_netapp_mixed(self):
        ''' Test test_ssc_netapp_mixed '''
        self._ssc_test('vol-type-mixed',
                       **{'netapp_thin_provisioned': 'true',
                          'netapp_compression': 'true', 'netapp_dedup': 'true',
                          'netapp:raid_type': 'raid_dp'})
