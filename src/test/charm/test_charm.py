# Copyright 2021 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

from src.main.charm.charm import SpringMusicCharm

import unittest

from ops.model import ActiveStatus
from ops.testing import Harness

import pathlib
import os

root_directory = pathlib.Path(__file__).parent.parent.parent.parent.absolute()


class CharmResource:
    def __init__(self, file_path):
        with open(os.path.join(root_directory, f"src/main/charm_resources/{file_path}")) as f:
            self.content = f.read()


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(
            charm_cls=SpringMusicCharm,
            meta=CharmResource("metadata.yaml").content,
            actions=None,
            config=None,
        )
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_bootstrap(self):
        container = self.harness.model.unit.get_container("application")

        self.harness.charm.on.application_pebble_ready.emit(container)

        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

        service = self.harness.model.unit.get_container("application").get_service("spring-music")
        self.assertTrue(service.is_running())
