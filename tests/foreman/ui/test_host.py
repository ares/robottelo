# -*- encoding: utf-8 -*-
"""Test class for Hosts UI

:Requirement: Host

:CaseAutomation: Automated

:CaseLevel: Acceptance

:CaseComponent: UI

:TestType: Functional

:CaseImportance: High

:Upstream: No
"""
from fauxfactory import gen_string
from nailgun import entities, entity_mixins
from robottelo.api.utils import (
    enable_rhrepo_and_fetchid,
    promote,
    upload_manifest,
)
from robottelo import manifests
from robottelo.cli.contentview import ContentView as cli_ContentView
from robottelo.cli.proxy import Proxy as cli_Proxy
from robottelo.config import settings
from robottelo.constants import (
    DEFAULT_CV,
    DEFAULT_PTABLE,
    ENVIRONMENT,
    PRDS,
    REPOS,
    REPOSET,
    RHEL_6_MAJOR_VERSION,
    RHEL_7_MAJOR_VERSION,
)
from robottelo.decorators import (
    run_only_on,
    skip_if_bug_open,
    skip_if_not_set,
    stubbed,
    tier2,
    tier3,
)
from robottelo.decorators.host import skip_if_os
from robottelo.test import UITestCase
from robottelo.ui.locators import locators, tab_locators
from robottelo.ui.factory import make_host, set_context
from robottelo.ui.session import Session

import robottelo.cli.factory as cli_factory


