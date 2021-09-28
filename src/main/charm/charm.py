#!/usr/bin/env python3
# Copyright 2021 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the Spring Music application.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
    ModelError,
    WaitingStatus
)

from kubernetes_service import K8sServicePatch, PatchFailed

from src.main.charm_libs.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider

logger = logging.getLogger(__name__)


SPRING_MUSIC_SERVICE_NAME = "spring-music"


class SpringMusicCharm(CharmBase):

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._port = 8080

        self._stored.set_default(k8s_service_patched=False)

        self.metrics_endpoint = MetricsEndpointProvider(
            self,
            jobs=[
                {
                    # Adjust the default `/metrics` path to the one exposed
                    # by the Spring Boot actuator.
                    "metrics_path": "/actuator/prometheus",
                    # The prometheus scrape library will automatically expand
                    # the `*` symbol to the pod IPs of all the units of this
                    # application.
                    "static_configs": [{"targets": ["*:8080"]}],
                },
            ],
        )

        self.framework.observe(
            self.on.install, self._on_install
        )
        self.framework.observe(
            self.on.application_pebble_ready, self._on_application_pebble_ready
        )
        self.framework.observe(
            self.on.upgrade_charm, self._on_upgrade_charm
        )

    def _on_install(self, _):
        """Set the right port on the K8s service on installation of the Juju app."""
        self._patch_k8s_service()

    def _on_application_pebble_ready(self, _):
        self._update_and_restart_spring_music()

    def _on_upgrade_charm(self, _):
        self._update_and_restart_spring_music()

    def _update_and_restart_spring_music(self):
        container = self.unit.get_container("application")

        if not container.can_connect():
            self.unit.status = WaitingStatus("container 'application' not yet ready")
            return

        updated_pebble_layer = {
            "summary": "application layer",
            "description": "Pebble config layer for the Spring Music application",
            "services": {
                SPRING_MUSIC_SERVICE_NAME: {
                    "override": "replace",
                    "summary": "Spring Music application",
                    "command": "/cnb/process/web",
                },
            },
        }

        current_pebble_layer = container.get_plan().to_dict()

        if current_pebble_layer != updated_pebble_layer:
            self.unit.status = MaintenanceStatus(
                f"updating the {SPRING_MUSIC_SERVICE_NAME} service"
            )

            container.add_layer("spring-music", updated_pebble_layer, combine=True)

            self.unit.status = MaintenanceStatus(
                f"stopping the '{SPRING_MUSIC_SERVICE_NAME}' service to update the configurations"
            )

            is_restart = self._stop_spring_music()

            self.unit.status = MaintenanceStatus(
                f"starting the '{SPRING_MUSIC_SERVICE_NAME}' service"
            )

            container.start(SPRING_MUSIC_SERVICE_NAME)

            if is_restart:
                logger.info("Spring Music restarted")
            else:
                logger.info("Spring Music started")
        else:
            logger.debug("No differences found in the Pebble plan, no restart needed")

        self.unit.status = ActiveStatus()

    def _stop_spring_music(self):
        container = self.unit.get_container("application")

        try:
            if container.get_service(SPRING_MUSIC_SERVICE_NAME).is_running():
                logging.info("Stopping Spring Music")

                container.stop(SPRING_MUSIC_SERVICE_NAME)

                return True
        except ModelError:
            # We have not yet set up the pebble service, nevermind
            logger.debug(
                "The following error occurred while stopping the '%s' service, "
                "maybe it has not been created yet?",
                SPRING_MUSIC_SERVICE_NAME,
                exc_info=True,
            )

        return False

    def _patch_k8s_service(self):
        """Fix the Kubernetes service that was setup by Juju with correct port numbers."""
        if self.unit.is_leader() and not self._stored.k8s_service_patched:
            service_ports = [
                (f"{self.app.name}", self._port, self._port),
            ]
            try:
                K8sServicePatch.set_ports(self.app.name, service_ports)
            except PatchFailed as e:
                logger.error("Unable to patch the Kubernetes service: %s", str(e))
            else:
                self._stored.k8s_service_patched = True
                logger.info("Successfully patched the Kubernetes service!")


if __name__ == "__main__":
    main(SpringMusicCharm)
