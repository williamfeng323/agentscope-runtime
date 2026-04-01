# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""Unit tests for GVisorKubernetesClient and runtimeClassName pod-spec support."""

from unittest.mock import MagicMock, patch

import pytest

from agentscope_runtime.common.container_clients import ContainerClientFactory
from agentscope_runtime.common.container_clients.gvisor_client import (
    get_gvisor_kubernetes_client_cls,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_K8S_CONFIG_MODULE = (
    "agentscope_runtime.common.container_clients.kubernetes_client.k8s_config"
)
_K8S_CLIENT_MODULE = (
    "agentscope_runtime.common.container_clients.kubernetes_client.client"
)


def _make_sandbox_config(namespace="default"):
    cfg = MagicMock()
    cfg.k8s_namespace = namespace
    cfg.kubeconfig_path = None
    return cfg


def _mock_k8s_patches():
    """Return a list of patches that prevent any real K8s API calls."""
    mock_core_v1 = MagicMock()
    mock_core_v1.list_namespace.return_value = MagicMock()

    mock_apps_v1 = MagicMock()

    patches = [
        patch(_K8S_CONFIG_MODULE),
        patch(f"{_K8S_CLIENT_MODULE}.CoreV1Api", return_value=mock_core_v1),
        patch(f"{_K8S_CLIENT_MODULE}.AppsV1Api", return_value=mock_apps_v1),
    ]
    return patches


def _start_k8s_patches():
    started = [p.start() for p in _mock_k8s_patches()]
    return started


def _stop_patches(patches):
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# KubernetesClient._create_pod_spec – runtimeClassName
# ---------------------------------------------------------------------------


class TestKubernetesClientRuntimeClassName:
    """Tests for runtime_class_name support in KubernetesClient."""

    @pytest.fixture()
    def k8s_client(self):
        patches = _mock_k8s_patches()
        for p in patches:
            p.start()
        from agentscope_runtime.common.container_clients.kubernetes_client import (
            KubernetesClient,
        )

        client = KubernetesClient(config=_make_sandbox_config())
        yield client
        for p in patches:
            p.stop()

    def test_runtime_class_name_set_in_pod_spec(self, k8s_client):
        """runtime_config['runtime_class_name'] must be reflected in PodSpec."""
        pod_spec = k8s_client._create_pod_spec(
            image="my-image:latest",
            name="test-pod",
            runtime_config={"runtime_class_name": "gvisor"},
        )
        assert pod_spec.runtime_class_name == "gvisor"

    def test_runtime_class_name_custom_value(self, k8s_client):
        """Any string value for runtime_class_name should be accepted."""
        pod_spec = k8s_client._create_pod_spec(
            image="my-image:latest",
            name="test-pod",
            runtime_config={"runtime_class_name": "kata-containers"},
        )
        assert pod_spec.runtime_class_name == "kata-containers"

    def test_runtime_class_name_absent_when_not_specified(self, k8s_client):
        """PodSpec.runtime_class_name must be None when not in runtime_config."""
        pod_spec = k8s_client._create_pod_spec(
            image="my-image:latest",
            name="test-pod",
            runtime_config={},
        )
        assert pod_spec.runtime_class_name is None

    def test_runtime_class_name_coexists_with_other_options(self, k8s_client):
        """Other runtime_config keys must still work alongside runtime_class_name."""
        pod_spec = k8s_client._create_pod_spec(
            image="my-image:latest",
            name="test-pod",
            runtime_config={
                "runtime_class_name": "gvisor",
                "node_selector": {"kubernetes.io/arch": "amd64"},
                "restart_policy": "OnFailure",
            },
        )
        assert pod_spec.runtime_class_name == "gvisor"
        assert pod_spec.node_selector == {"kubernetes.io/arch": "amd64"}
        assert pod_spec.restart_policy == "OnFailure"


# ---------------------------------------------------------------------------
# GVisorKubernetesClient
# ---------------------------------------------------------------------------


class TestGVisorKubernetesClient:
    """Tests for the GVisorKubernetesClient factory and create() behaviour."""

    @pytest.fixture()
    def gvisor_k8s_client(self):
        patches = _mock_k8s_patches()
        for p in patches:
            p.start()
        GVisorKubernetesClient = get_gvisor_kubernetes_client_cls()
        client = GVisorKubernetesClient(config=_make_sandbox_config())
        yield client
        for p in patches:
            p.stop()

    def test_inherits_from_kubernetes_client(self):
        """GVisorKubernetesClient must be a subclass of KubernetesClient."""
        patches = _mock_k8s_patches()
        for p in patches:
            p.start()
        try:
            from agentscope_runtime.common.container_clients.kubernetes_client import (  # noqa: E501
                KubernetesClient,
            )

            GVisorKubernetesClient = get_gvisor_kubernetes_client_cls()
            assert issubclass(GVisorKubernetesClient, KubernetesClient)
        finally:
            for p in patches:
                p.stop()

    def test_default_runtime_class_name_is_gvisor(self, gvisor_k8s_client):
        """create() must inject runtime_class_name='gvisor' by default."""
        from agentscope_runtime.common.container_clients.kubernetes_client import (
            KubernetesClient,
        )

        captured = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return ("cid-1", [18080], "127.0.0.1")

        with patch.object(KubernetesClient, "create", side_effect=fake_create):
            gvisor_k8s_client.create(image="my-image:latest")

        assert (
            captured.get("runtime_config", {}).get("runtime_class_name") == "gvisor"
        )

    def test_caller_can_override_runtime_class_name(self, gvisor_k8s_client):
        """Callers providing runtime_class_name must not be overridden."""
        from agentscope_runtime.common.container_clients.kubernetes_client import (
            KubernetesClient,
        )

        captured = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return ("cid-1", [18080], "127.0.0.1")

        with patch.object(KubernetesClient, "create", side_effect=fake_create):
            gvisor_k8s_client.create(
                image="my-image:latest",
                runtime_config={"runtime_class_name": "gvisor-co"},
            )

        assert (
            captured.get("runtime_config", {}).get("runtime_class_name") == "gvisor-co"
        )

    def test_none_runtime_config_initialised_correctly(self, gvisor_k8s_client):
        """When runtime_config=None, create() must build a fresh dict with gvisor."""
        from agentscope_runtime.common.container_clients.kubernetes_client import (
            KubernetesClient,
        )

        captured = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return ("cid-1", [18080], "127.0.0.1")

        with patch.object(KubernetesClient, "create", side_effect=fake_create):
            gvisor_k8s_client.create(image="my-image:latest", runtime_config=None)

        assert captured["runtime_config"]["runtime_class_name"] == "gvisor"

    def test_other_runtime_config_keys_preserved(self, gvisor_k8s_client):
        """Extra runtime_config keys must pass through unchanged."""
        from agentscope_runtime.common.container_clients.kubernetes_client import (
            KubernetesClient,
        )

        captured = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return ("cid-1", [18080], "127.0.0.1")

        with patch.object(KubernetesClient, "create", side_effect=fake_create):
            gvisor_k8s_client.create(
                image="my-image:latest",
                runtime_config={"node_selector": {"role": "sandbox"}},
            )

        rc = captured.get("runtime_config", {})
        assert rc.get("runtime_class_name") == "gvisor"
        assert rc.get("node_selector") == {"role": "sandbox"}


# ---------------------------------------------------------------------------
# ContainerClientFactory
# ---------------------------------------------------------------------------


class TestContainerClientFactoryGVisorK8s:
    """Tests for 'gvisor_k8s' deployment type in ContainerClientFactory."""

    def test_factory_creates_gvisor_kubernetes_client(self):
        """ContainerClientFactory must return a GVisorKubernetesClient for 'gvisor_k8s'."""
        patches = _mock_k8s_patches()
        for p in patches:
            p.start()
        try:
            from agentscope_runtime.common.container_clients.kubernetes_client import (  # noqa: E501
                KubernetesClient,
            )

            cfg = _make_sandbox_config()
            client = ContainerClientFactory.create_client("gvisor_k8s", cfg)
            assert isinstance(client, KubernetesClient)
            assert type(client).__name__ == "GVisorKubernetesClient"
        finally:
            for p in patches:
                p.stop()

    def test_factory_unknown_type_raises(self):
        """ContainerClientFactory must raise NotImplementedError for unknown types."""
        with pytest.raises(NotImplementedError):
            ContainerClientFactory.create_client("unknown_backend", MagicMock())

