# Copyright 2014 NetApp
# Copyright 2014 OpenStack Foundation
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

from tempest.api.volume import base
from tempest import config

CONF = config.CONF


class VolumesActionsTestNetApp(base.BaseVolumeV1Test):
    _interface = "json"

    @classmethod
    def setUpClass(cls):
        super(VolumesActionsTestNetApp, cls).setUpClass()
        cls.client = cls.volumes_client

    def setUp(self):
        super(VolumesActionsTestNetApp, self).setUp()
        self.volume = self.create_volume()

    def tearDown(self):
        self.clear_volumes()
        super(VolumesActionsTestNetApp, self).tearDown()

    def test_volume_extend_segmented_large_op(self):
        # Extend a volume by a very large amount. And force ZAPI to
        # segment LUN into multiple block ranges

        # Extend to size > 8 so that next extend must be segmented
        extend_size = 9
        self._extend_vol(extend_size)
        # Extend to a very large size
        extend_size = 300
        self._extend_vol(extend_size)


    def _extend_vol(self, extend_size):
        resp, body = self.client.extend_volume(self.volume['id'], extend_size)
        self.assertEqual(202, resp.status)
        self.client.wait_for_volume_status(self.volume['id'], 'available')
        resp, volume = self.client.get_volume(self.volume['id'])
        self.assertEqual(200, resp.status)
        self.assertEqual(extend_size, int(volume['size']))

    def test_volume_extend_multi_ops(self):
        # Extend a volume multiple times by various sizes
        for x in range(0, 5):
            resp, volume = self.client.get_volume(self.volume['id'])
            self.assertEqual(200, resp.status)
            extend_size = int(volume['size']) + 1
            self._extend_vol(extend_size)


class VolumesActionsTestNetAppXML(VolumesActionsTestNetApp):
    _interface = "xml"
