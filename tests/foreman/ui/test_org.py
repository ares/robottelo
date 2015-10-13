# -*- encoding: utf-8 -*-
# pylint: disable=too-many-public-methods, invalid-name
"""Test class for Organization UI"""

from fauxfactory import gen_ipaddr, gen_string
from nailgun import entities
from robottelo import manifests
from robottelo.api.utils import upload_manifest
from robottelo.config import settings
from robottelo.constants import INSTALL_MEDIUM_URL, LIBVIRT_RESOURCE_URL
from robottelo.datafactory import (
    generate_strings_list,
    invalid_names_list,
    invalid_values_list,
)
from robottelo.decorators import run_only_on, skip_if_bug_open, stubbed
from robottelo.test import UITestCase
from robottelo.ui.factory import make_lifecycle_environment, make_org
from robottelo.ui.locators import common_locators, locators, tab_locators
from robottelo.ui.session import Session


def valid_labels():
    """Returns a list of valid labels"""
    return [
        gen_string('alpha'),
        gen_string('numeric'),
        gen_string('alphanumeric'),
    ]


def valid_users():
    """Returns a list of valid users"""
    return[
        gen_string('alpha'),
        gen_string('numeric'),
        gen_string('alphanumeric'),
        gen_string('utf8'),
        gen_string('latin1'),
        # Note: HTML username is invalid as per the UI msg.
    ]


def valid_env_names():
    """Returns a list of valid environment names"""
    return [
        gen_string('alpha'),
        gen_string('numeric'),
        gen_string('alphanumeric'),
    ]


