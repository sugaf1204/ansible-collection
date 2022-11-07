#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2022, XLAB Steampunk <steampunk@xlab.si>
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: block_device

author:
  - Polona Mihalič (@PolonaM)
short_description: Creates, updates or deletes MAAS machines' block devices.
description:
  - If I(state) is C(present) and I(name) is not found, creates new block device.
  - If I(state) is C(present) and I(name) is found, updates an existing block device.
  - If I(state) is C(absent) selected block device is deleted.
version_added: 1.0.0
extends_documentation_fragment:
  - canonical.maas.cluster_instance
seealso: []
options:
  state:
    description:
      - Desired state of the block device.
    choices: [ present, absent ]
    type: str
    required: True
  machine_fqdn:
    description:
      - Fully qualified domain name of the machine that owns the block device.
      - Serves as unique identifier of the machine.
      - If machine is not found the task will FAIL.
    type: str
    required: True
  name:
    description:
      - The name of a block device to be created, updated or deleted.
    type: str
    required: True
  new_name:
    description:
      - Updated name of a selected block device.
    type: str
  size_gigabytes:
    description:
      - The size of the block device (in GB).
    type: int
    required: True
  block_size:
    description:
      - The block size of the block device. Defaults to 512.
    type: int
  is_boot_device:
    description:
      - Indicates if the block device is set as the boot device.
    type: bool
  partitions:
    description:
      - List of partition resources created for the new block device.
      - It is computed if it's not given.
    type: list #CHECK
    elements: dict #CHECK
    suboptions:
      size_gigabytes:
        description:
          - The partition size (in GB).
          - If not specified, all available space will be used.
        type: int
      bootable:
        description:
          - Indicates if the partition is set as bootable.
        type: bool
      tags:
        description:
          - The tags assigned to the new block device partition.
        type: str
      fs_type:
        description:
          - The file system type (e.g. ext4).
          - If this is not set, the partition is unformatted.
        type: str
      label:
        description:
          - The label assigned if the partition is formatted.
        type: str
      mount_point:
        description:
          - The mount point used.
          - If this is not set, the partition is not mounted.
          - This is used only if the partition is formatted.
        type: str
      mount_options:
        description:
          - The options used for the partition mount.
        type: str
    model:
      description:
        - Model of the block device.
        - Required together with I(serial).
        - Mutually exclusive with I(id_path).
        - This argument is computed if it's not given.
      type: str
    serial:
      description:
        - Serial number of the block device.
        - Required together with with I(model).
        - Mutually exclusive with I(id_path).
        - This argument is computed if it's not given.
      type: str
    id_path:
      description:
        - Only used if I(model) and I(serial) cannot be provided.
        - This should be a path that is fixed and doesn't change depending on the boot order or kernel version.
        - This argument is computed if it's not given.
      type: path
    tags:
      description:
        - A set of tag names assigned to the new block device.
        - This argument is computed if it's not given.
      type: list
"""

EXAMPLES = r"""
- name: Create and attach block device to machine
  canonical.maas.block_device:
    machine_fqdn: some_machine_name.project
    name: vdb
    state: present
    id_path: /dev/vdb
    size_gigabytes: 27
    tags: "ssd"
    block_size: 512
    is_boot_device: false
    partitions:
      - size_gigabytes: 10
        fs_type: "ext4"
        label: "media"
        mount_point: "/media"
      - size_gigabytes: 15
        fs_type: "ext4"
        mount_point: "/storage"
        bootable: false
        tags: my_partition
    model:
    serial:
    id_path:

- name: Delete block device
  canonical.maas.block_device:
    machine_fqdn: some_machine_name.project
    name: vdb
    state: absent
"""

RETURN = r"""
record:
  description:
    - Created or updated machine's block device.
  returned: success
  type: dict
  sample:
  - firmware_version: null
    system_id: y7388k
    block_size: 102400
    available_size: 1000000000
    model: fakemodel
    serial: 123
    used_size: 0
    tags: []
    partition_table_type: null
    partitions: []
    path: /dev/disk/by-dname/newblockdevice
    size: 1000000000
    id_path: ""
    filesystem: null
    storage_pool: null
    name: newblockdevice
    used_for: Unused
    id: 73
    type: physical
    uuid: null
    resource_uri: /MAAS/api/2.0/nodes/y7388k/blockdevices/73/
