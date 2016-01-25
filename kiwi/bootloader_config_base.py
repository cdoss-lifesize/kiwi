# Copyright (c) 2015 SUSE Linux GmbH.  All rights reserved.
#
# This file is part of kiwi.
#
# kiwi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# kiwi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with kiwi.  If not, see <http://www.gnu.org/licenses/>
#
# project
from logger import log
from disk_setup import DiskSetup
from path import Path

from exceptions import (
    KiwiBootLoaderTargetError
)


class BootLoaderConfigBase(object):
    """
        base class for bootloader configuration
    """
    def __init__(self, xml_state, root_dir, custom_args=None):
        self.root_dir = root_dir
        self.xml_state = xml_state

        self.post_init(custom_args)

    def post_init(self, custom_args):
        self.custom_args = custom_args

    def write(self):
        """
            write config data to config file. implement in
            specialized bootloader class
        """
        raise NotImplementedError

    def setup_disk_image_config(
        self, uuid, hypervisor, kernel, initrd
    ):
        """
            create boot config file to boot from disk. The boot target
            is identified via the boot filesystem uuid if such a lookup
            is supported by the specialized bootloader implementation
        """
        raise NotImplementedError

    def setup_install_image_config(
        self, mbrid, hypervisor, kernel, initrd
    ):
        """
            create boot config file to boot from install media in EFI mode.
            The boot target is identified via the image identifier(mbrid)
            if such a lookup is supported by the specialized bootloader
            implementation
        """
        raise NotImplementedError

    def setup_live_image_config(
        self, mbrid, hypervisor, kernel, initrd
    ):
        """
            create boot config file to boot live ISO image in EFI mode.
            The boot target is identified via the image identifier(mbrid)
            if such a lookup is supported by the specialized bootloader
            implementation
        """
        raise NotImplementedError

    def setup_disk_boot_images(self, boot_uuid, lookup_path=None):
        """
            some bootloaders requires to build a boot image the bootloader
            can load from a specific offset address or from a standardized
            path on a filesystem. It is the task of the specialized bootloader
            implementation to provide this data
        """
        raise NotImplementedError

    def setup_install_boot_images(self, mbrid, lookup_path=None):
        """
            bootloader images required when booting from an install media
            which is an ISO image
        """
        raise NotImplementedError

    def setup_live_boot_images(self, mbrid, lookup_path=None):
        """
            bootloader images required when booting from a live media
            which is an ISO image
        """
        raise NotImplementedError

    def create_efi_path(self, in_sub_dir='boot/efi'):
        efi_boot_path = self.root_dir + '/' + in_sub_dir + '/EFI/BOOT'
        Path.create(efi_boot_path)
        return efi_boot_path

    def get_boot_theme(self):
        theme = None
        for preferences in self.xml_state.get_preferences_sections():
            section_content = preferences.get_bootloader_theme()
            if section_content:
                theme = section_content[0]
        return theme

    def get_boot_timeout_seconds(self):
        timeout_seconds = self.xml_state.build_type.get_boottimeout()
        if not timeout_seconds:
            timeout_seconds = 10
        return timeout_seconds

    def failsafe_boot_entry_requested(self):
        if self.xml_state.build_type.get_installprovidefailsafe() is False:
            return False
        return True

    def get_hypervisor_domain(self):
        machine = self.xml_state.get_build_type_machine_section()
        if machine:
            return machine.get_domain()

    def get_boot_cmdline(self):
        cmdline = ''
        custom_cmdline = self.xml_state.build_type.get_kernelcmdline()
        if custom_cmdline:
            cmdline += ' ' + custom_cmdline
        custom_root = self.__get_root_cmdline_parameter()
        if custom_root:
            cmdline += ' ' + custom_root
        return cmdline.strip()

    def get_failsafe_boot_cmdline(self):
        cmdline = self.get_boot_cmdline()
        cmdline += ' ' + self.__get_failsafe_kernel_options()
        return cmdline

    def get_install_image_boot_id(self):
        boot_id = 0
        install_boot_name = self.xml_state.build_type.get_installboot()
        if install_boot_name == 'failsafe-install':
            boot_id = 2
        elif install_boot_name == 'install':
            boot_id = 1
        return boot_id

    def get_boot_path(self, target='disk'):
        if target != 'disk' and target != 'iso':
            raise KiwiBootLoaderTargetError(
                'Invalid boot loader target %s' % target
            )
        bootpath = '/boot'
        need_boot_partition = False
        if target == 'disk':
            disk_setup = DiskSetup(self.xml_state, self.root_dir)
            need_boot_partition = disk_setup.need_boot_partition()
            if need_boot_partition:
                # if an extra boot partition is used we will find the
                # data directly in the root of this partition and not
                # below the boot/ directory
                bootpath = '/'

        if target == 'disk':
            if not need_boot_partition:
                filesystem = self.xml_state.build_type.get_filesystem()
                volumes = self.xml_state.get_volumes()
                if filesystem == 'btrfs' and volumes:
                    # if we directly boot a btrfs filesystem with a subvolume
                    # setup and no extra boot partition we have to care for
                    # the layout of the system which places all volumes below
                    # a master volume called: @
                    bootpath = '/@' + bootpath

        return bootpath

    def quote_title(self, name):
        """
            quote characters in the title which causes problems for
            older bootloaders like legacy grub or zipl
        """
        name = name.replace(' ', '_')
        name = name.replace('[', '(')
        name = name.replace(']', ')')
        return name

    def get_menu_entry_title(self, plain=False):
        title = self.xml_state.xml_data.get_displayname()
        if not title:
            title = self.xml_state.xml_data.get_name()
        type_name = self.xml_state.build_type.get_image()
        if plain:
            return title
        return title + ' [ ' + type_name.upper() + ' ]'

    def get_menu_entry_install_title(self):
        title = self.xml_state.xml_data.get_displayname()
        if not title:
            title = self.xml_state.xml_data.get_name()
        return title

    def __get_failsafe_kernel_options(self):
        return ' '.join(
            [
                'ide=nodma',
                'apm=off',
                'noresume',
                'edd=off',
                'powersaved=off',
                'nohz=off',
                'highres=off',
                'processsor.max+cstate=1',
                'nomodeset',
                'x11failsafe'
            ]
        )

    def __get_root_cmdline_parameter(self):
        firmware = self.xml_state.build_type.get_firmware()
        cmdline = self.xml_state.build_type.get_kernelcmdline()
        if 'root=' in cmdline:
            log.info(
                'Kernel root device explicitly set via kernelcmdline'
            )
        elif firmware == 'ec2':
            # EC2 requires to specifiy the root device in the bootloader
            # configuration. EC2 extracts this information via pygrub and
            # use it for the guest configuration which has an impact on
            # the devices attached to the guest. With the current EC2
            # implementation and linux kernel the storage device allways
            # appears as /dev/sda1. Thus this value is set as fixed
            # kernel commandline parameter
            log.info(
                'Kernel root device set to /dev/sda1 for ec2 firmware'
            )
            return 'root=/dev/sda1'
        elif firmware == 'ec2hvm':
            # Similar to the firmware type 'ec2', EC2 needs in case of HVM
            # (hardware-assisted virtual machine) instances the root device
            # to be explicitly set to /dev/hda1.
            #
            # During the first boot, kiwi tries to detect the root device via
            # hwinfo --storage, takes the first entry and creates an initrd
            # and bootlaoder configuration based on this assumption. The
            # problem is, that the first entry refers to /dev/sda1 (the
            # second is /dev/hda1). During the second reboot, /dev/sda will
            # be removed from the system and therefore such an instance
            # won't come up again.
            log.info(
                'Kernel root device set to /dev/hda1 for ec2hvm firmware'
            )
            return 'root=/dev/hda1'