class Org(UITestCase):
    """Implements Organization tests in UI"""

    # Tests for issues

    @skip_if_bug_open('bugzilla', 1177610)
    def test_auto_search(self):
        """@test: Search for an organization can be auto-completed by partial
        name

        @feature: Organizations

        @assert: Auto search for created organization works as intended

        @BZ: 1177610

        """
        org_name = gen_string('alpha')
        part_string = org_name[:3]
        with Session(self.browser) as session:
            page = session.nav.go_to_org
            make_org(session, org_name=org_name)
            auto_search = self.org.auto_complete_search(
                page, locators['org.org_name'], part_string, org_name,
                search_key='name')
            self.assertIsNotNone(auto_search)

    # Positive Create

    def test_positive_create_with_different_names(self):
        """@test: Create organization with valid name only.

        @feature: Organizations

        @assert: Organization is created, label is auto-generated

        """
        with Session(self.browser) as session:
            for org_name in generate_strings_list():
                with self.subTest(org_name):
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))

    @stubbed('parent_org feature is disabled currently')
    def test_positive_create_with_parent(self):
        """@test: Create organization with valid name, label, parent_org, desc.

        @feature: Organizations

        @assert: organization is created.

        """
        with Session(self.browser) as session:
            for parent_name in generate_strings_list():
                with self.subTest(parent_name):
                    org_name = gen_string('alpha')
                    make_org(session, org_name=parent_name)
                    make_org(
                        session,
                        org_name=org_name,
                        label=gen_string('alpha'),
                        desc=gen_string('alpha'),
                        parent_org=parent_name
                    )
                    self.assertIsNotNone(self.org.search(org_name))

    # As label cannot contain chars other than ascii alpha numerals, '_', '-'.
    def test_positive_create_with_diff_names_and_labels(self):
        """@test: Create organization with valid unmatching name and label only

        @feature: Organizations

        @assert: organization is created, label does not match name

        """
        with Session(self.browser) as session:
            for label in valid_labels():
                with self.subTest(label):
                    org_name = gen_string('alphanumeric')
                    make_org(
                        session, org_name=org_name, label=label)
                    self.org.search(org_name).click()
                    name = session.nav.wait_until_element(
                        locators['org.name']).get_attribute('value')
                    label = session.nav.wait_until_element(
                        locators['org.label']).get_attribute('value')
                    self.assertNotEqual(name, label)

    # As label cannot contain chars other than ascii alpha numerals, '_', '-'.
    def test_positive_create_with_same_names_and_labels(self):
        """@test: Create organization with valid matching name and label only.

        @feature: Organizations

        @assert: organization is created, label matches name

        """
        with Session(self.browser) as session:
            for item in valid_labels():
                with self.subTest(item):
                    make_org(session, org_name=item, label=item)
                    self.org.search(item).click()
                    name = self.org.wait_until_element(
                        locators['org.name']).get_attribute('value')
                    label = self.org.wait_until_element(
                        locators['org.label']).get_attribute('value')
                    self.assertEqual(name, label)

    @skip_if_bug_open('bugzilla', 1079482)
    def test_positive_create_with_auto_gen_label(self):
        """@test: Create organization with valid name. Check that organization
        label is auto-populated

        @feature: Organizations

        @assert: organization is created, label is auto-generated

        @BZ: 1079482

        """
        with Session(self.browser) as session:
            for org_name in generate_strings_list():
                with self.subTest(org_name):
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.search(org_name).click()
                    label = session.nav.wait_until_element(
                        locators['org.label'])
                    label_value = label.get_attribute('value')
                    self.assertIsNotNone(label_value)

    def test_positive_create_with_both_location_and_org(self):
        """@test: Select both organization and location.

        @feature: Organizations

        @assert: Both organization and location are selected.

        """
        with Session(self.browser) as session:
            for name in generate_strings_list():
                with self.subTest(name):
                    #  Use nailgun to create Location
                    location = entities.Location(name=name).create()
                    self.assertEqual(location.name, name)
                    make_org(session, org_name=name, locations=[name])
                    self.assertIsNotNone(self.org.search(name))
                    organization = session.nav.go_to_select_org(name)
                    location = session.nav.go_to_select_loc(name)
                    self.assertEqual(organization, name)
                    self.assertEqual(location, name)

    def test_negative_create_with_different_names(self):
        """@test: Try to create organization and use whitespace, blank, tab
        symbol or too long string of different types as its name value

        @feature: Organizations Negative Tests

        @assert: organization is not created

        """
        with Session(self.browser) as session:
            for org_name in invalid_values_list(interface='ui'):
                with self.subTest(org_name):
                    make_org(session, org_name=org_name)
                    error = session.nav.wait_until_element(
                        common_locators['name_haserror'])
                    self.assertIsNotNone(error)

    def test_negative_create_with_same_name(self):
        """@test: Create organization with valid values, then create a new one
        with same values.

        @feature: Organizations Negative Test.

        @assert: organization is not created

        """
        with Session(self.browser) as session:
            for org_name in generate_strings_list():
                with self.subTest(org_name):
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.create(org_name)
                    error = session.nav.wait_until_element(
                        common_locators['name_haserror'])
                    self.assertIsNotNone(error)

    # Positive Delete

    def test_positive_delete(self):
        """@test: Create organization with valid values then delete it.

        @feature: Organizations Positive Delete test.

        @assert: Organization is deleted successfully

        """
        with Session(self.browser) as session:
            for org_name in generate_strings_list():
                with self.subTest(org_name):
                    # Use nailgun to create org
                    entities.Organization(name=org_name).create()
                    session.nav.go_to_org()
                    self.org.remove(org_name)

    def test_positive_delete_bz1225588(self):
        """@test: Create Organization with valid values and upload manifest.
        Then try to delete that organization.

        @feature: Organization Positive Delete Test.

        @assert: Organization is deleted successfully.

        """
        org_name = gen_string('alphanumeric')
        org = entities.Organization(name=org_name).create()
        with open(manifests.clone(), 'rb') as manifest:
            upload_manifest(org.id, manifest)
        with Session(self.browser) as session:
            make_lifecycle_environment(session, org_name, name='DEV')
            make_lifecycle_environment(
                session, org_name, name='QE', prior='DEV'
            )
            # Org cannot be deleted when selected,
            # So switching to Default Org and then deleting.
            session.nav.go_to_select_org('Default Organization')
            self.org.remove(org_name)
            session.nav.go_to_dashboard()
            status = self.org.search(org_name)
            # Check for at least ten times that org is deleted due #1225588
            for _ in range(10):
                status = self.org.search(org_name)
                if status is None:
                    break
            self.assertIsNone(status)

    def test_manifest_refresh_bz1259248(self):
        """@test: Create organization with valid manifest. Download debug
        certificate for that organization and refresh added manifest for few
        times in a row

        @feature: Organizations.

        @assert: Scenario passed without any issues in application

        """
        org = entities.Organization().create()
        sub = entities.Subscription(organization=org)
        with open(manifests.download_manifest_template(), 'rb') as manifest:
            upload_manifest(org.id, manifest)
        try:
            with Session(self.browser) as session:
                for _ in range(3):
                    self.assertIsNotNone(org.download_debug_certificate())
                    session.nav.go_to_select_org(org.name)
                    session.nav.go_to_red_hat_subscriptions()
                    self.subscriptions.refresh()
                    self.assertIsNone(session.nav.wait_until_element(
                        common_locators['notif.error'], timeout=5))
                    self.assertTrue(session.nav.wait_until_element(
                        common_locators['alert.success'], timeout=180))
        finally:
            sub.delete_manifest(data={'organization_id': org.id})

    # Negative Delete

    # Positive Update

    def test_positive_update_with_different_names(self):
        """@test: Create organization with valid values then update its name.

        @feature: Organizations Positive Update test.

        @assert: Organization name is updated successfully

        """
        org_name = gen_string('alpha')
        with Session(self.browser) as session:
            make_org(session, org_name=org_name)
            self.assertIsNotNone(self.org.search(org_name))
            for new_name in generate_strings_list():
                with self.subTest(new_name):
                    self.org.update(org_name, new_name=new_name)
                    self.assertIsNotNone(self.org.search(new_name))
                    org_name = new_name  # for next iteration

    # Negative Update

    def test_negative_update(self):
        """@test: Create organization with valid values then try to update it
        using incorrect name values

        @feature: Organizations Negative Update test.

        @assert: Organization name is not updated

        """
        org_name = gen_string('alpha')
        with Session(self.browser) as session:
            make_org(session, org_name=org_name)
            self.assertIsNotNone(self.org.search(org_name))
            for new_name in invalid_names_list():
                with self.subTest(new_name):
                    self.org.update(org_name, new_name=new_name)
                    error = session.nav.wait_until_element(
                        common_locators['name_haserror'])
                    self.assertIsNotNone(error)

    # Miscellaneous

    # Associations

    @run_only_on('sat')
    def test_remove_domain(self):
        """@test: Add a domain to an organization and remove it by organization
        name and domain name.

        @feature: Organizations Disassociate domain.

        @assert: the domain is removed from the organization

        """
        strategy, value = common_locators['entity_select']
        strategy1, value1 = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for domain_name in generate_strings_list():
                with self.subTest(domain_name):
                    org_name = gen_string('alpha')
                    domain = entities.Domain(name=domain_name).create()
                    self.assertEqual(domain.name, domain_name)
                    make_org(session, org_name=org_name, domains=[domain_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_domains'])
                    element = session.nav.wait_until_element(
                        (strategy1, value1 % domain_name))
                    # Item is listed in 'Selected Items' list and not
                    # 'All Items' list.
                    self.assertIsNotNone(element)
                    self.org.update(org_name, domains=[domain_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_domains'])
                    element = session.nav.wait_until_element(
                        (strategy, value % domain_name))
                    # Item is listed in 'All Items' list and not
                    # 'Selected Items' list.
                    self.assertIsNotNone(element)

    def test_remove_user(self):
        """@test: Create admin users then add user and remove it
        by using the organization name.

        @feature: Organizations Disassociate user.

        @assert: The user is added then removed from the organization

        """
        strategy, value = common_locators['entity_select']
        strategy1, value1 = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for user_name in valid_users():
                with self.subTest(user_name):
                    org_name = gen_string('alpha')
                    # Use nailgun to create user
                    user = entities.User(
                        login=user_name,
                        firstname=user_name,
                        lastname=user_name,
                        password=gen_string('alpha'),
                    ).create()
                    self.assertEqual(user.login, user_name)
                    make_org(session, org_name=org_name, users=[user_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_users'])
                    element = session.nav.wait_until_element(
                        (strategy1, value1 % user_name))
                    # Item is listed in 'Selected Items' list and not
                    # 'All Items' list.
                    self.assertIsNotNone(element)
                    self.org.update(
                        org_name, users=[user_name], new_users=None)
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_users'])
                    element = session.nav.wait_until_element(
                        (strategy, value % user_name))
                    # Item is listed in 'All Items' list and not
                    # 'Selected Items' list.
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_remove_hostgroup(self):
        """@test: Add a hostgroup and remove it by using the organization
        name and hostgroup name.

        @feature: Organizations Remove Hostgroup.

        @assert: hostgroup is added to organization then removed.

        """
        strategy, value = common_locators['entity_select']
        strategy1, value1 = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for host_grp_name in generate_strings_list():
                with self.subTest(host_grp_name):
                    org_name = gen_string('alpha')
                    # Create hostgroup using nailgun
                    host_grp = entities.HostGroup(name=host_grp_name).create()
                    self.assertEqual(host_grp.name, host_grp_name)
                    make_org(
                        session, org_name=org_name, hostgroups=[host_grp_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_hostgrps'])
                    element = session.nav.wait_until_element(
                        (strategy1, value1 % host_grp_name))
                    # Item is listed in 'Selected Items' list and not
                    # 'All Items' list.
                    self.assertIsNotNone(element)
                    self.org.update(
                        org_name,
                        hostgroups=[host_grp_name],
                        new_hostgroups=None
                    )
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_hostgrps'])
                    element = session.nav.wait_until_element(
                        (strategy, value % host_grp_name))
                    # Item is listed in 'All Items' list and not
                    # Selected Items' list.
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    @stubbed()
    def test_add_smartproxy_1(self):
        """@test: Add a smart proxy by using org and smartproxy name

        @feature: Organizations

        @assert: smartproxy is added

        @status: manual

        """

        pass

    @run_only_on('sat')
    def test_add_subnet(self):
        """@test: Add a subnet using organization name and subnet name.

        @feature: Organizations associate subnet.

        @assert: subnet is added.

        """
        strategy, value = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for subnet_name in generate_strings_list():
                with self.subTest(subnet_name):
                    org_name = gen_string('alpha')
                    # Create subnet using nailgun
                    subnet = entities.Subnet(
                        name=subnet_name,
                        network=gen_ipaddr(ip3=True),
                        mask='255.255.255.0'
                    ).create()
                    self.assertEqual(subnet.name, subnet_name)
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.update(org_name, new_subnets=[subnet_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_subnets'])
                    element = session.nav.wait_until_element(
                        (strategy, value % subnet_name))
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_add_domain(self):
        """@test: Add a domain to an organization.

        @feature: Organizations associate domain.

        @assert: Domain is added to organization.

        """
        strategy, value = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for domain_name in generate_strings_list():
                with self.subTest(domain_name):
                    org_name = gen_string('alpha')
                    domain = entities.Domain(name=domain_name).create()
                    self.assertEqual(domain.name, domain_name)
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.update(org_name, new_domains=[domain_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_domains'])
                    element = session.nav.wait_until_element(
                        (strategy, value % domain_name))
                    self.assertIsNotNone(element)

    def test_add_user(self):
        """@test: Create different types of users then add user using
        organization name.

        @feature: Organizations associate user.

        @assert: User is added to organization.

        """
        strategy, value = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for user_name in valid_users():
                with self.subTest(user_name):
                    org_name = gen_string('alpha')
                    user = entities.User(
                        login=user_name,
                        firstname=user_name,
                        lastname=user_name,
                        password=gen_string('alpha')
                    ).create()
                    self.assertEqual(user.login, user_name)
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.update(org_name, new_users=[user_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_users'])
                    element = session.nav.wait_until_element(
                        (strategy, value % user_name))
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_add_hostgroup(self):
        """@test: Add a hostgroup by using the organization
        name and hostgroup name.

        @feature: Organizations associate host-group.

        @assert: hostgroup is added to organization

        """
        strategy, value = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for host_grp_name in generate_strings_list():
                with self.subTest(host_grp_name):
                    org_name = gen_string('alpha')
                    # Create host group using nailgun
                    host_grp = entities.HostGroup(name=host_grp_name).create()
                    self.assertEqual(host_grp.name, host_grp_name)
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.update(org_name, new_hostgroups=[host_grp_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_hostgrps'])
                    element = session.nav.wait_until_element(
                        (strategy, value % host_grp_name))
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_add_location(self):
        """@test: Add a location by using the organization name and location
        name

        @feature: Organizations associate location.

        @assert: location is added to organization.

        """
        strategy, value = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for location_name in generate_strings_list():
                with self.subTest(location_name):
                    org_name = gen_string('alpha')
                    location = entities.Location(name=location_name).create()
                    self.assertEqual(location.name, location_name)
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.update(org_name, new_locations=[location_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_locations'])
                    element = session.nav.wait_until_element(
                        (strategy, value % location_name))
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_remove_computeresource(self):
        """@test: Remove compute resource using the organization name and
        compute resource name.

        @feature: Organizations dis-associate compute-resource.

        @assert: compute resource is added then removed.

        """
        strategy, value = common_locators['entity_select']
        strategy1, value1 = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for resource_name in generate_strings_list():
                with self.subTest(resource_name):
                    org_name = gen_string('alpha')
                    url = LIBVIRT_RESOURCE_URL % settings.server.hostname
                    # Create compute resource using nailgun
                    resource = entities.LibvirtComputeResource(
                        name=resource_name,
                        url=url
                    ).create()
                    self.assertEqual(resource.name, resource_name)
                    make_org(
                        session, org_name=org_name, resources=[resource_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_resources'])
                    element = session.nav.wait_until_element(
                        (strategy1, value1 % resource_name))
                    # Item is listed in 'Selected Items' list and not
                    # 'All Items' list.
                    self.assertIsNotNone(element)
                    self.org.update(
                        org_name,
                        resources=[resource_name],
                        new_resources=None
                    )
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_resources'])
                    element = session.nav.wait_until_element(
                        (strategy, value % resource_name))
                    # Item is listed in 'All Items' list and not
                    # 'Selected Items' list.
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_remove_medium(self):
        """@test: Remove medium by using organization name and medium name.

        @feature: Organizations disassociate installation media.

        @assert: medium is added then removed.

        """
        strategy, value = common_locators['entity_select']
        strategy1, value1 = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for medium_name in generate_strings_list():
                with self.subTest(medium_name):
                    org_name = gen_string('alpha')
                    # Create media using nailgun
                    medium = entities.Media(
                        name=medium_name,
                        path_=INSTALL_MEDIUM_URL % gen_string('alpha', 6),
                        os_family='Redhat',
                    ).create()
                    self.assertEqual(medium.name, medium_name)
                    make_org(session, org_name=org_name, medias=[medium_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_media'])
                    element = session.nav.wait_until_element(
                        (strategy1, value1 % medium_name))
                    # Item is listed in 'Selected Items' list and not
                    # 'All Items' list.
                    self.assertIsNotNone(element)
                    self.navigator.go_to_org()
                    self.org.update(
                        org_name, medias=[medium_name], new_medias=None)
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_media'])
                    element = session.nav.wait_until_element(
                        (strategy, value % medium_name))
                    # Item is listed in 'All Items' list and not
                    # 'Selected Items' list.
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_remove_configtemplate(self):
        """@test: Remove config template.

        @feature: Organizations dissociate config templates.

        @assert: configtemplate is added then removed.

        @BZ: 1129612

        """
        strategy, value = common_locators['entity_select']
        strategy1, value1 = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for template_name in generate_strings_list():
                with self.subTest(template_name):
                    org_name = gen_string('alpha')
                    # Create config template using nailgun
                    entities.ConfigTemplate(name=template_name).create()
                    make_org(
                        session, org_name=org_name, templates=[template_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_template'])
                    element = session.nav.wait_until_element(
                        (strategy1, value1 % template_name))
                    # Item is listed in 'Selected Items' list and not
                    # 'All Items' list.
                    self.assertIsNotNone(element)
                    self.org.update(org_name, templates=[template_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_template'])
                    element = self.org.wait_until_element(
                        (strategy, value % template_name))
                    # Item is listed in 'All Items' list and not
                    # 'Selected Items' list.
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_add_environment(self):
        """@test: Add environment by using organization name and env name.

        @feature: Organizations associate environment.

        @assert: environment is added.

        """
        strategy, value = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for env_name in valid_env_names():
                with self.subTest(env_name):
                    org_name = gen_string('alpha')
                    env = entities.Environment(name=env_name).create_json()
                    self.assertEqual(env['name'], env_name)
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.update(org_name, new_envs=[env_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_env'])
                    element = session.nav.wait_until_element(
                        (strategy, value % env_name))
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    @stubbed()
    def test_remove_smartproxy_1(self):
        """@test: Remove smartproxy by using organization name and smartproxy
        name

        @feature: Organizations

        @assert: smartproxy is added then removed

        @status: manual

        """

        pass

    @run_only_on('sat')
    def test_add_computeresource(self):
        """@test: Add compute resource using the organization
        name and compute resource name.

        @feature: Organizations associate compute resource.

        @assert: compute resource is added.

        """
        strategy, value = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for resource_name in generate_strings_list():
                with self.subTest(resource_name):
                    org_name = gen_string('alpha')
                    url = LIBVIRT_RESOURCE_URL % settings.server.hostname
                    # Create compute resource using nailgun
                    resource = entities.LibvirtComputeResource(
                        name=resource_name,
                        url=url,
                    ).create()
                    self.assertEqual(resource.name, resource_name)
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.update(org_name, new_resources=[resource_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_resources'])
                    element = session.nav.wait_until_element(
                        (strategy, value % resource_name))
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_add_medium(self):
        """@test: Add medium by using the organization name and medium name.

        @feature: Organizations associate medium.

        @assert: medium is added.

        """
        strategy, value = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for medium_name in generate_strings_list():
                with self.subTest(medium_name):
                    org_name = gen_string('alpha')
                    # Create media using nailgun
                    medium = entities.Media(
                        name=medium_name,
                        path_=INSTALL_MEDIUM_URL % gen_string('alpha', 6),
                        os_family='Redhat',
                    ).create()
                    self.assertEqual(medium.name, medium_name)
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.update(org_name, new_medias=[medium_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_media'])
                    element = session.nav.wait_until_element(
                        (strategy, value % medium_name))
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_add_configtemplate(self):
        """@test: Add config template by using organization name and
        config template name.

        @feature: Organizations associate config template.

        @assert: config template is added

        @BZ: 1129612

        """
        strategy, value = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for template_name in generate_strings_list():
                with self.subTest(template_name):
                    org_name = gen_string('alpha')
                    # Create config template using nailgun
                    entities.ConfigTemplate(name=template_name).create()
                    make_org(session, org_name=org_name)
                    self.assertIsNotNone(self.org.search(org_name))
                    self.org.update(org_name, new_templates=[template_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_template'])
                    element = session.nav.wait_until_element(
                        (strategy, value % template_name))
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_remove_environment(self):
        """@test: Remove environment by using org & environment name.

        @feature: Organizations dis-associate environment.

        @assert: environment is removed from Organization.

        """
        strategy, value = common_locators['entity_select']
        strategy1, value1 = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for env_name in valid_env_names():
                with self.subTest(env_name):
                    org_name = gen_string('alpha')
                    # Create environment using nailgun
                    env = entities.Environment(name=env_name).create_json()
                    self.assertEqual(env['name'], env_name)
                    make_org(session, org_name=org_name, envs=[env_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_env'])
                    element = session.nav.wait_until_element(
                        (strategy1, value1 % env_name))
                    # Item is listed in 'Selected Items' list and not
                    # 'All Items' list.
                    self.assertIsNotNone(element)
                    self.org.update(org_name, envs=[env_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_env'])
                    element = session.nav.wait_until_element(
                        (strategy, value % env_name))
                    # Item is listed in 'All Items' list and not
                    # 'Selected Items' list.
                    self.assertIsNotNone(element)

    @run_only_on('sat')
    def test_remove_subnet(self):
        """@test: Remove subnet by using organization name and subnet name.

        @feature: Organizations dis-associate subnet.

        @assert: subnet is added then removed.

        """
        strategy, value = common_locators['entity_select']
        strategy1, value1 = common_locators['entity_deselect']
        with Session(self.browser) as session:
            for subnet_name in generate_strings_list():
                with self.subTest(subnet_name):
                    org_name = gen_string('alpha')
                    # Create subnet using nailgun
                    subnet = entities.Subnet(
                        name=subnet_name,
                        network=gen_ipaddr(ip3=True),
                        mask='255.255.255.0',
                    ).create()
                    self.assertEqual(subnet.name, subnet_name)
                    make_org(session, org_name=org_name, subnets=[subnet_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_subnets'])
                    element = session.nav.wait_until_element(
                        (strategy1, value1 % subnet_name))
                    # Item is listed in 'Selected Items' list and not
                    # 'All Items' list.
                    self.assertIsNotNone(element)
                    self.org.update(org_name, subnets=[subnet_name])
                    self.org.search(org_name).click()
                    session.nav.click(tab_locators['context.tab_subnets'])
                    element = session.nav.wait_until_element(
                        (strategy, value % subnet_name))
                    # Item is listed in 'All Items' list and not
                    # 'Selected Items' list.
                    self.assertIsNotNone(element)
