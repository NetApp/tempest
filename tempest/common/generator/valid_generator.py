# Copyright 2014 Deutsche Telekom AG
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

import tempest.common.generator.base_generator as base
from tempest.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class ValidTestGenerator(base.BasicGeneratorSet):
    @base.generator_type("string")
    @base.simple_generator
    def generate_valid_string(self, schema):
        size = schema.get("minLength", 0)
        # TODO(dkr mko): handle format and pattern
        return "x" * size

    @base.generator_type("integer")
    @base.simple_generator
    def generate_valid_integer(self, schema):
        # TODO(dkr mko): handle multipleOf
        if "minimum" in schema:
            minimum = schema["minimum"]
            if "exclusiveMinimum" not in schema:
                return minimum
            else:
                return minimum + 1
        if "maximum" in schema:
            maximum = schema["maximum"]
            if "exclusiveMaximum" not in schema:
                return maximum
            else:
                return maximum - 1
        return 0

    @base.generator_type("object")
    @base.simple_generator
    def generate_valid_object(self, schema):
        obj = {}
        for k, v in schema["properties"].iteritems():
            obj[k] = self.generate_valid(v)
        return obj

    def generate_valid(self, schema):
        return self.generate(schema)[0][1]
