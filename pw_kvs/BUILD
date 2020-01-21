# Copyright 2020 The Pigweed Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

load(
    "//pw_build:pigweed.bzl",
    "pw_cc_library",
    "pw_cc_test",
)

package(default_visibility = ["//visibility:public"])

licenses(["notice"])  # Apache License 2.0

pw_cc_library(
    name = "pw_kvs",
    srcs = [
        "flash.cc",
        "key_value_store.cc",
    ],
    hdrs = [
        "public/pw_kvs/assert.h",
        "public/pw_kvs/flash.h",
        "public/pw_kvs/flash_memory.h",
        "public/pw_kvs/in_memory_fake_flash.h",
        "public/pw_kvs/key_value_store.h",
        "public/pw_kvs/partition_table_entry.h",
    ],
    includes = ["public"],
    deps = [
        "//pw_checksum",
        "//pw_log",
        "//pw_status",
        "//pw_string",
    ],
)

pw_cc_test(
    name = "key_value_store_test",
    srcs = ["key_value_store_test.cc"],
    deps = [
        ":pw_kvs",
        "//pw_checksum",
        "//pw_log",
    ],
)

pw_cc_test(
    name = "key_value_store_sub_sector_test",
    srcs = ["key_value_store_sub_sector_test.cc"],
    deps = [
        ":pw_kvs",
        "//pw_checksum",
        "//pw_log",
    ],
)