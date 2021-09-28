# Spring Music Charm

<img src="images/spring-boot+juju.png" style="width: 30%; float: right"/>

This repository is a fork of Spring Music, a famous Spring Boot demo application, together with a charmed operator that enable [Juju](https://juju.is) to run the application on top of Kubernetes.

The Spring Music charm operators integrates with other charmed operators, [Prometheus](https://charmhub.io/prometheus-k8s) and [Grafana](https://charmhub.io/grafana-k8s) to expose and consume the metrics made available by the [Spring Boot Actuator](https://docs.spring.io/spring-boot/docs/current/reference/htmlsingle/#actuator).
<div style="clear: both"></div>

## Setup

These instructions are tailored to an Ubuntu 20.04 or later environment, although [`snap`](https://snapcraft.io/about) supports tons of different Linux distributions.

### Install MicroK8s

Install MicroK8s with the following add ons: `storage`, `dns`, `registry`:

```sh
snap install microk8s
microk8s enable storage dns registry
```

### Install Juju

```sh
snap install juju
```

### Install Charmcraft and LXD

```sh
snap install charmcraft
```

The `charmcraft pack` command relies on [LXD](https://linuxcontainers.org/lxd/introduction/) to build charms in a safe and reproducible way.
Install LXD on your machine as follows:

```
snap install lxd
lxd init --minimal
```

### Bootstrap a Juju MicroK8s controller

```sh
juju bootstrap microk8s development
```

## Build

### Building the Spring Music container image

Assuming you are using MicroK8s with the `registry` add on, build the OCI image of the Spring Music application with:

```sh
./gradlew bootBuildImage --imageName=localhost:32000/spring-music:latest
docker push localhost:32000/spring-music:latest
```

The `localhost:32000` is the location of the registry integrated in MicroK8s.

### Building the Spring Music charm

```sh
charmcraft pack
```

## Deploy the Spring Music application

```sh
juju add-model spring
juju deploy ./spring-music_ubuntu-20.04-amd64.charm spring-music --resource application-image=localhost:32000/spring-music
```

Alternatively, the `./build_and_deploy_charm` automates the build and deploy (or refresh) of the charm in a model:

```sh
./juju_utils/build_and_deploy_charm spring spring-music
```

## Deploy the LMA bundle

Follow the [LMA Light on MicroK8s](https://juju.is/docs/lma2/on%20MicroK8s) tutorial together with the [offers overlay](https://github.com/canonical/lma-light-bundle/blob/main/overlays/offers-overlay.yaml).

## Enable the monitoring of Spring Music

```
juju switch spring
juju consume lma.prometheus-scrape prometheus
juju consume lma.grafana-dashboards grafana
juju add-relation spring-music prometheus
juju add-relation spring-music grafana
```

## Utility scripts

In the `./juju_utils/` folder there are three utility scripts to streamline some common development tasks:

### build_and_deploy_charm

The `./juju_utils/build_and_deploy_charm` bash script automates the creation of the charm (i.e., `charmcraft pack`) and its deployment or the update of the application; it accepts two additional, optional arguments, the first for the model in which to deploy, and the second the application name:

```sh
./juju_utils/build_and_deploy_charm <model> <application>
```

The default model is `spring`, and the default application name is `spring-music`

**Important:** The `./juju_utils/build_and_deploy_charm` bash script does **not** build the OCI image for the Spring Music application, nor it uploads it to the local MicroK8s registry.
Refer to the [Building the Spring Music container image](#building-the-spring-music-container-image) for instructions on how to ensure that the OCI image for the Spring Music application is available in the local MicroK8s registry.

### juju-unit-address

The `./juju_utils/juju-unit-address` bash script outputs the address and port of the provided Juju unit:

```sh
./juju_utils/juju-unit-address <model>.<application>/<unit_id>
```

For example:

```sh
$ ./juju_utils/juju-unit-address lma.prometheus/0
10.1.151.75:9090
```

### browse-juju-unit

The `./juju_utils/browse-juju-unit` bash script opens the address and port of the provided Juju unit in Firefox:

```sh
./juju_utils/browse-juju-unit <model>.<application>/<unit_id>
```

For example:

```sh
./juju_utils/browse-juju-unit lma.prometheus/0
```

would result in Firefox opening something like the `10.1.151.75:9090` address.

## Development

### Where is the charm code?

To play nice with Maven and Gradle, the charm code is located in directories that different than in "normal" charm repository (e.g., what `charmcraft init` sets up for you):

* Charm code in `src/main/charm`
* Charm yaml files and additional file-based resources, including the "original" `metadata.yaml` in `src/main/charm_resources`
* Charm libraries in `src/main/charm_libs`
* Charm tests in `src/test/charm`

Achieving the above required the following adjustments:

* Much "priming" and a custom `charm-entrypoint` in [`charmcraft.yaml`](./charmcraft.yaml)
* A custom [`dispatch`](./dispatch) script to ensure that the charm libraries are visible in the Charm container
* A number of edits to the standard [`tox.ini`](./tox.ini)
* A symlink from `src/main/charm_resources/metadata.yaml` to `metadata.yaml` for `charmcraft pack`'s benefit
* A symlink from `lib/charms` to `src/main/charm_libs` for `charmcraft fetch-lib`'s benefit
