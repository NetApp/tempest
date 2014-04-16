# Copyright (c) 2014 NetApp, Inc.
# All Rights Reserved.
"""
Created on Feb 6, 2014

@author: akerr

NOTE: THESE TESTS SHOULD --NOT-- BE RUN IN PARALLEL WITH OTHER TESTS.  THESE
TESTS BOUNCE THE CINDER AND GLANCE SERVICES AND CHANGE CONFIG FILES.

This test requires that the NetApp driver is properly configured in cinder
.conf and the nfs shares config file, and that the copy offload binary has
beeen correctly downloaded to the proper location.  It will attempt to do
the rest of the setup by creating a volume on the vserver for glance to use,
configuring glance to use that volume, creating a proper netapp.json file,
mounting the volume locally for glance, ensuring that cinder is using the
right glance api version and restarting both Cinder and Glance.  This setup
is run prior to each test, and so additional setup is done on a test-by-test
basis to support the desired scenario.
"""
import ConfigParser
import random
import subprocess
import time

import os
from tempest.api.volume import base
from tempest.openstack.common import log as logging
from tempest import config
from tempest.api.volume.netapp.utils import ontapSSH
import tempest.api.volume.netapp.utils.devstack_utils as devstack


CONF = config.CONF
LOG = logging.getLogger(__name__)


