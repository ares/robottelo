"""Tests for Oscapcontent

:Requirement: Oscapcontent

:CaseAutomation: Automated

:CaseLevel: Acceptance

:CaseComponent: UI

:TestType: Functional

:CaseImportance: High

:Upstream: No
"""
import unittest2

from fauxfactory import gen_string
from nailgun import entities
from robottelo.config import settings
from robottelo.constants import OSCAP_DEFAULT_CONTENT
from robottelo.datafactory import invalid_values_list, valid_data_list
from robottelo.decorators import (
    skip_if_bug_open,
    skip_if_not_set,
    tier1,
    tier2,
)
from robottelo.helpers import get_data_file
from robottelo.test import UITestCase
from robottelo.ui.factory import make_oscapcontent
from robottelo.ui.locators import common_locators
from robottelo.ui.session import Session


class OpenScapContentTestCase(UITestCase):
    """Implements Oscap Content tests in UI."""

    @classmethod
    @skip_if_not_set('oscap')
    def setUpClass(cls):
        super(OpenScapContentTestCase, cls).setUpClass()
        path = settings.oscap.content_path
        cls.content_path = get_data_file(path)
        org = entities.Organization(name=gen_string('alpha')).create()
        cls.org_name = org.name
        proxy = entities.SmartProxy().search(
            query={
                u'search': u'name={0}'.format(
                    settings.server.hostname)
            }
        )[0]
        proxy.organization = [org]

    @tier1
    def test_positive_create(self):
        """Create OpenScap content.

        :id: 6580cffa-da37-40d5-affa-cfb1ff27c545

        :Steps:

            1. Create an openscap content.
            2. Provide all the appropriate parameters.

        :expectedresults: Whether creating  content for OpenScap is successful.

        :CaseImportance: Critical
        """
        with Session(self) as session:
            for content_name in valid_data_list():
                with self.subTest(content_name):
                    make_oscapcontent(
                        session,
                        name=content_name,
                        content_path=self.content_path,
                        content_org=self.org_name,
                    )
                    self.assertIsNotNone(
                        self.oscapcontent.search(content_name))

    @skip_if_bug_open('bugzilla', 1289571)
    @tier1
    def test_negative_create_with_invalid_name(self):
        """Create OpenScap content with negative values

        :id: 8ce0e8b4-396a-43cd-8cbe-fb60fcf853b0

        :Steps:

            1. Create an openscap content.
            2. Provide all the appropriate parameters.

        :expectedresults: Creating content for OpenScap is not successful.

        :BZ: 1289571

        :CaseImportance: Critical
        """
        with Session(self) as session:
            for content_name in invalid_values_list(interface='ui'):
                with self.subTest(content_name):
                    make_oscapcontent(
                        session,
                        name=content_name,
                        content_path=self.content_path,
                        content_org=self.org_name,
                    )
                    self.assertIsNotNone(session.nav.wait_until_element(
                        common_locators['haserror']))

    @tier1
    @unittest2.skip('oscap contents are not installed by default.'
                    'Installer needs to be fixed')
    def test_positive_default(self):
        """Check whether OpenScap content exists by default.

        :id: 0beca127-8294-4d85-bace-b9170215c0cd

        :Steps:

            1. Set Org as Any Org.
            2. Navigate to oscap Content page.

        :expectedresults: Whether oscap content exists by default.

        :CaseImportance: Critical
        """
        # see BZ 1336374
        with Session(self):
            self.assertIsNotNone(self.oscapcontent.search(
                OSCAP_DEFAULT_CONTENT['rhel7_content']))
            self.assertIsNotNone(self.oscapcontent.search(
                OSCAP_DEFAULT_CONTENT['rhel6_content']))

    @tier2
    def test_positive_update(self):
        """Update OpenScap content.

        :id: 9870555d-0b60-41ab-a481-81d4d3f78fec

        :Steps:

            1. Create an openscap content.
            2. Provide all the appropriate parameters.
            3. Update the openscap content, here the Org.

        :expectedresults: Whether creating  content for OpenScap is successful.

        :CaseLevel: Integration
        """
        org = entities.Organization(name=gen_string('alpha')).create()
        content_name = gen_string('alpha')
        with Session(self) as session:
            make_oscapcontent(
                session,
                name=content_name,
                content_path=self.content_path,
                content_org=self.org_name,
            )
            self.oscapcontent.update(content_name, content_org=org.name)
            session.nav.go_to_select_org(org.name)
            self.assertIsNotNone(
                self.oscapcontent.search(content_name))

    @tier1
    def test_positive_delete(self):
        """Create OpenScap content and then delete it.

        :id: 8eade129-5666-4e90-ba3e-f0c51a3090ce

        :Steps:

            1. Create an openscap content.
            2. Provide all the appropriate parameters.
            3. Delete the openscap content.

        :expectedresults: Deleting content for OpenScap is successful.

        :CaseImportance: Critical
        """
        with Session(self) as session:
            for content_name in valid_data_list():
                with self.subTest(content_name):
                    make_oscapcontent(
                        session,
                        name=content_name,
                        content_path=self.content_path,
                        content_org=self.org_name,
                    )
                    self.assertIsNotNone(
                        self.oscapcontent.search(content_name))
                    self.oscapcontent.delete(
                        content_name, dropdown_present=True)
