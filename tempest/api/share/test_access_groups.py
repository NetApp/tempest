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

from tempest.api.share import base
from tempest import config_share as config
from tempest import exceptions
from tempest import test
from tempest.clients_share import Manager
from tempest.clients_share import AdminManager
from tempest.common.utils import data_utils

CONF = config.CONF


class AccessGroupsNFSTest(base.BaseSharesTest):
    """Covers Access Group Functionality as it's related to NFS share types"""
    protocol = 'nfs'

    @classmethod
    def setUpClass(cls):
        super(AccessGroupsNFSTest, cls).setUpClass()
        manager = Manager(username='demo', password='nomoresecrete',
                              tenant_name='demo')
        admin_manager = AdminManager()
        cls.client = manager.shares_client
        cls.identity_admin_client = admin_manager.identity_client

    @test.attr(type=['gate'])
    def test_create_access_group(self):
        access_group_id, _ = self._create_and_validate_access_group(
            name='test')
        self.addCleanup(
            self.shares_client.delete_access_group, access_group_id)


    @test.attr(type=['gate'])
    def test_modify_access_group(self):
        access_group_id, _ = self._create_and_validate_access_group(
            name='test')
        self.addCleanup(self.shares_client.delete_access_group,
                        access_group_id)
        _ = self._update_and_validate_access_group(access_group_id,
                                                   name='newName',
                                                   desc='newDesc')

    @test.attr(type=['gate'])
    def test_list_all_access_groups(self):
        # Create two access groups
        access_group_id1, _ = self._create_and_validate_access_group(
            name='test1')
        self.addCleanup(
            self.shares_client.delete_access_group, access_group_id1)
        access_group_id2, _ = self._create_and_validate_access_group(
            name='test2')
        self.addCleanup(
            self.shares_client.delete_access_group, access_group_id2)
        # And then list them with details
        resp, resp_body = self.shares_client.list_access_groups()
        self.assertEqual('200', resp['status'])
        #self.assertIn('test1', resp_body)
        #self.assertIn('test2', resp_body)

    @test.attr(type=['gate'])
    def test_list_all_access_groups_detailed(self):
        # Create two access groups
        access_group_id1, _ = self._create_and_validate_access_group(
            name='test1')
        self.addCleanup(
            self.shares_client.delete_access_group, access_group_id1)
        access_group_id2, _ = self._create_and_validate_access_group(
            name='test2')
        self.addCleanup(
            self.shares_client.delete_access_group, access_group_id2)
        # And then list them with details
        resp, resp_body = self.shares_client.list_access_groups_detail()
        self.assertEqual('200', resp['status'])
        #self.assertIn('entries', resp_body)

    @test.attr(type=['gate'])
    def test_show_access_group(self):
        access_group_id, _ = self._create_and_validate_access_group(
            name='test', desc='show_test')
        self.addCleanup(
            self.shares_client.delete_access_group, access_group_id)
        resp, resp_body = self.shares_client.get_access_group(access_group_id)
        self.assertEqual('200', resp['status'])
        self.assertEqual('test', resp_body['name'])
        self.assertEqual('show_test', resp_body['description'])
        self.assertEqual(access_group_id, resp_body['id'])

    @test.attr(type=['gate'])
    def test_delete_access_group(self):
        access_group_id, _ = self._create_and_validate_access_group()
        resp, body = self.shares_client.delete_access_group(access_group_id)
        self.assertEqual('202', resp['status'])

    @test.attr(type=['gate'])
    def test_add_entry_to_access_group(self):
        raise NotImplementedError

    @test.attr(type=['gate'])
    def test_remove_entry_from_access_group(self):
        raise NotImplementedError

    def _create_and_validate_access_group(self, name=None, desc=None):
        resp, resp_body = self.shares_client.create_access_group('ip',
                                                                 name=name,
                                                                 desc=desc)
        self.assertEqual('200', resp['status'])
        self.assertEqual('ip', resp_body['type'])
        if name:
            self.assertEqual(name, resp_body['name'])
        if desc:
            self.assertEqual(desc, resp_body['description'])
        return resp_body['id'], resp_body

    def _update_and_validate_access_group(self, access_group_id, name=None,
                                          desc=None):
        resp, resp_body = self.shares_client.update_access_group(
            access_group_id, type='ip', description=desc, name=name)
        self.assertEqual('200', resp['status'])
        if name:
            self.assertEqual(name, resp_body['name'])
        if desc:
            self.assertEqual(desc, resp_body['description'])
        return resp_body

class AccessGroupsCIFSTest(AccessGroupsNFSTest):
    """Covers Access Group Functionality as it's related to CIFS share types"""
    protocol = 'cifs'


