# Copyright 2014 NetApp, Inc.
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
WARNING: THIS IS A DESTRUCTIVE TEST - ALL EXISTING FLEXVOLS ON THE VSERVER
WILL BE DELETED.
"""

import ConfigParser
import MySQLdb
import os
import random
import subprocess
import testtools
import time

from tempest.common.utils import data_utils
from tempest.api.volume import base

from tempest.api.volume.netapp.utils import ontapSSH as ontap
from tempest.api.volume.netapp.utils import devstack_utils as devstack


class NetAppSSCTest(base.BaseVolumeV1AdminTest):
    _interface = "json"

    @classmethod
    def setUpClass(cls):
        super(NetAppSSCTest, cls).setUpClass()
        # Read the cinder.conf file to get the sql connection details
        cinder_config = ConfigParser.SafeConfigParser()
        cinder_config.read('/etc/cinder/cinder.conf')
        driver_name = cinder_config.get('DEFAULT', 'enabled_backends')
        storage_family = cinder_config.get(driver_name,
                                           'netapp_storage_family')
        if storage_family != 'ontap_cluster':
            raise cls.skipException("Driver is not NetApp CDOT")
        cls.protocol = cinder_config.get(driver_name,
                                         'netapp_storage_protocol')
        if cls.protocol == 'nfs':
            cls.shares_file = cinder_config.get(driver_name,
                                                'nfs_shares_config')
        ntap_host = cinder_config.get(driver_name, 'netapp_server_hostname')
        ntap_user = cinder_config.get(driver_name, 'netapp_login')
        ntap_password = cinder_config.get(driver_name, 'netapp_password')
        cls.vserver = cinder_config.get(driver_name, "netapp_vserver")
        cls.filer = ontap.NetappFiler(ntap_host, ntap_user, ntap_password)
        aggrs = cls.filer.get_vserver_aggrs(cls.vserver)
        cls.aggr = random.choice(aggrs)

        sql_connection = str(cinder_config.get('DEFAULT', 'sql_connection'))
        sql_connection = sql_connection.split('/')
        for item in sql_connection:
            if '@' in item:
                sql_connection = item
                break
        sql_connection = sql_connection.split('@')
        login = sql_connection[0]
        cls.server = sql_connection[1]
        login = login.split(':')
        cls.sql_user = login[0]
        cls.sql_pwd = login[1]
        cls.filer.delete_all_volumes(cls.vserver)

    def _delete_volume(self, volume_id):
        """ Deletes a volume and waits for deletion to complete. """
        resp, _ = self.volumes_client.delete_volume(volume_id)
        self.assertEqual(202, resp.status)
        self.volumes_client.wait_for_resource_deletion(volume_id)

    def _delete_volume_type(self, volume_type_id):
        """ Deletes a volume type. """
        resp, _ = self.client.delete_volume_type(volume_type_id)
        self.assertEqual(202, resp.status)

    def _get_db_cursor(self):
        """Returns cursor to sql database."""
        db = MySQLdb.connect(host=self.server,
                             user=self.sql_user,
                             passwd=self.sql_pwd,
                             db='cinder')
        self.addCleanup(db.close())
        cursor = db.cursor()
        self.addCleanup(cursor.close())
        return cursor

    def _get_volume_location(self, vol_id):
        """Returns the provider_location for a volume."""
        cur = self._get_db_cursor()
        cur.execute("SELECT provider_location FROM volumes WHERE id='%s'"
                    % vol_id)
        volume_location = str(cur.fetchone()[0])
        return volume_location

    def _wait_for_volume_status_change(self, volume_id, status):
        """ Waits for a Volume to change a given status. """
        resp, body = self.volumes_client.get_volume(volume_id)
        volume_status = body['status']
        while volume_status == status:
            time.sleep(self.build_interval)
            resp, body = self.volumes_client.get_volume(volume_id)
            volume_status = body['status']

    def _verify_vol_on_flexvol(self, vol_id, flexvol):
        """Verifies volume was created on the correct flexvol."""
        volume_location = self._get_volume_location(vol_id)
        self.assertIn(flexvol, volume_location)

    def _create_vol_type(self, name, extra_specs):
        """Create a volume-type."""
        resp, vol_type = self.client.create_volume_type(name,
                                                        extra_specs=extra_specs
                                                        )
        self.assertEqual(200, resp.status)
        self.assertIn('id', vol_type)
        print vol_type
        self.addCleanup(self._delete_volume_type, vol_type['id'])

    def _create_vol_of_type(self, type_name):
        """Create volume with a specific volume-type."""
        vol_name = data_utils.rand_name("volume-")
        resp, volume = self.volumes_client.create_volume(size=1,
                                                         display_name=vol_name,
                                                         volume_type=type_name)
        self.assertEqual(200, resp.status)
        self.assertIn('id', volume)
        self.addCleanup(self._delete_volume, volume['id'])
        self.volumes_client.wait_for_volume_status(volume['id'], 'available')
        return volume

    def _create_vol_of_type_neg(self, type_name):
        """Create volume with a specific volume-type."""
        vol_name = data_utils.rand_name("volume-")
        resp, volume = self.volumes_client.create_volume(size=1,
                                                         display_name=vol_name,
                                                         volume_type=type_name)
        self.assertEqual(200, resp.status)
        self.assertIn('id', volume)
        self.addCleanup(self._delete_volume, volume['id'])
        self._wait_for_volume_status_change(volume['id'], 'creating')
        resp, body = self.volumes_client.get_volume(volume['id'])
        self.assertEqual('error', body['status'])

    def _ssc_test(self, type_name, flexvol, **kwargs):
        """Base ssc test method."""
        self._create_vol_type(type_name, kwargs)
        volume = self._create_vol_of_type(type_name)
        self._verify_vol_on_flexvol(volume['id'], flexvol)

    def _ssc_test_negative(self, type_name, **kwargs):
        """Base ssc negative test method."""
        self._create_vol_type(type_name, kwargs)
        self._create_vol_of_type_neg(type_name)

    @staticmethod
    def _restart_cinder():
        """Restart cinder services."""
        devstack.restart_cinder()
        time.sleep(10)

    def _create_qos_policy(self, policy_name):
        """Creates a QOS policy on the filer."""
        self.filer.create_qos_policy(policy_name)
        self.addCleanup(self.filer.delete_qos_policy, policy_name)

    def _mount_flexvol(self, name):
        if self.protocol == 'nfs':
            self.filer.mount_volume(self.vserver, name)
            self.addCleanup(self.filer.unmount_volume, self.vserver, name)

    def _create_test_flexvol(self, name, vol_size='5GB', **kwargs):
        """Creates the expected destination flexvol."""
        self.filer.create_volume(self.vserver, name, self.aggr, vol_size,
                                 **kwargs)
        self.addCleanup(self.filer.delete_volume, self.vserver, name)
        self._mount_flexvol(name)

    def _create_honeypot(self, vol_size='10GB', **kwargs):
        """Creates an enticing flexvol larger than expected dest."""
        self.filer.create_volume(self.vserver, 'honeypot', self.aggr, vol_size,
                                 **kwargs)
        self.addCleanup(self.filer.delete_volume, self.vserver, 'honeypot')
        self._mount_flexvol('honeypot')

    def _get_nfs_data_address(self):
        if self.protocol != 'nfs':
            return None
        cmd = ('network interface show -vserver %s -role data -data-protocol '
               'nfs -fields address -status-oper up -status-admin up'
               % self.vserver)
        lines = self.filer.ssh_cmd(cmd)
        self.assertGreaterEqual(len(lines), 3,
                                'No usable NFS data lifs detected on filer')
        lif = lines[2].split()
        address = lif[2]
        return address

    def _update_nfs_shares(self, name, honeypot=True):
        if self.protocol != 'nfs':
            return
        address = self._get_nfs_data_address()
        os.rename(self.shares_file, '%s.bak' % self.shares_file)
        self.addCleanup(os.rename, '%s.bak' % self.shares_file,
                        self.shares_file)
        nfs_file = open(self.shares_file, 'w')
        lines = ['%s:/%s' % (address, name)]
        unmount = 'sudo umount %s:/%s' % (address, name)
        self.addCleanup(subprocess.call, unmount.split())
        if honeypot:
            lines.append('\n%s:/honeypot' % address)
            unmount = 'sudo umount %s:/honeypot' % address
            self.addCleanup(subprocess.call, unmount.split())
        nfs_file.writelines(lines)
        nfs_file.close()
        self.addCleanup(os.remove, self.shares_file)

    def test_ssc_netapp_mirrored(self):
        """Test netapp_mirrored."""
        name = 'mirrored'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name, mirror_aggr=self.aggr,
                                  mirrored=True, mirror_vserver=self.vserver)
        self._create_honeypot()
        self._update_nfs_shares(name)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp_mirrored': 'true'})

    def test_ssc_netapp_mirrored_neg(self):
        """Negative test for netapp_mirrored."""
        self.addCleanup(self._restart_cinder)
        self._create_honeypot()
        self._update_nfs_shares('honeypot', honeypot=False)
        self._restart_cinder()
        self._ssc_test_negative('mirrored', **{'netapp_mirrored': 'true'})

    def test_ssc_netapp_unmirrored(self):
        """Test netapp_unmirrored."""
        name = 'unmirrored'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name)
        self._create_honeypot(mirror_aggr=self.aggr, mirrored=True,
                              mirror_vserver=self.vserver)
        self._update_nfs_shares(name)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp_unmirrored': 'true'})

    def test_ssc_netapp_unmirrored_neg(self):
        """Negative test for netapp_unmirrored."""
        self.addCleanup(self._restart_cinder)
        self._create_honeypot(mirror_aggr=self.aggr, mirrored=True,
                              mirror_vserver=self.vserver)
        self._update_nfs_shares('honeypot', honeypot=False)
        self._restart_cinder()
        self._ssc_test_negative('unmirrored', **{'netapp_unmirrored': 'true'})

    def test_ssc_netapp_dedup(self):
        """Test netapp_dedup."""
        name = 'dedup'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name, dedup=True)
        self._create_honeypot()
        self._update_nfs_shares(name)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp_dedup': 'true'})

    def test_ssc_netapp_dedup_neg(self):
        """Negative test for netapp_dedup."""
        name = 'dedup'
        self.addCleanup(self._restart_cinder)
        self._create_honeypot()
        self._update_nfs_shares('honeypot', honeypot=False)
        self._restart_cinder()
        self._ssc_test_negative(name, **{'netapp_dedup': 'true'})

    def test_ssc_netapp_nodedup(self):
        """Test netapp_nodedup."""
        name = 'nodedup'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name)
        self._create_honeypot(dedup=True)
        self._update_nfs_shares(name)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp_nodedup': 'true'})

    def test_ssc_netapp_nodedup_neg(self):
        """Negative test for netapp_nodedup."""
        name = 'nodedup'
        self.addCleanup(self._restart_cinder)
        self._create_honeypot(dedup=True)
        self._update_nfs_shares('honeypot', honeypot=False)
        self._restart_cinder()
        self._ssc_test_negative(name, **{'netapp_nodedup': 'true'})

    def test_ssc_netapp_compressed(self):
        """Test netapp_compressed."""
        name = 'compression'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name, dedup=True, compression=True)
        self._create_honeypot()
        self._update_nfs_shares(name)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp_compression': 'true'})

    def test_ssc_netapp_compressed_neg(self):
        """Negative test for netapp_compressed."""
        name = 'compression'
        self.addCleanup(self._restart_cinder)
        self._create_honeypot()
        self._update_nfs_shares('honeypot', honeypot=False)
        self._restart_cinder()
        self._ssc_test_negative(name, **{'netapp_compression': 'true'})

    def test_ssc_netapp_nocompressed(self):
        """Test netapp_nocompressed."""
        name = 'nocompression'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name)
        self._create_honeypot(dedup=True, compression=True)
        self._update_nfs_shares(name)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp_nocompression': 'true'})

    def test_ssc_netapp_nocompressed_neg(self):
        """Negative test for netapp_nocompressed."""
        name = 'nocompression'
        self.addCleanup(self._restart_cinder)
        self._create_honeypot(dedup=True, compression=True)
        self._update_nfs_shares('honeypot', honeypot=False)
        self._restart_cinder()
        self._ssc_test_negative(name, **{'netapp_nocompression': 'true'})

    def test_ssc_netapp_thin_provisioned(self):
        """Test netapp_thin_provisioned."""
        name = 'thinprovisioned'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name, thin=True)
        self._create_honeypot()
        self._update_nfs_shares(name)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp_thin_provisioned': 'true'})

    def test_ssc_netapp_thin_provisioned_neg(self):
        """Negative test for netapp_thin_provisioned."""
        name = 'thinprovisioned'
        self.addCleanup(self._restart_cinder)
        self._create_honeypot()
        self._update_nfs_shares('honeypot', honeypot=False)
        self._restart_cinder()
        self._ssc_test_negative(name, **{'netapp_thin_provisioned': 'true'})

    def test_ssc_netapp_thick_provisioned(self):
        """Test netapp_thick_provisioned."""
        name = 'thickprovisioned'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name)
        self._create_honeypot(thin=True)
        self._update_nfs_shares(name)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp_thick_provisioned': 'true'})

    def test_ssc_netapp_thick_provisioned_neg(self):
        """Negative test for netapp_thick_provisioned."""
        name = 'thickprovisioned'
        self.addCleanup(self._restart_cinder)
        self._create_honeypot(thin=True)
        self._update_nfs_shares('honeypot', honeypot=False)
        self._restart_cinder()
        self._ssc_test_negative(name, **{'netapp_thick_provisioned': 'true'})

    # TODO: Update qualified spec tests
    @testtools.skip("Qualified Specs are changing")
    def test_ssc_netapp_raid_dp(self):
        """Test netapp_raidDP."""
        name = 'raiddp'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name)
        self._update_nfs_shares(name, honeypot=False)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp:raid_type': 'raid_dp'})

    @testtools.skip("Qualified Specs are changing")
    def test_ssc_netapp_raid4_neg(self):
        """Test netapp_raid4."""
        name = 'raid4'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name)
        self._update_nfs_shares(name, honeypot=False)
        self._restart_cinder()
        # Create should fail as we do not have raid4 configured
        self._ssc_test_negative(name, **{'netapp:raid_type': 'raid4'})

    @testtools.skip("Qualified Specs are changing")
    def test_ssc_netapp_sata_disk(self):
        """Test netapp_sata_disk."""
        name = 'sata'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name)
        self._update_nfs_shares(name, honeypot=False)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp:disk_type': 'SATA'})

    @testtools.skip("Qualified Specs are changing")
    def test_ssc_netapp_ssd_disk_neg(self):
        """Test netapp_ssd_disk."""
        name = 'ssd'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name)
        self._update_nfs_shares(name, honeypot=False)
        self._restart_cinder()
        # Create should fail as there are no SSD disks
        self._ssc_test_negative(name, **{'netapp:disk_type': 'SSD'})

    # TODO: Rethink how this test is run in light of new QOS implementation
    @testtools.skip("QOS implementation has changed")
    def test_ssc_netapp_qos_policy(self):
        """ Test netapp_qos_policy """
        name = 'qos'
        policy_name = 'qosp2'
        self.addCleanup(self._restart_cinder)
        self._create_qos_policy(policy_name)
        self._create_test_flexvol(name)
        self._ssc_test('vol-type-qos', name, **{'netapp:qos_policy_group':
                                                'p2'})

    def test_ssc_netapp_mixed(self):
        """Test test_ssc_netapp_mixed_unqualified."""
        name = 'mixed'
        self.addCleanup(self._restart_cinder)
        self._create_test_flexvol(name, compression=True, dedup=True)
        self._create_honeypot(dedup=True)
        self._update_nfs_shares(name)
        self._restart_cinder()
        self._ssc_test(name, name, **{'netapp_compression': 'true',
                                      'netapp_dedup': 'true'})
