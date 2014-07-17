# Copyright 2014 OpenStack Foundation
# Copyright 2014 NetApp
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
import base64
import binascii
import ConfigParser
import json
import random
import time
import uuid
import subprocess

import requests
import re
from tempest.api.volume import base
from tempest.common.utils import data_utils
from tempest.openstack.common import log as logging
from tempest import config


CONF = config.CONF


class NetAppEseriesTest(base.BaseVolumeV2Test):
    _interface = 'json'
    LOG = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls):
        super(NetAppEseriesTest, cls).setUpClass()
        cls.cinder_client = cls.os.volumes_v2_client
        cls.glance_client = cls.os.image_client_v2
        cls.nova_client = cls.servers_client
        cls.cinder_config = cls._read_cinder_config()
        cls.driver_name = cls.cinder_config.get('DEFAULT', 'enabled_backends')
        cls.storage_family = cls.cinder_config.get(cls.driver_name,
                                                   'netapp_storage_family')
        if cls.storage_family != 'eseries':
            raise cls.skipException("Driver is not NetApp Eseries")
        cls.proxy_host = cls.cinder_config.get(cls.driver_name,
                                               'netapp_server_hostname')
        cls.proxy_port = cls.cinder_config.get(cls.driver_name,
                                               'netapp_server_port')
        cls.proxy_path = cls.cinder_config.get(cls.driver_name,
                                               'netapp_webservice_path')
        cls.proxy_user = cls.cinder_config.get(cls.driver_name,
                                               'netapp_login')
        cls.proxy_password = cls.cinder_config.get(cls.driver_name,
                                                   'netapp_password')
        cls.controller_ips = cls.cinder_config.get(cls.driver_name,
                                                   'netapp_controller_ips')
        cls.controller_ips = cls.controller_ips.split(',')
        try:
            cls.es_password = cls.cinder_config.get(cls.driver_name,
                                                    'netapp_sa_password')
        except ConfigParser.NoOptionError:
            cls.es_password = None
        try:
            cls.transport_type = cls.cinder_config.get(cls.driver_name,
                                                       'netapp_transport_type')
        except ConfigParser.NoOptionError:
            cls.transport_type = 'http'

    def setUp(self):
        super(NetAppEseriesTest, self).setUp()
        self.system_id = self._get_system_id()

    @staticmethod
    def _read_cinder_config():
        """Objectifies cinder.conf as a ConfigParser object."""
        configuration = ConfigParser.SafeConfigParser()
        configuration.read('/etc/cinder/cinder.conf')
        return configuration

    def _get_system_id(self):
        """Returns the proxy's systemID of of the eseries array."""
        path = "/storage-systems"
        data = {"controllerAddresses": self.controller_ips}
        response = self._send_message(path, 'POST', data)
        self.assertLess(response.status_code, 300)
        system = response.json()
        return system.get('id')

    def _send_message(self, url, method='GET', body=None):
        """Send a REST message."""
        headers = {'Accept': 'application/json', 'Content-Type':
                   'application/json'}
        if body and self.es_password:
            body.setdefault('password', self.es_password)
        body = json.dumps(body) if body else None
        url = self.transport_type + '://' + self.proxy_host + ':' + \
            self.proxy_port + self.proxy_path + url
        if method == 'POST':
            return requests.post(url, body, auth=(self.proxy_user,
                                                  self.proxy_password),
                                 headers=headers)
        elif method == 'GET':
            return requests.get(url, auth=(self.proxy_user,
                                           self.proxy_password),
                                headers=headers)
        elif method == 'DELETE':
            return requests.delete(url, auth=(self.proxy_user,
                                              self.proxy_password),
                                   headers=headers)

    def _do_delete(self, path):
        """Send delete message."""
        self._send_message(path, 'DELETE')

    def _create_server(self):
        """Create a nova instance."""
        srv_name = data_utils.rand_name('Instance')
        _, server = self.nova_client.create_server(srv_name,
                                                   self.image_ref,
                                                   self.flavor_ref)
        self.addCleanup(self.nova_client.delete_server, server['id'])
        self.nova_client.wait_for_server_status(server['id'], 'ACTIVE')
        return server

    def _create_volume(self, size=1, **kwargs):
        """Create a cinder volume."""
        vol_name = data_utils.rand_name('Volume')
        resp, volume = self.cinder_client.create_volume(size,
                                                        display_name=vol_name,
                                                        **kwargs)
        self.addCleanup(self.cinder_client.delete_volume, volume['id'])
        self.assertEqual(202, resp.status)
        self.cinder_client.wait_for_volume_status(volume['id'], 'available')
        return volume

    def _attach_volume(self, server, volume):
        """Attach volume to nova instance."""
        resp, attachment = self.nova_client.attach_volume(server['id'],
                                                          volume['id'])
        self.addCleanup(self._detach_volume, server['id'], volume['id'])
        self.assertEqual(200, resp.status)
        self.cinder_client.wait_for_volume_status(volume['id'], 'in-use')

    def _create_host(self):
        """Create a host on eseries."""
        label = convert_uuid_to_es_fmt(uuid.uuid4())
        port_label = convert_uuid_to_es_fmt(uuid.uuid4())
        host_type = 'LnxALUA'
        port_suffix = '%012x' % random.randrange(16**12)
        port_id = 'iqn.1993-08.org.debian:01:' + port_suffix
        port = {'type': 'iscsi', 'port': port_id, 'label': port_label}
        path = '/storage-systems/%s/hosts' % self.system_id
        data = {'name': label, 'hostType': host_type, 'ports': [port]}
        response = self._send_message(path, 'POST', data)
        self.assertLess(response.status_code, 300)
        return response.json()

    def _delete_host(self, host_id):
        """Deletes a host from eseries array."""
        path = '/storage-systems/%s/hosts/%s' % (self.system_id, host_id)
        self._do_delete(path)

    def _get_eseries_volume(self, vol_id):
        """Returns details about a lun on eseries array."""
        es_label = convert_uuid_to_es_fmt(vol_id)
        vols = self._get_volumes_list()
        for vol in vols:
            if vol.get('label') == es_label:
                return vol
        return None

    def _create_mapping(self, volume, host):
        """Maps a lun to a given host on eseries array."""
        lun_id = random.randint(0, 255)
        path = "/storage-systems/%s/volume-mappings" % self.system_id
        data = {'mappableObjectId': volume.get('volumeRef'), 'targetId':
                host.get('hostRef'), 'lun': lun_id}
        print "data=%s" % data
        mapping = self._send_message(path, 'POST', data)
        return mapping.json()

    def _create_lun_mapping(self, volume):
        """Maps a lun to a randomly generated host on eseries array."""
        host = self._create_host()
        self.addCleanup(self._delete_host, host.get('hostRef'))
        es_vol = self._get_eseries_volume(volume['id'])
        self.assertIsNotNone(es_vol)
        mapping = self._create_mapping(es_vol, host)
        self.addCleanup(self._delete_mapping, mapping.get('lunMappingRef'))
        return mapping

    def _get_volumes_list(self):
        """Returns a list of luns on eseries array."""
        path = '/storage-systems/%s/volumes' % self.system_id
        my_list = self._send_message(path)
        return my_list.json()

    def _delete_mapping(self, map_id):
        """Deletes lun mapping from eseries array."""
        path = "/storage-systems/%s/volume-mappings/%s" % (self.system_id,
                                                           map_id)
        self._do_delete(path)

    def _detach_volume(self, server_id, vol_id):
        """Detaches volume from nova instance."""
        resp, _ = self.nova_client.detach_volume(server_id, vol_id)
        self.assertEqual(202, resp.status)
        self.cinder_client.wait_for_volume_status(vol_id, 'available')

    def _delete_image(self, image_id):
        """Deletes an image from glance."""
        self.glance_client.delete_image(image_id)
        self.glance_client.wait_for_resource_deletion(image_id)

    def _upload_to_image(self, volume):
        """Uploads a volume to glance."""
        image_name = data_utils.rand_name('Image')
        resp, image = self.cinder_client.upload_volume(volume['id'],
                                                       image_name, 'raw')
        self.addCleanup(self._delete_image, image['image_id'])
        self.assertGreaterEqual(resp.status, 200)
        self.assertLess(resp.status, 300)
        self.cinder_client.wait_for_volume_status(volume['id'], 'uploading')
        self.cinder_client.wait_for_volume_status(volume['id'], 'available')
        return image

    def _verify_image(self, image_id):
        """Verifies that the image has been successfully created."""
        resp, image = self.glance_client.get_image(image_id)
        self.assertEqual(200, resp.status)
        self.assertEqual('active', image['status'])

    def _verify_volume_attached_to_server(self, volume_id, server_id):
        """Verifies that volume has successfully attached to server."""
        resp, volume = self.cinder_client.get_volume(volume_id)
        self.assertEqual(200, resp.status)
        self.assertNotEmpty(volume['attachments'], 'Volume %s is not '
                                                   'attached to any servers'
                                                   % volume_id)
        self.assertEqual(server_id, volume['attachments'][0]['server_id'])

    def _get_eseries_volume_preferred_controller_id(self, volref):
        """Returns the preferred controller (1 or 2)."""
        # label = convert_uuid_to_es_fmt(volume['id'])
        # print "label=%s" % label
        #volref = volume.get('volumeRef')
        path = "/storage-systems/%s/volumes/%s" % (self.system_id, volref)
        response = self._send_message(path)
        self.assertLess(response.status_code, 300)
        volinfo = response.json()
        preferredcontroller = volinfo['preferredControllerId']
        return preferredcontroller

    def _get_iscsi_target_ips_by_controller(self, preferredcontroller):
        """Returns a list of iscsi target ips for a controller"""
        path = "/storage-systems/%s/iscsi/target-settings/" % self.system_id
        response = self._send_message(path)
        self.assertLess(response.status_code, 300)
        iscsitargets = response.json()
        ips = []
        for port in iscsitargets['portals']:
            if port['groupTag'] == int(preferredcontroller):
                addr = port['ipAddress']
                #print "addr=%s" % addr
                if addr['addressType'] == 'ipv4':
                    #print "addr=%s" % addr
                    ips.append(addr['ipv4Address'])
        print '\n'
        print "targetips=%s" % ips
        return ips

    def _change_volume_ownership(self, volumeref, controllerid):
        """Changes the preferred controller of a volume"""
        path = "/storage-systems/%s/symbol/assignVolumeOwnership" % (self.system_id)
        data = { "volumeRef": volumeref,
                 "manager": controllerid}
        print "data for vol ownership chg=%s" % data
        response = self._send_message(path, 'POST', data)
        self.assertEqual(response.status_code, 200)
        return response

    def _get_alternate_controller(self, preferredcontroller):
        prefix = preferredcontroller[:-1]
        suffix = preferredcontroller[-1]
        newsuffix = None
        if preferredcontroller[-1] == '1':
            newsuffix = "2"
        else:
            newsuffix = "1"
        longcontrollerstr = str(prefix) + str(newsuffix)
        shortcontrollerstr = str(newsuffix)
        print "suffix=%s" % newsuffix
        return shortcontrollerstr, longcontrollerstr

    def _get_current_controller(self, preferredcontroller):
        prefix = preferredcontroller[:-1]
        suffix = preferredcontroller[-1]
        newsuffix = None
        if preferredcontroller[-1] == '1':
            newsuffix = "1"
        else:
            newsuffix = "2"
        longcontrollerstr = str(prefix) + str(newsuffix)
        shortcontrollerstr = str(newsuffix)
        return shortcontrollerstr, longcontrollerstr

    def _verify_mapped_path(self, targetips):
        path = "/dev/disk/by-path/"
        #print "path=%s" % path
        mappings = [subprocess.check_output(["ls", path])]
        #print mappings
        for m in mappings:
            for ip in targetips:
                result=re.findall(ip, m)
                if m:
                    print "targetip %s found in %s" % (targetips, path)
                    return True
                else:
                    return False

    def test_tc1_attach_lun_while_already_mapped(self):
        """Attach a pre-mapped lun to a nova instance."""
        server = self._create_server()
        volume = self._create_volume()
        self._create_lun_mapping(volume)
        self._attach_volume(server, volume)
        self._verify_volume_attached_to_server(volume['id'], server['id'])

    def test_tc2_upload_to_image_while_lun_already_mapped(self):
        """Upload a pre-mapped lun to glance."""
        volume = self._create_volume()
        self._create_lun_mapping(volume)
        image = self._upload_to_image(volume)
        self._verify_image(image['image_id'])

    def test_tc13_concurrent_create_from_images(self):
        """Creates 2 volumes from a 1g image concurrently."""
        base_vol = self._create_volume()
        image = self._upload_to_image(base_vol)
        vol1 = self._create_volume_from_image(image['image_id'])
        time.sleep(10)
        vol2 = self._create_volume_from_image(image['image_id'])
        self.cinder_client.wait_for_volume_status(vol1['id'], 'available')
        self.cinder_client.wait_for_volume_status(vol2['id'], 'available')

    def test_tc35_verify_preferred_path(self):
        """Verifies that the mapped path is to the correct controller"""
        server = self._create_server()
        volume = self._create_volume()
        volinfo = self._get_eseries_volume(volume.get('id'))
        volumeref = volinfo.get('volumeRef')
        self.assertIsNotNone(volumeref)
        #find preferred controller from volume info
        preferredcontroller = self._get_eseries_volume_preferred_controller_id(volumeref)
        #get alternate controller
        shortcontrollerstr, longcontrollerstr = self._get_current_controller(preferredcontroller)
        #get list of target ips for the preferred controller
        targetips = self._get_iscsi_target_ips_by_controller(shortcontrollerstr)
        # skip changing owner until bug resolved with web proxy api
        #response = self._change_volume_ownership(volumeref, longcontrollerstr)
        self._attach_volume(server, volume)
        self._verify_volume_attached_to_server(volume['id'], server['id'])
        preferredcontroller = self._get_eseries_volume_preferred_controller_id(volumeref)
        self._get_eseries_volume(volume.get('id'))
        self._verify_mapped_path(targetips)

def encode_hex_to_base32(hex_string):
    """Encodes hex to base32 bit as per RFC4648."""
    bin_form = binascii.unhexlify(hex_string)
    return base64.b32encode(bin_form)


def decode_base32_to_hex(base32_string):
    """Decodes base32 string to hex string."""
    bin_form = base64.b32decode(base32_string)
    return binascii.hexlify(bin_form)


def convert_uuid_to_es_fmt(uuid_str):
    """Converts uuid to e-series compatible name format."""
    uuid_base32 = encode_hex_to_base32(uuid.UUID(str(uuid_str)).hex)
    return uuid_base32.strip('=')


def convert_es_fmt_to_uuid(es_label):
    """Converts e-series name format to uuid."""
    es_label_b32 = es_label.ljust(32, '=')
    return uuid.UUID(binascii.hexlify(base64.b32decode(es_label_b32)))
