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
from ops.model import ActiveStatus, MaintenanceStatus, ModelError, WaitingStatus

from kubernetes_service import K8sServicePatch, PatchFailed

from src.main.charm_libs.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from src.main.charm_libs.loki_k8s.v0.loki_push_api import LokiPushApiConsumer
from src.main.charm_libs.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from src.main.charm_libs.traefik_k8s.v0.ingress import IngressPerAppRequirer

from urllib.parse import urlparse

logger = logging.getLogger(__name__)


SPRING_MUSIC_SERVICE_NAME = "spring-music"


class SpringMusicCharm(CharmBase):

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._port = 8080

        self._stored.set_default(k8s_service_patched=False)

        self.ingress = IngressPerAppRequirer(charm=self, port=self._port)

        self.loki_consumer = LokiPushApiConsumer(
            self,
            alert_rules_path="src/main/charm_resources/loki_alert_rules",
        )

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
            # This configuration would not be needed if the charm code would
            # reside under `<repo_root>/src`.
            alert_rules_path="src/main/charm_resources/prometheus_alert_rules",
        )

        self.dashboard_provider = GrafanaDashboardProvider(
            self,
            # This configuration would not be needed if the charm code would
            # reside under `<repo_root>/src`.
            dashboards_path="src/main/charm_resources/grafana_dashboards",
        )

        self.framework.observe(self.ingress.on.ingress_changed, self._on_ingress_changed)

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.application_pebble_ready, self._on_application_pebble_ready)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)

        self.framework.observe(
            self.loki_consumer.on.loki_push_api_endpoint_joined,
            self._on_loki_push_api_endpoint_joined,
        )
        self.framework.observe(
            self.loki_consumer.on.loki_push_api_endpoint_departed,
            self._on_loki_push_api_endpoint_departed,
        )

    def _on_install(self, _):
        """Set the right port on the K8s service on installation of the Juju app."""
        self._patch_k8s_service()

    def _on_application_pebble_ready(self, _):
        self._update_and_restart_spring_music()

    def _on_ingress_changed(self, _):
        self._update_and_restart_spring_music()

    def _on_upgrade_charm(self, _):
        self._update_and_restart_spring_music()

    def _on_loki_push_api_endpoint_joined(self, _):
        logger.debug("Loki endpoint joined")
        self._update_and_restart_spring_music()

    def _on_loki_push_api_endpoint_departed(self, _):
        logger.debug("Loki endpoint departed")
        self._update_and_restart_spring_music()

    def _update_and_restart_spring_music(self):
        container = self.unit.get_container("application")

        if not container.can_connect():
            self.unit.status = WaitingStatus("container 'application' not yet ready")
            return

        # When the ingress is using subpaths to route to out application, we need to tell
        # Spring Music to adjust the root of its API accordingly
        context_path = urlparse(self.ingress.url).path if self.ingress.is_ready() else "/"
        logger.debug("Servlet context path: %s; ingress url: %s", context_path, self.ingress.url)

        environment = {
            "SERVER_SERVLET_CONTEXT_PATH": context_path,
            "JUJU_CHARM": self.meta.name,
            "JUJU_MODEL": self.model.name,
            "JUJU_MODEL_UUID": self.model.uuid,
            "JUJU_APPLICATION": self.app.name,
            "JUJU_UNIT": self.unit.name,
        }

        loki_endpoints = self.loki_consumer.loki_endpoints
        if len(loki_endpoints) > 0:
            environment["SPRING_PROFILES_ACTIVE"] = "production,loki-logging"
            environment["LOKI_PUSH_API_URL"] = loki_endpoints[0].get("url")
        else:
            # When Loki should not be set up, ensure we "zero out" the
            # LOKI_PUSH_API_URL env var to remove its value when combining the
            # new layer with a previous one that did set LOKI_PUSH_API_URL.
            environment["SPRING_PROFILES_ACTIVE"] = "production"

        logger.debug(f"Setting Loki Push API URL to: {environment.get('LOKI_PUSH_API_URL')}")

        updated_pebble_layer = {
            "summary": "application layer",
            "description": "Pebble config layer for the Spring Music application",
            "services": {
                SPRING_MUSIC_SERVICE_NAME: {
                    "override": "replace",
                    "summary": "Spring Music application",
                    "command": "/cnb/process/web",
                    "environment": environment,
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
