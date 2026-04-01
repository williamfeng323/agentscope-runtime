# -*- coding: utf-8 -*-
import logging
from .docker_client import DockerClient

logger = logging.getLogger(__name__)


class GVisorDockerClient(DockerClient):
    """
    A DockerClient that enforces gVisor runtime (`runsc`).
    """

    def create(
        self,
        image,
        name=None,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        if runtime_config is None:
            runtime_config = {}

        runtime_config["runtime"] = "runsc"

        logger.debug(
            f"[GVisorDockerClient] Forcing runtime=runsc for image {image}",
        )

        return super().create(
            image=image,
            name=name,
            ports=ports,
            volumes=volumes,
            environment=environment,
            runtime_config=runtime_config,
        )


def get_gvisor_kubernetes_client_cls():
    """Return the GVisorKubernetesClient class using lazy import."""
    from .kubernetes_client import KubernetesClient

    class GVisorKubernetesClient(KubernetesClient):
        """A KubernetesClient that enforces gVisor via ``runtimeClassName: gvisor``.

        On a Kubernetes cluster with the gVisor ``RuntimeClass`` installed
        (typically named ``gvisor``), every Pod created by this client will
        have ``spec.runtimeClassName`` set to ``"gvisor"``, so the kubelet
        selects the ``runsc`` container runtime instead of the default one.

        Any ``runtime_class_name`` value already present in ``runtime_config``
        is preserved, which allows callers to override the class name when
        using a custom ``RuntimeClass`` object (e.g. ``"gvisor-co"``).

        .. code-block:: python

            from agentscope_runtime.common.container_clients import (
                GVisorKubernetesClient,
            )

            client = GVisorKubernetesClient(config=sandbox_manager_config)
            client.create(image="my-image:latest", ports=["80/tcp"])

        """

        def create(
            self,
            image,
            name=None,
            ports=None,
            volumes=None,
            environment=None,
            runtime_config=None,
        ):
            """Create a Kubernetes Pod with ``runtimeClassName`` set to ``gvisor``.

            Args:
                image (`str`):
                    Docker image to run.
                name (`str | None`, optional):
                    Desired pod name. Auto-generated when omitted.
                ports (`list | None`, optional):
                    Port specifications forwarded to the parent implementation.
                volumes (`dict | None`, optional):
                    Volume bindings forwarded to the parent implementation.
                environment (`dict | None`, optional):
                    Environment variables forwarded to the parent
                    implementation.
                runtime_config (`dict | None`, optional):
                    Extra Kubernetes runtime options.  ``runtime_class_name``
                    defaults to ``"gvisor"`` when not explicitly provided.

            Returns:
                `tuple`:
                    A ``(container_id, ports, ip_address)`` tuple as returned
                    by :meth:`KubernetesClient.create`.
            """
            if runtime_config is None:
                runtime_config = {}

            runtime_config.setdefault("runtime_class_name", "gvisor")

            logger.debug(
                "[GVisorKubernetesClient] Setting runtimeClassName=%s "
                "for image %s",
                runtime_config["runtime_class_name"],
                image,
            )

            return super().create(
                image=image,
                name=name,
                ports=ports,
                volumes=volumes,
                environment=environment,
                runtime_config=runtime_config,
            )

    return GVisorKubernetesClient