class LibvirtHostTestCase(UITestCase):
    """Implements Libvirt Host tests in UI"""

    hostname = gen_string('numeric')

    @classmethod
    @skip_if_not_set('vlan_networking', 'compute_resources')
    def setUpClass(cls):
        """Steps required to create a real host on libvirt

        1. Creates new Organization and Location.
        2. Creates new life-cycle environment.
        3. Creates new product and rhel67 custom repository.
        4. Creates new content-view by associating rhel67 repository.
        5. Publish and promote the content-view to next environment.
        6. Search for puppet environment and associate location.
        7. Search for smart-proxy and associate location.
        8. Search for existing domain or create new otherwise. Associate org,
           location and dns proxy.
        9. Search for '192.168.100.0' network and associate org, location,
           dns/dhcp/tftp proxy, and if its not there then creates new.
        10. Search for existing compute-resource with 'libvirt' provider and
            associate org.location, and if its not there then creates
            new.
        11. Search 'Kickstart default' partition table and rhel67 OS along with
            provisioning/PXE templates.
        12. Associates org, location and OS with provisioning and PXE templates
        13. Search for x86_64 architecture
        14. Associate arch, partition table, provisioning/PXE templates with OS
        15. Search for media and associate org/location
        16. Create new host group with all required entities
        """
        super(LibvirtHostTestCase, cls).setUpClass()
        # Create a new Organization and Location
        cls.org_ = entities.Organization(name=gen_string('alpha')).create()
        cls.org_name = cls.org_.name
        cls.loc = entities.Location(
            name=gen_string('alpha'),
            organization=[cls.org_]
        ).create()
        cls.loc_name = cls.loc.name

        # Create a new Life-Cycle environment
        cls.lc_env = entities.LifecycleEnvironment(
            name=gen_string('alpha'),
            organization=cls.org_
        ).create()

        # Create a Product, Repository for custom RHEL6 contents
        cls.product = entities.Product(
            name=gen_string('alpha'),
            organization=cls.org_
        ).create()
        cls.repo = entities.Repository(
            name=gen_string('alpha'),
            product=cls.product,
        ).create()

        # Increased timeout value for repo sync
        cls.old_task_timeout = entity_mixins.TASK_TIMEOUT
        entity_mixins.TASK_TIMEOUT = 3600
        cls.repo.sync()

        # Create, Publish and promote CV
        cls.content_view = entities.ContentView(
            name=gen_string('alpha'),
            organization=cls.org_
        ).create()
        cls.content_view.repository = [cls.repo]
        cls.content_view = cls.content_view.update(['repository'])
        cls.content_view.publish()
        cls.content_view = cls.content_view.read()
        promote(cls.content_view.version[0], cls.lc_env.id)
        entity_mixins.TASK_TIMEOUT = cls.old_task_timeout
        # Search for puppet environment and associate location
        cls.environment = entities.Environment(
            organization=[cls.org_.id]).search()[0]
        cls.environment.location = [cls.loc]
        cls.environment = cls.environment.update(['location'])

        # Search for SmartProxy, and associate location
        cls.proxy = entities.SmartProxy().search(
            query={
                u'search': u'name={0}'.format(
                    settings.server.hostname
                )
            }
        )[0]
        cls.proxy.location = [cls.loc]
        cls.proxy = cls.proxy.update(['location'])
        cls.proxy.organization = [cls.org_]
        cls.proxy = cls.proxy.update(['organization'])

        # Search for existing domain or create new otherwise. Associate org,
        # location and dns to it
        _, _, domain = settings.server.hostname.partition('.')
        cls.domain = entities.Domain().search(
            query={
                u'search': u'name="{0}"'.format(domain)
            }
        )
        if len(cls.domain) == 1:
            cls.domain = cls.domain[0].read()
            cls.domain.location.append(cls.loc)
            cls.domain.organization.append(cls.org_)
            cls.domain.dns = cls.proxy
            cls.domain = cls.domain.update(['dns', 'location', 'organization'])
        else:
            cls.domain = entities.Domain(
                dns=cls.proxy,
                location=[cls.loc],
                organization=[cls.org_],
            ).create()
        cls.domain_name = cls.domain.name

        # Search if subnet is defined with given network.
        # If so, just update its relevant fields otherwise,
        # Create new subnet
        network = settings.vlan_networking.subnet
        cls.subnet = entities.Subnet().search(
            query={u'search': u'network={0}'.format(network)}
        )
        if len(cls.subnet) == 1:
            cls.subnet = cls.subnet[0]
            cls.subnet.domain = [cls.domain]
            cls.subnet.location = [cls.loc]
            cls.subnet.organization = [cls.org_]
            cls.subnet.dns = cls.proxy
            cls.subnet.dhcp = cls.proxy
            cls.subnet.ipam = 'DHCP'
            cls.subnet.tftp = cls.proxy
            cls.subnet.discovery = cls.proxy
            cls.subnet = cls.subnet.update([
                'domain',
                'discovery',
                'dhcp',
                'dns',
                'ipam',
                'location',
                'organization',
                'tftp',
            ])
        else:
            # Create new subnet
            cls.subnet = entities.Subnet(
                name=gen_string('alpha'),
                network=network,
                mask=settings.vlan_networking.netmask,
                domain=[cls.domain],
                ipam='DHCP',
                location=[cls.loc],
                organization=[cls.org_],
                dns=cls.proxy,
                dhcp=cls.proxy,
                tftp=cls.proxy,
                discovery=cls.proxy
            ).create()

        # Search if Libvirt compute-resource already exists
        # If so, just update its relevant fields otherwise,
        # Create new compute-resource with 'libvirt' provider.
        resource_url = u'qemu+ssh://root@{0}/system'.format(
            settings.compute_resources.libvirt_hostname
        )
        comp_res = [
            res for res in entities.LibvirtComputeResource().search()
            if res.provider == 'Libvirt' and res.url == resource_url
        ]
        if len(comp_res) >= 1:
            cls.computeresource = entities.LibvirtComputeResource(
                id=comp_res[0].id).read()
            cls.computeresource.location.append(cls.loc)
            cls.computeresource.organization.append(cls.org_)
            cls.computeresource = cls.computeresource.update([
                'location', 'organization'])
        else:
            # Create Libvirt compute-resource
            cls.computeresource = entities.LibvirtComputeResource(
                name=gen_string('alpha'),
                provider=u'libvirt',
                url=resource_url,
                set_console_password=False,
                display_type=u'VNC',
                location=[cls.loc.id],
                organization=[cls.org_.id],
            ).create()

        # Get the Partition table ID
        cls.ptable = entities.PartitionTable().search(
            query={
                u'search': u'name="{0}"'.format(DEFAULT_PTABLE)
            }
        )[0]

        # Get the OS ID
        cls.os = entities.OperatingSystem().search(query={
            u'search': u'name="RedHat" AND (major="{0}" OR major="{1}")'
                       .format(RHEL_6_MAJOR_VERSION, RHEL_7_MAJOR_VERSION)
        })[0]

        # Get the Provisioning template_ID and update with OS, Org, Location
        cls.provisioning_template = entities.ConfigTemplate().search(
            query={
                u'search': u'name="Satellite Kickstart Default"'
            }
        )[0]
        cls.provisioning_template.operatingsystem = [cls.os]
        cls.provisioning_template.organization = [cls.org_]
        cls.provisioning_template.location = [cls.loc]
        cls.provisioning_template = cls.provisioning_template.update([
            'location',
            'operatingsystem',
            'organization'
        ])

        # Get the PXE template ID and update with OS, Org, location
        cls.pxe_template = entities.ConfigTemplate().search(
            query={
                u'search': u'name="Kickstart default PXELinux"'
            }
        )[0]
        cls.pxe_template.operatingsystem = [cls.os]
        cls.pxe_template.organization = [cls.org_]
        cls.pxe_template.location = [cls.loc]
        cls.pxe_template = cls.pxe_template.update(
            ['location', 'operatingsystem', 'organization']
        )

        # Get the arch ID
        cls.arch = entities.Architecture().search(
            query={u'search': u'name="x86_64"'}
        )[0]

        # Get the media and update its location
        cls.media = entities.Media(organization=[cls.org_]).search()[0].read()
        cls.media.location.append(cls.loc)
        cls.media.organization.append(cls.org_)
        cls.media = cls.media.update(['location', 'organization'])
        # Update the OS to associate arch, ptable, templates
        cls.os.architecture = [cls.arch]
        cls.os.ptable = [cls.ptable]
        cls.os.config_template = [cls.provisioning_template]
        cls.os.config_template = [cls.pxe_template]
        cls.os.medium = [cls.media]
        cls.os = cls.os.update([
            'architecture',
            'config_template',
            'ptable',
            'medium',
        ])

        # Create Hostgroup
        cls.host_group = entities.HostGroup(
            architecture=cls.arch,
            domain=cls.domain.id,
            subnet=cls.subnet.id,
            lifecycle_environment=cls.lc_env.id,
            content_view=cls.content_view.id,
            location=[cls.loc.id],
            name=gen_string('alpha'),
            environment=cls.environment.id,
            puppet_proxy=cls.proxy,
            puppet_ca_proxy=cls.proxy,
            content_source=cls.proxy,
            medium=cls.media,
            operatingsystem=cls.os.id,
            organization=[cls.org_.id],
            ptable=cls.ptable.id,
        ).create()

    def tearDown(self):
        """Delete the host to free the resources"""
        with Session(self) as session:
            session.nav.go_to_select_org(self.org_name)
            host_name = u'{0}.{1}'.format(self.hostname, self.domain_name)
            if self.hosts.search(host_name):
                self.hosts.delete(host_name, dropdown_present=True)
        super(LibvirtHostTestCase, self).tearDown()

    @run_only_on('sat')
    @tier3
    def test_positive_create_libvirt(self):
        """Create a new Host on libvirt compute resource

        :id: 2678f95f-0c0e-4b46-a3c1-3f9a954d3bde

        :expectedresults: Host is created

        :CaseLevel: System
        """
        resource = u'{0} (Libvirt)'.format(self.computeresource.name)
        root_pwd = gen_string('alpha', 15)
        environment = entities.Environment(
            location=[self.loc],
            organization=[self.org_],
        ).create(True)
        with Session(self) as session:
            make_host(
                session,
                name=self.hostname,
                org=self.org_name,
                parameters_list=[
                    ['Host', 'Organization', self.org_name],
                    ['Host', 'Location', self.loc_name],
                    ['Host', 'Host group', self.host_group.name],
                    ['Host', 'Deploy on', resource],
                    ['Host', 'Puppet Environment', environment.name],
                    ['Virtual Machine', 'Memory', '1 GB'],
                    ['Operating System', 'Media', self.media.name],
                    ['Operating System', 'Partition table', DEFAULT_PTABLE],
                    ['Operating System', 'Root password', root_pwd],
                ],
                interface_parameters=[
                    ['Network type', 'Physical (Bridge)'],
                    ['Network', settings.vlan_networking.bridge],
                ],
            )
            search = self.hosts.search(
                u'{0}.{1}'.format(self.hostname, self.domain_name)
            )
            self.assertIsNotNone(search)