class TestCopyOffload(base.BaseVolumeV2Test):
    @classmethod
    def setUpClass(cls):
        super(TestCopyOffload, cls).setUpClass()
        cls.client = cls.os.volumes_v2_client
        cls.image_client = cls.os.image_client_v2

    def setUp(self):
        super(TestCopyOffload, self).setUp()
        # Configure Glance and Cinder properly
        self.glance = ConfigParser.SafeConfigParser()
        self.glance.read('/etc/glance/glance-api.conf')
        self.cinder = ConfigParser.SafeConfigParser()
        self.cinder.read('/etc/cinder/cinder.conf')
        backends = self.cinder.get('DEFAULT', 'enabled_backends')
        backends = backends.split(',')
        self.vserver = None
        for backend in backends:
            try:
                self.tool = self.cinder.get(backend,
                                            'netapp_copyoffload_tool_path')
            except ConfigParser.NoOptionError:
                continue
            if os.path.isfile(self.tool):
                self.vserver = self.cinder.get(backend, 'netapp_vserver')
                self.server = self.cinder.get(backend,
                                              'netapp_server_hostname')
                self.login = self.cinder.get(backend, 'netapp_login')
                self.password = self.cinder.get(backend, 'netapp_password')
                self.backend = backend
        self.assertIsNotNone(self.vserver,
                             'No backend is configured for copy offload')
        self.assertTrue(os.path.isfile(self.tool),
                        '%s does not exist' % self.tool)
        self.cinder.set('DEFAULT', 'glance_api_version', '2')

        with open('/etc/cinder/cinder.conf', 'w+') as configfile:
            self.cinder.write(configfile)
        configfile.close()

        self.shares_file = self.cinder.get(self.backend, 'nfs_shares_config')
        share = open(self.shares_file, 'r')
        self.shares = share.readline().strip()
        share.close()

        # Query vserver for glance volume, if it doesn't already exist create
        # on a random aggregate and find out the vserver's data IP address
        self.filer = ontapSSH.NetappFiler(self.server,
                                          self.login,
                                          self.password)
        if 'glance' not in self.filer.get_vserver_volumes(self.vserver):
            aggrs = self.filer.get_vserver_aggrs(self.vserver)
            try:
                aggr = random.choice(aggrs)
            except IndexError as e:
                LOG.error('Vserver %s does not appear to have any aggregates'
                          % self.vserver)
                raise e
            self.filer.create_volume(self.vserver, 'glance', aggr)
        self.assertIsNotNone(self.filer.get_volume(self.vserver, 'glance'),
                             'glance volume could not be found or created on '
                             'server %s vserver %s'
                             % (self.server, self.vserver))
        self.filer.unmount_volume('glance')
        self.filer.mount_volume('glance')
        try:
            self.vserver_ip = random.choice(
                self.filer.get_vserver_data_ips(self.vserver))
        except IndexError:
            print('Vserver %s does not appear to have any data ips'
                  % self.vserver)
            exit(1)

        # Use filesystem store
        self.glance.set('DEFAULT', 'default_store', 'file')

        # Mount/remount the filesystem store
        self.image_store = self.glance.get('DEFAULT',
                                           'filesystem_store_datadir')
        if self.image_store[-1] == '/':
            self.image_store = self.image_store[:-1]
        mount = subprocess.check_output("mount").decode("utf-8")
        if self.image_store in mount:
            self._unmount_glance()
        self._mount_glance()

        # The metatdata file is configured
        self._reset_json()
        self.glance.set('DEFAULT', 'filesystem_store_metadata_file',
                        '/etc/glance/netapp.json')

        # Multiple locations is True
        self.glance.set('DEFAULT', 'show_multiple_locations', 'True')

        # show_image_direct_url is True
        self.glance.set('DEFAULT', 'show_image_direct_url', 'True')

        with open('/etc/glance/glance-api.conf', 'w+') as configfile:
            self.glance.write(configfile)
        configfile.close()
        self._restart_services()

    def tearDown(self):
        del self.filer
        super(TestCopyOffload, self).tearDown()

    def _delete_image(self, image_id):
        # Delete image from glance
        self.image_client.delete_image(image_id)

    def _delete_volume(self, volume_id):
        resp, _ = self.client.delete_volume(volume_id)
        self.assertEqual(202, resp.status)
        self.client.wait_for_resource_deletion(volume_id)

    def _reset_json(self):
        metadatafile = open('/etc/glance/netapp.json', 'w')
        json = str('{'
                   '"share_location": "nfs://%s/glance",'
                   '"mount_point": "%s",'
                   '"type": "nfs"'
                   '}' % (self.vserver_ip, self.image_store))
        metadatafile.write(json)
        metadatafile.close()

    def _restart_services(self):
        # Restart glance and cinder
        devstack.restart_cinder()
        devstack.restart_glance()
        # Give services time to initialize
        time.sleep(20)

    def _mount_glance(self):
        subprocess.check_call(["sudo",
                               "mount",
                               "-t",
                               "nfs",
                               "-o",
                               "vers=4",
                               "%s:/glance" % self.vserver_ip,
                               self.image_store])

    def _unmount_glance(self):
        subprocess.check_call(["sudo", "umount", self.image_store])

    def _create_volume(self, size, **kwargs):
        resp, volume = self.client.create_volume(size, **kwargs)
        self.assertEqual(202, resp.status)
        self.assertIn('id', volume)
        self.addCleanup(self._delete_volume, volume['id'])
        # Wait for volume creation
        self.client.wait_for_volume_status(volume['id'], 'available')
        return volume

    def _upload_volume(self, vol_id, image_name):
        resp, image = self.client.upload_volume(vol_id, image_name, 'raw')
        self.addCleanup(self._delete_image, image['image_id'])
        # Wait for volume to become available again
        self.client.wait_for_volume_status(vol_id, 'available')
        # Ensure image was uploaded properly
        resp, image_get = self.image_client.get_image(image['image_id'])
        self.assertEqual('active', image_get['status'])
        return image

    def _get_copy_reqs_and_failures(self):
        rtn = self.filer.ssh_cmd("node run -node * -command \"priv set diag; "
                                 "stats show copy_manager:%s\"" % self.vserver)
        copy_reqs = 0
        copy_failures = 0
        for line in rtn:
            if ':copy_reqs:' in line:
                copy_reqs += int(line.split(':')[-1])
            if ':copy_failures:' in line:
                copy_failures += int(line.split(':')[-1])
        return copy_reqs, copy_failures

    def _do_image_download_test(self):
        """ This function creates a new volume, uploads it to glance, and
            creates a new volume from that image.  It returns the number of
            copy_reqs and copy_failures generated by the image download """
        # Create initial volume
        LOG.debug('Creating volume')
        volume = self._create_volume(1, display_name='vol-origin')

        # Create image from origin volume
        LOG.debug('Uploading volume %s' % volume['id'])
        image = self._upload_volume(volume['id'], 'colImage')

        # Check initial volume copy_reqs
        LOG.debug('Checking initial copy reqs')
        copy_reqs_origin, copy_failures_origin = \
            self._get_copy_reqs_and_failures()

        # Create volume from image
        LOG.debug('Creating volume from image %s' % image['image_id'])
        self._create_volume(1, display_name='image_vol',
                            imageRef=image['image_id'])

        # Check final volume copy_reqs
        LOG.debug('Checking final copy reqs')
        copy_reqs_final, copy_failures_final = \
            self._get_copy_reqs_and_failures()

        # Check difference in copy_reqs
        copy_reqs = copy_reqs_final - copy_reqs_origin
        copy_failures = copy_failures_final - copy_failures_origin
        return copy_reqs, copy_failures

    def test_image_download_different_flexvols_positive(self):
        """ This test attempts to use copy offload when downloading an image
            from glance that resides in a different flexvol than where the
            cinder volumes are stored """
        copy_reqs, copy_failures = self._do_image_download_test()
        self.assertEqual(1, copy_reqs,
                         '%s copy_reqs detected, expected 1' % copy_reqs)
        self.assertEqual(0, copy_failures,
                         '%s copy_failures detected, expected 0' %
                         copy_failures)

    def test_image_download_same_flexvol_negative(self):
        """ This tests the use of copy offload when downloading an image
            from glance that resides in the same flexvol as where the
            cinder volumes are stored.  Cloning should be used instead of
            copy offload """
        self._unmount_glance()
        # Force cinder to use only 1 volume for backend
        share_file = self.shares_file
        nfs_file = open(share_file, 'r')
        nfs = nfs_file.readline()
        nfs_file.close()
        os.rename(share_file, '%s.bak' % share_file)
        self.addCleanup(os.rename, '%s.bak' % share_file, share_file)
        nfs_file = open(share_file, 'w')
        nfs_file.write(nfs)
        nfs_file.close()
        self.addCleanup(os.remove, share_file)

        ip = nfs.split('/')[0].strip()
        vol = nfs.split(':')[-1].strip()
        metadatafile = open('/etc/glance/netapp.json', 'w')
        metadatafile.write(str('{'
                               '"share_location": "nfs://%s%s",'
                               '"mount_point": "%s",'
                               '"type": "nfs"'
                               '}' % (ip[:-1], vol, self.image_store)))
        metadatafile.close()
        subprocess.check_call(["sudo", "mount", "-t", "nfs", "-o", "vers=4",
                               "%s" % nfs.strip(), self.image_store])
        self._restart_services()

        copy_reqs, copy_failures = self._do_image_download_test()
        self.assertEqual(0, copy_reqs,
                         '%s copy_reqs detected, expected 0' % copy_reqs)
        self.assertEqual(0, copy_failures,
                         '%s copy_failures detected, expected 0' %
                         copy_failures)

    def test_image_download_bad_json_negative(self):
        """ This tests the use of copy offload when downloading an image
            from glance when the data in the json file is incorrect.
            HTTP download should be used a fall-back """
        metadatafile = open('/etc/glance/netapp.json', 'w')
        metadatafile.write(str('{'
                               '"share_location": "nfs://bogus.com/bogus",'
                               '"mount_point": "%s",'
                               '"type": "nfs"'
                               '}' % self.image_store))
        metadatafile.close()
        copy_reqs, copy_failures = self._do_image_download_test()
        self.assertEqual(0, copy_reqs,
                         '%s copy_reqs detected, expected 0' % copy_reqs)
        self.assertEqual(0, copy_failures,
                         '%s copy_failures detected, expected 0' %
                         copy_failures)

    def test_image_download_bad_binary_negative(self):
        """ This tests the use of copy offload when downloading an image
            from glance when the copy offload binary doesn't exist.
            HTTP download should be used a fall-back """
        binary_loc = self.tool
        os.rename(self.tool, '%s.bak' % binary_loc)
        self.addCleanup(os.rename, '%s.bak' % binary_loc, binary_loc)
        copy_reqs, copy_failures = self._do_image_download_test()
        self.assertEqual(0, copy_reqs,
                         '%s copy_reqs detected, expected 0' % copy_reqs)
        self.assertEqual(0, copy_failures,
                         '%s copy_failures detected, expected 0' %
                         copy_failures)