"""


from ansible.module_utils.basic import AnsibleModule

from ..module_utils import arguments, errors
from ..module_utils.client import Client
from ..module_utils.machine import Machine
from ..module_utils.state import MachineTaskState
from ..module_utils.partition import Partition
from ..module_utils.block_device import BlockDevice


def data_for_create_block_device(module):
    data = {}
    data["name"] = module.params["name"]  # required
    data["size"] = module.params["size_gigabytes"]  # required
    data["block_size"] = 512  # default
    if module.params["block_size"]:
        data["block_size"] = module.params["block_size"]
    if module.params["model"]:
        data["model"] = module.params["model"]
    if module.params["serial"]:
        data["serial"] = module.params["serial"]
    if module.params["id_path"]:
        data["id_path"] = module.params["id_path"]
    return data


def create_block_device(module, client: Client, machine_id):
    data = data_for_create_block_device(module)
    block_device = BlockDevice.create(client, machine_id, data)
    if module.params["partitions"]:
        create_partition(module, client, machine_id, block_device.id)
    if module.params["tags"]:
        for tag in module.params["tags"]:
            block_device.add_tag(client, tag)
    if module.params["is_boot_device"]:  # if it is true
        block_device.set_boot_disk(client)
    block_device_maas_dict = block_device.get(client)
    return (
        True,
        block_device_maas_dict,
        dict(before={}, after=block_device_maas_dict),
    )


def data_for_create_partition(partition):
    data = {}
    if partition["size_gigabytes"]:
        data["size"] = partition["size_gigabytes"]
    if partition["bootable"]:
        data["bootalbe"] = partition["bootable"]


def create_partition(module, client, machine_id, block_device_id):
    for partition in module.params["partitions"]:
        data = data_for_create_partition(partition)
        new_partition = Partition.create(client, machine_id, block_device_id, data)
        if partition[
            "fs_type"
        ]:  # If this is not set, the partition is unformatted. - CHECK IF IT REALLY NEEDS TO BE UNFOMRATED WHEN CREATING NEW PARTITION
            data = {}
            data["fstype"] = partition["fs_type"]
            if partition["label"]:
                data["label"] = partition["label"]
            new_partition.format(client, data)
            if partition[
                "mount_point"
            ]:  # This is used only if the partition is formatted
                data = {}
                data["mount_point"] = partition["mount_point"]
                if partition["mount_options"]:
                    data["mount_options"] = partition["mount_options"]
                new_partition.mount(client, data)
        if partition["tags"]:
            for tag in partition["tags"]:
                new_partition.add_tag(client, tag)


def data_for_update_block_device(module, block_device, machine, client):
    """
    Machines must have a status of Ready to have access to all options.
    Machines with Deployed status can only have the name, model, serial, and/or id_path updated for a block device.
    This is intented to allow a bad block device to be replaced while the machine remains deployed.
    """
    data = {}
    if module.params["new_name"]:
        if block_device.name != module.params["new_name"]:
            data["name"] = module.params["new_name"]
    if module.params["model"]:
        if block_device.model != module.params["model"]:
            data["model"] = module.params["model"]
    if module.params["serial"]:
        if block_device.serial != module.params["serial"]:
            data["serial"] = module.params["serial"]
    if module.params["id_path"]:
        if block_device.id_path != module.params["id_path"]:
            data["id_path"] = module.params["id_path"]
    if machine.status == MachineTaskState.ready.value:
        if module.params["block_size"]:
            if block_device.block_size != module.params["block_size"]:
                data["block_size"] = module.params["block_size"]
        if module.params["size_gigabytes"]:
            if block_device.size != module.params["size_gigabytes"]:
                data["size"] = module.params["size_gigabytes"]
    return data


def update_block_device(module, client: Client, machine):
    block_device = BlockDevice.get_by_name(
        module,
        client,
        machine.id,
        must_exist=True,
        name_field_ansible="name",
    )
    block_device_maas_dict = block_device.get(client)
    data = data_for_update_block_device(module, machine)
    if data:
        block_device.update(client, data)
    if module.params["tags"]:  # tags can be added but not removed!!
        for tag in module.params["tags"]:
            if tag not in block_device.tags:
                block_device.add_tag(client, tag)
    if module.params["is_boot_device"]:  # if it is true
        block_device.set_boot_disk(client)
    # check if create_partition works if partition are already created on the device
    updated_block_device_maas_dict = block_device.get(client)
    if updated_block_device_maas_dict == block_device_maas_dict:
        return (
            False,
            block_device_maas_dict,
            dict(before=block_device_maas_dict, after=block_device_maas_dict),
        )
    return (
        True,
        updated_block_device_maas_dict,
        dict(before=block_device_maas_dict, after=updated_block_device_maas_dict),
    )


def delete_block_device(module, client: Client, machine_id):
    block_device = BlockDevice.get_by_name(module, client, machine_id)
    if block_device:
        block_device_maas_dict = block_device.get(client)
        block_device.delete(client)
        return True, dict(), dict(before=block_device_maas_dict, after={})
    return False, dict(), dict(before={}, after={})


def run(module, client: Client):
    machine = Machine.get_by_fqdn(
        module, client, must_exist=True, name_field_ansible="machine_fqdn"
    )
    if module.params["state"] == "present":
        block_device = BlockDevice.get_by_name(module, client, machine.id)
        if block_device:
            return update_block_device(module, client, machine)
        else:
            return create_block_device(module, client, machine.id)
    if module.params["state"] == "absent":
        return delete_block_device(module, client, machine.id)


def main():
    module = AnsibleModule(
        supports_check_mode=True,
        argument_spec=dict(
            arguments.get_spec("cluster_instance"),
            state=dict(
                type="str",
                choices=["present", "absent"],
                required=True,
            ),
            machine_fqdn=dict(type="str", required=True),
            name=dict(type="str", required=True),
            new_name=dict(type="str"),
            block_size=dict(type="int"),
            size_gigabytes=dict(type="int"),
            is_boot_device=dict(type="bool"),
            model=dict(type="str"),
            serial=dict(type="str"),
            id_path=dict(type="path"),
            tags=dict(type="list", elements="str"),
            partitions=dict(
                type="list",
                elements="dict",
                options=dict(
                    size_gigabytes=dict(type="int"),
                    bootable=dict(type="bool"),
                    tags=dict(type="list", elements="str"),
                    fs_type=dict(type="str"),
                    label=dict(type="str"),
                    mount_point=dict(type="str"),
                    mount_options=dict(type="str"),
                ),
            ),
        ),
        required_together=[("model", "serial")],
        mutually_exclusive=[("model", "id_path"), ("serial", "id_path")],
    )

    try:
        cluster_instance = module.params["cluster_instance"]
        host = cluster_instance["host"]
        consumer_key = cluster_instance["customer_key"]
        token_key = cluster_instance["token_key"]
        token_secret = cluster_instance["token_secret"]

        client = Client(host, token_key, token_secret, consumer_key)
        changed, record, diff = run(module, client)
        module.exit_json(changed=changed, record=record, diff=diff)
    except errors.MaasError as e:
        module.fail_json(msg=str(e))


if __name__ == "__main__":
    main()