class HostTestCase(UITestCase):
    """Implements Host tests in UI"""

    @run_only_on('sat')
    @stubbed
    @tier3
    def test_positive_create_baremetal_with_bios(self):
        """Create a new Host from provided MAC address

        :id: 2cedc634-7761-4326-b77a-b999098f5c00

        :setup: Create a PXE-based VM with BIOS boot mode (outside of
            Satellite).

        :steps: Create a new host using 'BareMetal' option and MAC address of
            the pre-created VM

        :expectedresults: Host is created

        :caseautomation: notautomated

        :caselevel: System
        """

    @run_only_on('sat')
    @stubbed
    @tier3
    def test_positive_create_baremetal_with_uefi(self):
        """Create a new Host from provided MAC address

        :id: ec62e90b-1b2a-4eac-8b15-7e36c8179086

        :setup: Create a PXE-based VM with UEFI boot mode (outside of
            Satellite).

        :steps: Create a new host using 'BareMetal' option and MAC address of
            the pre-created VM

        :expectedresults: Host is created

        :caseautomation: notautomated

        :caselevel: System
        """

    @run_only_on('sat')
    @stubbed
    @tier3
    def test_positive_verify_files_with_pxegrub_uefi(self):
        """Provision a new Host and verify the tftp and dhcpd file
        structure is correct

        :id: e3dd2334-6e82-4272-a099-6f4214b77151

        :steps:

            1. Associate a pxegrub-type provisioning template with the os
            2. Create new host (can be fictive bare metal) with the above OS
                and PXE loader set to Grub UEFI
            3. Build the host

        :expectedresults: Verify [/var/lib/tftpboot/] contains the following
            dir/file structure:

                grub/bootia32.efi
                grub/bootx64.efi
                grub/01-AA-BB-CC-DD-EE-FF
                grub/efidefault
                grub/shim.efi

            And record in /var/lib/dhcpd/dhcpd.leases points to the bootloader

        :caseautomation: notautomated

        :caselevel: System
        """

    @run_only_on('sat')
    @stubbed
    @tier3
    def test_positive_verify_files_with_pxegrub_uefi_secureboot(self):
        """Provision a new Host and verify the tftp and dhcpd file
        structure is correct

        :id: fc97dfcc-15d0-4eab-a778-fa1bcf82be22

        :steps:

            1. Associate a pxegrub-type provisioning template with the os
            2. Create new host (can be fictive bare metal) with the above OS
                and PXE loader set to Grub UEFI SecureBoot
            3. Build the host

        :expectedresults: Verify [/var/lib/tftpboot/] contains the following
            dir/file structure:

                grub/bootia32.efi
                grub/bootx64.efi
                grub/01-AA-BB-CC-DD-EE-FF
                grub/efidefault
                grub/shim.efi

            And record in /var/lib/dhcpd/dhcpd.leases points to the bootloader

        :caseautomation: notautomated

        :caselevel: System
        """

    @run_only_on('sat')
    @stubbed
    @tier3
    def test_positive_verify_files_with_pxegrub2_uefi(self):
        """Provision a new UEFI Host and verify the and dhcpd file
        structure is correct

        :id: eec31881-eb20-4fb3-8d19-e3a4012ba4a0

        :steps:

            1. Associate a pxegrub-type provisioning template with the os
            2. Create new host (can be fictive bare metal) with the above OS
                and PXE loader set to Grub2 UEFI
            3. Build the host

        :expectedresults: Verify [/var/lib/tftpboot/] contains the following
            dir/file structure:

                pxegrub2
                grub2/grub.cfg-01-aa-bb-cc-dd-ee-ff
                grub2/grub.cfg
                grub2/grubx32.efi
                grub2/grubx64.efi
                grub/shim.efi

            And record in /var/lib/dhcpd/dhcpd.leases points to the bootloader

        :caseautomation: notautomated

        :caselevel: System
        """

    @run_only_on('sat')
    @stubbed
    @tier3
    def test_positive_verify_files_with_pxegrub2_uefi_secureboot(self):
        """Provision a new UEFI Host and verify the tftp and dhcpd file
        structure is correct

        :id: fdbb3617-74f2-46c4-930f-028dd4edcf9e

        :steps:

            1. Associate a pxegrub-type provisioning template with the os
            2. Create new host (can be fictive bare metal) with the above OS
                and PXE loader set to Grub2 UEFI SecureBoot
            3. Build the host

        :expectedresults: Verify [/var/lib/tftpboot/] contains the following
            dir/file structure:

                pxegrub2
                grub2/grub.cfg-01-aa-bb-cc-dd-ee-ff
                grub2/grub.cfg
                grub2/grubx32.efi
                grub2/grubx64.efi
                grub/shim.efi

            And record in /var/lib/dhcpd/dhcpd.leases points to the bootloader

        :caseautomation: notautomated

        :caselevel: System
        """

    @run_only_on('sat')
    @tier3
    def test_positive_create(self):
        """Create a new Host

        :id: 4821444d-3c86-4f93-849b-60460e025ba0

        :expectedresults: Host is created

        :CaseLevel: System
        """
        host = entities.Host()
        host.create_missing()
        os_name = u'{0} {1}'.format(
            host.operatingsystem.name, host.operatingsystem.major)
        with Session(self) as session:
            make_host(
                session,
                name=host.name,
                org=host.organization.name,
                parameters_list=[
                    ['Host', 'Organization', host.organization.name],
                    ['Host', 'Location', host.location.name],
                    ['Host', 'Lifecycle Environment', ENVIRONMENT],
                    ['Host', 'Content View', DEFAULT_CV],
                    ['Host', 'Puppet Environment', host.environment.name],
                    [
                        'Operating System',
                        'Architecture',
                        host.architecture.name
                    ],
                    ['Operating System', 'Operating system', os_name],
                    ['Operating System', 'Media', host.medium.name],
                    ['Operating System', 'Partition table', host.ptable.name],
                    ['Operating System', 'Root password', host.root_pass],
                ],
                interface_parameters=[
                    ['Type', 'Interface'],
                    ['MAC address', host.mac],
                    ['Domain', host.domain.name],
                    ['Primary', True],
                ],
            )
            # confirm the Host appears in the UI
            search = self.hosts.search(
                u'{0}.{1}'.format(host.name, host.domain.name)
            )
            self.assertIsNotNone(search)

    @run_only_on('sat')
    @tier3
    def test_negative_delete_primary_interface(self):
        """Attempt to delete primary interface of a host

        :id: bc747e2c-38d9-4920-b4ae-6010851f704e

        :BZ: 1417119

        :expectedresults: Interface was not deleted

        :CaseLevel: System
        """
        host = entities.Host()
        host.create_missing()
        os_name = u'{0} {1}'.format(
            host.operatingsystem.name, host.operatingsystem.major)
        interface_id = gen_string('alpha')
        with Session(self) as session:
            make_host(
                session,
                name=host.name,
                org=host.organization.name,
                parameters_list=[
                    ['Host', 'Organization', host.organization.name],
                    ['Host', 'Location', host.location.name],
                    ['Host', 'Lifecycle Environment', ENVIRONMENT],
                    ['Host', 'Content View', DEFAULT_CV],
                    ['Host', 'Puppet Environment', host.environment.name],
                    [
                        'Operating System',
                        'Architecture',
                        host.architecture.name
                    ],
                    ['Operating System', 'Operating system', os_name],
                    ['Operating System', 'Media', host.medium.name],
                    ['Operating System', 'Partition table', host.ptable.name],
                    ['Operating System', 'Root password', host.root_pass],
                ],
                interface_parameters=[
                    ['Type', 'Interface'],
                    ['Device Identifier', interface_id],
                    ['MAC address', host.mac],
                    ['Domain', host.domain.name],
                    ['Primary', True],
                ],
            )
            host_el = self.hosts.search(
                u'{0}.{1}'.format(host.name, host.domain.name)
            )
            self.assertIsNotNone(host_el)
            self.hosts.click(host_el)
            self.hosts.click(locators['host.edit'])
            self.hosts.click(tab_locators['host.tab_interfaces'])
            delete_button = self.hosts.wait_until_element(
                locators['host.delete_interface'] % interface_id)
            # Verify the button is disabled
            self.assertFalse(delete_button.is_enabled())
            self.assertEqual(delete_button.get_attribute('disabled'), 'true')
            # Attempt to delete the interface
            self.hosts.delete_interface(
                host.name, host.domain.name, interface_id)
            # Verify interface wasn't deleted by fetching one of its parameters
            # (e.g., MAC address)
            results = self.hosts.fetch_host_parameters(
                host.name,
                host.domain.name,
                [['Interfaces', 'Primary Interface MAC']],
            )
            self.assertEqual(results['Primary Interface MAC'], host.mac)

    @run_only_on('sat')
    @tier3
    def test_positive_update_name(self):
        """Create a new Host and update its name to valid one

        :id: f1c19599-f613-431d-bf09-62addec1e60b

        :expectedresults: Host is updated successfully

        :CaseLevel: System
        """
        host = entities.Host()
        host.create_missing()
        os_name = u'{0} {1}'.format(
            host.operatingsystem.name, host.operatingsystem.major)
        host_name = host.name
        with Session(self) as session:
            make_host(
                session,
                name=host_name,
                org=host.organization.name,
                parameters_list=[
                    ['Host', 'Organization', host.organization.name],
                    ['Host', 'Location', host.location.name],
                    ['Host', 'Lifecycle Environment', ENVIRONMENT],
                    ['Host', 'Content View', DEFAULT_CV],
                    ['Host', 'Puppet Environment', host.environment.name],
                    [
                        'Operating System',
                        'Architecture',
                        host.architecture.name],
                    ['Operating System', 'Operating system', os_name],
                    ['Operating System', 'Media', host.medium.name],
                    ['Operating System', 'Partition table', host.ptable.name],
                    ['Operating System', 'Root password', host.root_pass],
                ],
                interface_parameters=[
                    ['Type', 'Interface'],
                    ['MAC address', host.mac],
                    ['Domain', host.domain.name],
                    ['Primary', True],
                ],
            )
            # confirm the Host appears in the UI
            search = self.hosts.search(
                u'{0}.{1}'.format(host_name, host.domain.name)
            )
            self.assertIsNotNone(search)
            new_name = gen_string('alpha')
            self.hosts.update(host_name, host.domain.name, new_name)
            new_host_name = (
                u'{0}.{1}'.format(new_name, host.domain.name)).lower()
            self.assertIsNotNone(self.hosts.search(new_host_name))
            self.hostname = new_name

    @run_only_on('sat')
    @tier3
    def test_positive_update_name_with_prefix(self):
        """Create a new Host and update its name to valid one. Host should
        contain word 'new' in its name

        :id: b08cb5c9-bd2c-4dc7-97b1-d1f20d1373d7

        :expectedresults: Host is updated successfully

        :BZ: 1419161

        :CaseLevel: System
        """
        current_name = 'new{0}'.format(gen_string('alpha'), 6).lower()
        new_name = 'new{0}'.format(gen_string('alpha')).lower()
        host = entities.Host(name=current_name)
        host.create_missing()
        os_name = u'{0} {1}'.format(
            host.operatingsystem.name, host.operatingsystem.major)
        with Session(self) as session:
            make_host(
                session,
                name=current_name,
                org=host.organization.name,
                parameters_list=[
                    ['Host', 'Organization', host.organization.name],
                    ['Host', 'Location', host.location.name],
                    ['Host', 'Lifecycle Environment', ENVIRONMENT],
                    ['Host', 'Content View', DEFAULT_CV],
                    ['Host', 'Puppet Environment', host.environment.name],
                    [
                        'Operating System',
                        'Architecture',
                        host.architecture.name],
                    ['Operating System', 'Operating system', os_name],
                    ['Operating System', 'Media', host.medium.name],
                    ['Operating System', 'Partition table', host.ptable.name],
                    ['Operating System', 'Root password', host.root_pass],
                ],
                interface_parameters=[
                    ['Type', 'Interface'],
                    ['MAC address', host.mac],
                    ['Domain', host.domain.name],
                    ['Primary', True],
                ],
            )
            # confirm the Host appears in the UI
            search = self.hosts.search(
                u'{0}.{1}'.format(current_name, host.domain.name)
            )
            self.assertIsNotNone(search)
            self.hosts.update(current_name, host.domain.name, new_name)
            new_host_name = (
                u'{0}.{1}'.format(new_name, host.domain.name)).lower()
            self.assertIsNotNone(self.hosts.search(new_host_name))

    @run_only_on('sat')
    @tier3
    def test_positive_delete(self):
        """Delete a Host

        :id: 13735af1-f1c7-466e-a969-80618a1d854d

        :expectedresults: Host is delete

        :CaseLevel: System
        """
        host = entities.Host()
        host.create_missing()
        os_name = u'{0} {1}'.format(
            host.operatingsystem.name, host.operatingsystem.major)
        with Session(self) as session:
            make_host(
                session,
                name=host.name,
                org=host.organization.name,
                parameters_list=[
                    ['Host', 'Organization', host.organization.name],
                    ['Host', 'Location', host.location.name],
                    ['Host', 'Lifecycle Environment', ENVIRONMENT],
                    ['Host', 'Content View', DEFAULT_CV],
                    ['Host', 'Puppet Environment', host.environment.name],
                    [
                        'Operating System',
                        'Architecture',
                        host.architecture.name
                    ],
                    ['Operating System', 'Operating system', os_name],
                    ['Operating System', 'Media', host.medium.name],
                    ['Operating System', 'Partition table', host.ptable.name],
                    ['Operating System', 'Root password', host.root_pass],
                ],
                interface_parameters=[
                    ['Type', 'Interface'],
                    ['MAC address', host.mac],
                    ['Domain', host.domain.name],
                    ['Primary', True],
                ],
            )
            # Delete host
            self.hosts.delete(
                u'{0}.{1}'.format(host.name, host.domain.name),
                dropdown_present=True
            )

    @run_only_on('sat')
    @tier2
    def test_positive_search_by_parameter(self):
        """Search for the host by global parameter assigned to it

        :id: 8e61127c-d0a0-4a46-a3c6-22d3b2c5457c

        :expectedresults: Only one specific host is returned by search

        :CaseLevel: Integration
        """
        org = entities.Organization().create()
        param_name = gen_string('alpha')
        param_value = gen_string('alpha')
        parameters = [{'name': param_name, 'value': param_value}]
        param_host = entities.Host(
            organization=org,
            host_parameters_attributes=parameters,
        ).create()
        additional_host = entities.Host(organization=org).create()
        with Session(self) as session:
            set_context(session, org=org.name)
            # Check that hosts present in the system
            for host in [param_host, additional_host]:
                self.assertIsNotNone(self.hosts.search(host.name))
            # Check that search by parameter returns only one host in the list
            self.assertIsNotNone(
                self.hosts.search(
                    param_host.name,
                    _raw_query='params.{0} = {1}'.format(
                        param_name, param_value)
                )
            )
            strategy, value = locators['host.select_name']
            self.assertIsNone(self.hosts.wait_until_element(
                (strategy, value % additional_host.name)))

    @run_only_on('sat')
    @tier2
    def test_positive_search_by_parameter_with_different_values(self):
        """Search for the host by global parameter assigned to it by its value

        :id: c3a4551e-d759-4a9d-ba90-8db4cab3db2c

        :expectedresults: Only one specific host is returned by search

        :CaseLevel: Integration
        """
        org = entities.Organization().create()
        name = gen_string('alpha')
        param_values = [gen_string('alpha'), gen_string('alphanumeric')]
        hosts = [
            entities.Host(
                organization=org,
                host_parameters_attributes=[{'name': name, 'value': value}]
            ).create()
            for value in param_values
        ]
        with Session(self) as session:
            set_context(session, org=org.name)
            # Check that hosts present in the system
            for host in hosts:
                self.assertIsNotNone(self.hosts.search(host.name))
            # Check that search by parameter returns only one host in the list
            strategy, value = locators['host.select_name']
            for i in range(2):
                self.assertIsNotNone(
                    self.hosts.search(
                        hosts[i].name,
                        _raw_query='params.{0} = {1}'.format(
                            name, param_values[i])
                    )
                )
                self.assertIsNone(self.hosts.wait_until_element(
                    (strategy, value % hosts[-i-1])))

    @run_only_on('sat')
    @tier2
    def test_positive_search_by_parameter_with_prefix(self):
        """Search by global parameter assigned to host using prefix 'not' and
        any random string as parameter value to make sure that all hosts will
        be present in the list

        :id: a4affb90-1222-4d9a-94be-213f9e5be573

        :expectedresults: All assigned hosts to organization are returned by
            search

        :CaseLevel: Integration
        """
        org = entities.Organization().create()
        param_name = gen_string('alpha')
        param_value = gen_string('alpha')
        parameters = [{'name': param_name, 'value': param_value}]
        param_host = entities.Host(
            organization=org,
            host_parameters_attributes=parameters,
        ).create()
        additional_host = entities.Host(organization=org).create()
        with Session(self) as session:
            set_context(session, org=org.name)
            # Check that hosts present in the system
            for host in [param_host, additional_host]:
                self.assertIsNotNone(self.hosts.search(host.name))
            # Check that search by parameter with 'not' prefix returns both
            # hosts in the list
            self.assertIsNotNone(
                self.hosts.search(
                    param_host.name,
                    _raw_query='not params.{0} = {1}'.format(
                        param_name, gen_string('alphanumeric'))
                )
            )
            strategy, value = locators['host.select_name']
            self.assertIsNotNone(self.hosts.wait_until_element(
                (strategy, value % additional_host.name)))

    @run_only_on('sat')
    @skip_if_bug_open('bugzilla', 1392422)
    @tier2
    def test_positive_search_by_parameter_with_operator(self):
        """Search by global parameter assigned to host using operator '<>' and
        any random string as parameter value to make sure that all hosts will
        be present in the list

        :id: 264065b7-0d04-467d-887a-0aba0d871b7c

        :expectedresults: All assigned hosts to organization are returned by
            search

        :BZ: 1392422

        :CaseLevel: Integration
        """
        org = entities.Organization().create()
        param_name = gen_string('alpha')
        param_value = gen_string('alpha')
        parameters = [{'name': param_name, 'value': param_value}]
        param_host = entities.Host(
            organization=org,
            host_parameters_attributes=parameters,
        ).create()
        additional_host = entities.Host(organization=org).create()
        with Session(self) as session:
            set_context(session, org=org.name)
            # Check that hosts present in the system
            for host in [param_host, additional_host]:
                self.assertIsNotNone(self.hosts.search(host.name))
            # Check that search by parameter with '<>' operator returns both
            # hosts in the list
            self.assertIsNotNone(
                self.hosts.search(
                    param_host.name,
                    _raw_query='params.{0} <> {1}'.format(
                        param_name, gen_string('alphanumeric'))
                )
            )
            strategy, value = locators['host.select_name']
            self.assertIsNotNone(self.hosts.wait_until_element(
                (strategy, value % additional_host.name)))

    @run_only_on('sat')
    @tier2
    def test_positive_search_with_org_and_loc_context(self):
        """Perform usual search for host, but organization and location used
        for host create procedure should have 'All capsules' checkbox selected

        :id: 2ce50df0-2b30-42cc-a40b-0e1f4fde3c6f

        :expectedresults: Search functionality works as expected and correct
            result is returned

        :BZ: 1405496

        :CaseLevel: Integration
        """
        org = entities.Organization().create()
        loc = entities.Location().create()
        host = entities.Host(organization=org, location=loc).create()
        with Session(self) as session:
            self.org.update(org.name, all_capsules=True)
            self.location.update(loc.name, all_capsules=True)
            set_context(session, org=org.name, loc=loc.name)
            # Check that host present in the system
            self.assertIsNotNone(self.hosts.search(host.name))
            self.assertIsNotNone(
                self.hosts.search(host.name, _raw_query=host.name))

    @tier2
    def test_positive_validate_inherited_cv_lce(self):
        """Create a host with hostgroup specified via CLI. Make sure host
        inherited hostgroup's lifecycle environment, content view and both
        fields are properly reflected via WebUI

        :id: c83f6819-2649-4a8b-bb1d-ce93b2243765

        :expectedresults: Host's lifecycle environment and content view match
            the ones specified in hostgroup

        :CaseLevel: Integration

        :BZ: 1391656
        """
        host = entities.Host()
        host.create_missing()

        new_lce = cli_factory.make_lifecycle_environment({
            'organization-id': host.organization.id})
        new_cv = cli_factory.make_content_view({
            'organization-id': host.organization.id})
        cli_ContentView.publish({'id': new_cv['id']})
        version_id = cli_ContentView.version_list({
            'content-view-id': new_cv['id'],
        })[0]['id']
        cli_ContentView.version_promote({
            'id': version_id,
            'to-lifecycle-environment-id': new_lce['id'],
            'organization-id': host.organization.id,
        })
        hostgroup = cli_factory.make_hostgroup({
            'content-view-id': new_cv['id'],
            'lifecycle-environment-id': new_lce['id'],
            'organization-ids': host.organization.id,
        })
        puppet_proxy = cli_Proxy.list({
            'search': 'url = https://{0}:9090'.format(settings.server.hostname)
        })[0]

        cli_factory.make_host({
            'architecture-id': host.architecture.id,
            'domain-id': host.domain.id,
            'environment-id': host.environment.id,
            'hostgroup-id': hostgroup['id'],
            'location-id': host.location.id,
            'medium-id': host.medium.id,
            'name': host.name,
            'operatingsystem-id': host.operatingsystem.id,
            'organization-id': host.organization.id,
            'partition-table-id': host.ptable.id,
            'puppet-proxy-id': puppet_proxy['id'],
        })
        with Session(self) as session:
            set_context(session, host.organization.name, host.location.name)
            result = self.hosts.fetch_host_parameters(
                host.name,
                host.domain.name,
                [['Host', 'Lifecycle Environment'],
                 ['Host', 'Content View']],
            )
            self.assertEqual(result['Lifecycle Environment'], new_lce['name'])
            self.assertEqual(result['Content View'], new_cv['name'])

    @stubbed()
    @tier3
    def test_positive_create_with_user(self):
        """Create Host with new user specified

        :id: b97d6fe5-b0a1-4ddc-8d7f-cbf7b17c823d

        :expectedresults: Host is created

        :caseautomation: notautomated

        :CaseLevel: System
        """

    @stubbed()
    @tier3
    def test_positive_update_with_user(self):
        """Update Host with new user specified

        :id: 4c030cf5-b89c-4dec-bb3e-0cb3215a2315

        :expectedresults: Host is updated

        :caseautomation: notautomated

        :CaseLevel: System
        """


