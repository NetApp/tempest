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
        resp, resp_body = self.shares_client.create_access_group('ip')
        self.assertEqual('200', resp['status'])
        self.assertEqual('ip', resp_body['type'])

    @test.attr(type=['gate'])
    def test_modify_access_group(self):
        resp, resp_body = self.shares_client.create_access_group('ip')
        self.assertEqual('200', resp['status'])
        self.assertEqual('ip', resp_body['type'])
        access_group_id = resp_body['id']
        resp, resp_body = self.shares_client.update_access_group(
            access_group_id, description='modified', name='newName')
        self.assertEqual('200', resp['status'])
        self.assertEqual('modified', resp_body['description'])
        self.assertEqual('newName', resp_body['name'])

    @test.attr(type=['gate'])
    def test_list_all_access_groups(self):
        raise NotImplementedError

    @test.attr(type=['gate'])
    def test_list_all_access_groups_detailed(self):
        raise NotImplementedError

    @test.attr(type=['gate'])
    def test_show_access_group(self):
        raise NotImplementedError

    @test.attr(type=['gate'])
    def test_delete_access_group(self):
        raise NotImplementedError

    @test.attr(type=['gate'])
    def test_add_entry_to_access_group(self):
        raise NotImplementedError

    @test.attr(type=['gate'])
    def test_remove_entry_from_access_group(self):
        raise NotImplementedError


class AccessGroupsCIFSTest(AccessGroupsNFSTest):
    """Covers Access Group Functionality as it's related to CIFS share types"""
    protocol = 'cifs'