class AtomicHostTestCase(UITestCase):
    """Implements Atomic Host tests in UI"""

    hostname = gen_string('numeric')

    @classmethod
    @skip_if_bug_open('bugzilla', 1414134)
    @skip_if_os('RHEL6')
    @skip_if_not_set('vlan_networking', 'compute_resources', 'ostree')
    def setUpClass(cls):
        """Steps required to create a Atomic host on libvirt

        1. Creates new Organization and Location.
        2. Creates new life-cycle environment.
        3. Creates new product and sync RH Atomic OSTree repository.
        4. Creates new content-view by associating RH Atomic repository.
        5. Publish and promote the content-view to next environment.
        6. Search for smart-proxy and associate location.
        7. Search for existing domain or create new otherwise. Associate org,
           location and dns proxy.
        8. Search for '192.168.100.0' network and associate org, location,
           dns/dhcp/tftp proxy, and if its not there then creates new.
        9. Search for existing compute-resource with 'libvirt' provider and
            associate org.location, and if its not there then creates
            new.
        10. Search 'Kickstart default' partition table and RH Atomic OS along
            with PXE templates.
        11. Associates org, location and OS with provisioning and PXE templates
        12. Search for x86_64 architecture
        13. Associate arch, partition table, provisioning/PXE templates with OS
        14. Search for existing Atomic media or create new otherwise and
            associate org/location
        15. Create new host group with all required entities
        """
        super(AtomicHostTestCase, cls).setUpClass()
        # Create a new Organization and Location
        cls.org = entities.Organization().create()
        cls.org_name = cls.org.name
        cls.loc = entities.Location(organization=[cls.org]).create()
        cls.loc_name = cls.loc.name
        # Create a new Life-Cycle environment
        cls.lc_env = entities.LifecycleEnvironment(
            organization=cls.org
        ).create()
        cls.rh_ah_repo = {
            'name': REPOS['rhaht']['name'],
            'product': PRDS['rhah'],
            'reposet': REPOSET['rhaht'],
            'basearch': None,
            'releasever': None,
        }
        with manifests.clone() as manifest:
            upload_manifest(cls.org.id, manifest.content)
        # Enables the RedHat repo and fetches it's Id.
        cls.repo_id = enable_rhrepo_and_fetchid(
            basearch=cls.rh_ah_repo['basearch'],
            # OrgId is passed as data in API hence str
            org_id=str(cls.org.id),
            product=cls.rh_ah_repo['product'],
            repo=cls.rh_ah_repo['name'],
            reposet=cls.rh_ah_repo['reposet'],
            releasever=cls.rh_ah_repo['releasever'],
        )
        # Increased timeout value for repo sync
        cls.old_task_timeout = entity_mixins.TASK_TIMEOUT
        entity_mixins.TASK_TIMEOUT = 600
        # Sync repository
        entities.Repository(id=cls.repo_id).sync()
        entity_mixins.TASK_TIMEOUT = cls.old_task_timeout
        cls.cv = entities.ContentView(organization=cls.org).create()
        cls.cv.repository = [entities.Repository(id=cls.repo_id)]
        cls.cv = cls.cv.update(['repository'])
        cls.cv.publish()
        cls.cv = cls.cv.read()
        promote(cls.cv.version[0], cls.lc_env.id)
        # Search for SmartProxy, and associate location
        cls.proxy = entities.SmartProxy().search(
            query={
                u'search': u'name={0}'.format(
                    settings.server.hostname
                )
            }
        )[0]
        cls.proxy.location = [cls.loc]
        cls.proxy.organization = [cls.org]
        cls.proxy = cls.proxy.update(['organization', 'location'])

        # Search for existing domain or create new otherwise. Associate org,
        # location and dns to it
        _, _, domain = settings.server.hostname.partition('.')
        cls.domain = entities.Domain().search(
            query={
                u'search': u'name="{0}"'.format(domain)
            }
        )
        if len(cls.domain) == 1:
            cls.domain = cls.domain[0].read()
            cls.domain.location.append(cls.loc)
            cls.domain.organization.append(cls.org)
            cls.domain.dns = cls.proxy
            cls.domain = cls.domain.update(['dns', 'location', 'organization'])
        else:
            cls.domain = entities.Domain(
                dns=cls.proxy,
                location=[cls.loc],
                organization=[cls.org],
            ).create()
        cls.domain_name = cls.domain.name

        # Search if subnet is defined with given network.
        # If so, just update its relevant fields otherwise,
        # Create new subnet
        network = settings.vlan_networking.subnet
        cls.subnet = entities.Subnet().search(
            query={u'search': u'network={0}'.format(network)}
        )
        if len(cls.subnet) == 1:
            cls.subnet = cls.subnet[0]
            cls.subnet.domain = [cls.domain]
            cls.subnet.location = [cls.loc]
            cls.subnet.organization = [cls.org]
            cls.subnet.dns = cls.proxy
            cls.subnet.dhcp = cls.proxy
            cls.subnet.tftp = cls.proxy
            cls.subnet.discovery = cls.proxy
            cls.subnet = cls.subnet.update([
                'domain',
                'discovery',
                'dhcp',
                'dns',
                'location',
                'organization',
                'tftp',
            ])
        else:
            # Create new subnet
            cls.subnet = entities.Subnet(
                name=gen_string('alpha'),
                network=network,
                mask=settings.vlan_networking.netmask,
                domain=[cls.domain],
                location=[cls.loc],
                organization=[cls.org],
                dns=cls.proxy,
                dhcp=cls.proxy,
                tftp=cls.proxy,
                discovery=cls.proxy
            ).create()

        # Search if Libvirt compute-resource already exists
        # If so, just update its relevant fields otherwise,
        # Create new compute-resource with 'libvirt' provider.
        resource_url = u'qemu+ssh://root@{0}/system'.format(
            settings.compute_resources.libvirt_hostname
        )
        comp_res = [
            res for res in entities.LibvirtComputeResource().search()
            if res.provider == 'Libvirt' and res.url == resource_url
        ]
        if len(comp_res) >= 1:
            cls.computeresource = entities.LibvirtComputeResource(
                id=comp_res[0].id).read()
            cls.computeresource.location.append(cls.loc)
            cls.computeresource.organization.append(cls.org)
            cls.computeresource = cls.computeresource.update([
                'location', 'organization'])
        else:
            # Create Libvirt compute-resource
            cls.computeresource = entities.LibvirtComputeResource(
                name=gen_string('alpha'),
                provider=u'libvirt',
                url=resource_url,
                set_console_password=False,
                display_type=u'VNC',
                location=[cls.loc.id],
                organization=[cls.org.id],
            ).create()

        # Get the Partition table ID
        cls.ptable = entities.PartitionTable().search(
            query={
                u'search': u'name="{0}"'.format(DEFAULT_PTABLE)
            }
        )[0]

        # Get the OS ID
        cls.os = entities.OperatingSystem().search(query={
            u'search': u'name="RedHat_Enterprise_Linux_Atomic_Host"'
        })[0]

        # Get the Provisioning template_ID and update with OS, Org, Location
        cls.provisioning_template = entities.ConfigTemplate().search(
            query={
                u'search': u'name="Satellite Atomic Kickstart Default"'
            }
        )[0]
        cls.provisioning_template.operatingsystem = [cls.os]
        cls.provisioning_template.organization = [cls.org]
        cls.provisioning_template.location = [cls.loc]
        cls.provisioning_template = cls.provisioning_template.update(
            ['location', 'operatingsystem', 'organization']
        )

        # Get the PXE template ID and update with OS, Org, location
        cls.pxe_template = entities.ConfigTemplate().search(
            query={
                u'search': u'name="Kickstart default PXELinux"'
            }
        )[0]
        cls.pxe_template.operatingsystem = [cls.os]
        cls.pxe_template.organization = [cls.org]
        cls.pxe_template.location = [cls.loc]
        cls.pxe_template = cls.pxe_template.update(
            ['location', 'operatingsystem', 'organization']
        )
        # Get the arch ID
        cls.arch = entities.Architecture().search(
            query={u'search': u'name="x86_64"'}
        )[0]
        # Get the ostree installer URL
        ostree_path = settings.ostree.ostree_installer
        # Get the Media
        cls.media = entities.Media().search(query={
            u'search': u'path={0}'.format(ostree_path)
        })
        if len(cls.media) == 1:
            cls.media = cls.media[0]
            cls.media.location = [cls.loc]
            cls.media.organization = [cls.org]
            cls.media = cls.media.update(['location', 'organization'])
        else:
            cls.media = entities.Media(
                organization=[cls.org],
                location=[cls.loc],
                os_family='Redhat',
                path_=ostree_path
            ).create()
        # Update the OS to associate arch, ptable, templates
        cls.os.architecture = [cls.arch]
        cls.os.ptable = [cls.ptable]
        cls.os.config_template = [cls.pxe_template, cls.provisioning_template]
        cls.os.medium = [cls.media]
        cls.os = cls.os.update([
            'architecture',
            'config_template',
            'ptable',
            'medium',
        ])

        # Create Hostgroup
        cls.host_group = entities.HostGroup(
            architecture=cls.arch,
            domain=cls.domain.id,
            subnet=cls.subnet.id,
            lifecycle_environment=cls.lc_env.id,
            content_view=cls.cv.id,
            location=[cls.loc.id],
            name=gen_string('alpha'),
            medium=cls.media,
            operatingsystem=cls.os.id,
            organization=[cls.org.id],
            ptable=cls.ptable.id,
        ).create()

    def tearDown(self):
        """Delete the host to free the resources"""
        with Session(self) as session:
            session.nav.go_to_select_org(self.org_name)
            host_name = u'{0}.{1}'.format(self.hostname, self.domain_name)
            if self.hosts.search(host_name):
                self.hosts.delete(host_name, dropdown_present=True)
        super(AtomicHostTestCase, self).tearDown()

    @tier3
    def test_positive_provision_atomic_host(self):
        """Provision an atomic host on libvirt and register it with satellite

        :id: 5ddf2f7f-f7aa-4321-8717-372c7b6e99b6

        :expectedresults: Atomic host should be provisioned and listed under
            content-hosts/Hosts

        :CaseLevel: System
        """
        resource = u'{0} (Libvirt)'.format(self.computeresource.name)
        root_pwd = gen_string('alpha', 15)
        with Session(self) as session:
            make_host(
                session,
                name=self.hostname,
                org=self.org_name,
                parameters_list=[
                    ['Host', 'Organization', self.org_name],
                    ['Host', 'Location', self.loc_name],
                    ['Host', 'Host group', self.host_group.name],
                    ['Host', 'Deploy on', resource],
                    ['Virtual Machine', 'Memory', '1 GB'],
                    ['Operating System', 'Media', self.media.name],
                    ['Operating System', 'Partition table', DEFAULT_PTABLE],
                    ['Operating System', 'Root password', root_pwd],
                ],
                interface_parameters=[
                    ['Network type', 'Physical (Bridge)'],
                    ['Network', settings.vlan_networking.bridge],
                ],
            )
            search = self.hosts.search(
                u'{0}.{1}'.format(self.hostname, self.domain_name)
            )
            self.assertIsNotNone(search)

    @stubbed()
    @tier3
    def test_positive_register_pre_installed_atomic_host(self):
        """Register a pre-installed atomic host with satellite using admin
        credentials

        :id: 09729944-b60b-4742-8f1b-e8859e2e36d3

        :expectedresults: Atomic host should be registered successfully and
            listed under content-hosts/Hosts

        :caseautomation: notautomated

        :CaseLevel: System
        """

    @stubbed()
    @tier3
    def test_positive_register_pre_installed_atomic_host_using_ak(self):
        """Register a pre-installed atomic host with satellite using activation
        key

        :id: 31e5ffcf-2e3c-474a-a6a3-6d8e2f392abe

        :expectedresults: Atomic host should be registered successfully and
            listed under content-hosts/Hosts

        :caseautomation: notautomated

        :CaseLevel: System
        """

    @tier3
    def test_positive_delete_atomic_host(self):
        """Delete a provisioned atomic host

        :id: c0bcf753-8ddf-4e95-b214-42d1e077a6cf

        :expectedresults: Atomic host should be deleted successfully and
            shouldn't be listed under hosts/content-hosts

        :CaseLevel: System
        """
        resource = u'{0} (Libvirt)'.format(self.computeresource.name)
        root_pwd = gen_string('alpha', 15)
        with Session(self) as session:
            make_host(
                session,
                name=self.hostname,
                org=self.org_name,
                parameters_list=[
                    ['Host', 'Organization', self.org_name],
                    ['Host', 'Location', self.loc_name],
                    ['Host', 'Host group', self.host_group.name],
                    ['Host', 'Deploy on', resource],
                    ['Virtual Machine', 'Memory', '1 GB'],
                    ['Operating System', 'Media', self.media.name],
                    ['Operating System', 'Partition table', DEFAULT_PTABLE],
                    ['Operating System', 'Root password', root_pwd],
                ],
                interface_parameters=[
                    ['Network type', 'Physical (Bridge)'],
                    ['Network', settings.vlan_networking.bridge],
                ],
            )
            # Delete host
            self.hosts.delete(
                u'{0}.{1}'.format(self.hostname, self.domain_name),
                dropdown_present=True,
            )

    @stubbed()
    @tier3
    def test_positive_update_atomic_host_cv(self):
        """Update atomic-host with a new environment and content-view

        :id: 2ddd3bb7-ef58-42c0-908c-ae4d4bd0bff9

        :expectedresults: Atomic host should be updated with new content-view

        :caseautomation: notautomated

        :CaseLevel: System
        """

    @stubbed()
    @tier3
    def test_positive_execute_cmd_on_atomic_host_with_job_templates(self):
        """Execute ostree/atomic commands on provisioned atomic host with job
        templates

        :id: 56a46a1e-9e24-4ad7-9cea-3d78c7310b14

        :expectedresults: Ostree/atomic commands should be executed
            successfully via job templates

        :caseautomation: notautomated

        :CaseLevel: System
        """


class BulkHostTestCase(UITestCase):
    """Implements tests for Bulk Hosts actions in UI"""

    @tier3
    def test_positive_bulk_delete_host(self):
        """Delete a multiple hosts from the list

        :id: 8da2084a-8b50-46dc-b305-18eeb80d01e0

        :expectedresults: All selected hosts should be deleted successfully

        :BZ: 1368026

        :CaseLevel: System
        """
        org = entities.Organization().create()
        hosts_names = [
            entities.Host(
                organization=org
            ).create().name
            for _ in range(18)
        ]
        with Session(self) as session:
            set_context(session, org=org.name)
            self.assertIsNotNone(self.hosts.update_host_bulkactions(
                hosts_names,
                action='Delete Hosts',
                parameters_list=[{'timeout': 300}],
            ))

    @stubbed()
    @tier3
    def test_positive_bulk_delete_atomic_host(self):
        """Delete a multiple atomic hosts

        :id: 7740e7c2-db54-4f6a-b5d4-6005fccb4c61

        :expectedresults: All selected atomic hosts should be deleted
            successfully

        :caseautomation: notautomated

        :CaseLevel: System
        """
