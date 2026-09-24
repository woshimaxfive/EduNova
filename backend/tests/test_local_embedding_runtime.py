from unittest.mock import Mock

import pytest

from backend.app.core.config import Settings
from backend.app.providers.local_embeddings import LocalEmbeddingProvider, MODEL_FILES, MODEL_REVISION
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelSettingsService, ModelNotConfiguredError
from backend.tests.test_model_settings import FakeModelSettingsRepository, ImmediateExecutionRuntime, make_user


def make_service(path, **kwargs):
    return ModelSettingsService(
        FakeModelSettingsRepository({}),
        Settings(_env_file=None, system_embedding_provider="fastembed_local",
                 local_embedding_model_dir=str(path), **kwargs),
        provider=Mock(), execution_runtime=ImmediateExecutionRuntime(),
    )


def prepare_files(path):
    for name in MODEL_FILES:
        (path / name).write_bytes(b"synthetic")


def test_default_local_retrieval_ignores_stale_rerank_credentials(tmp_path):
    settings = Settings(_env_file=None, local_embedding_model_dir=str(tmp_path),
                        system_rerank_provider="bailian_rerank", system_rerank_api_key="synthetic-old",
                        system_rerank_base_url="https://example.com", system_rerank_model="old")
    service = ModelSettingsService(FakeModelSettingsRepository({}), settings, provider=Mock())
    assert service.resolve_embedding_runtime_config(make_user()).provider == "fastembed_local"
    rerank = service.resolve_rerank_runtime_config(make_user())
    assert not rerank.can_use_model and rerank.api_key is None


def test_local_missing_weights_never_borrows_cloud_credentials(tmp_path):
    service = make_service(tmp_path, system_model_api_key="synthetic-cloud-secret")
    runtime = service.resolve_embedding_runtime_config(make_user())
    assert runtime.provider == "fastembed_local" and not runtime.can_use_model
    assert runtime.api_key is None and runtime.base_url is None
    with pytest.raises(ModelNotConfiguredError):
        service.embedding_vectors(make_user(), ["合成资料"])
    service.provider.embed_texts.assert_not_called()
    assert EmbeddingService(service).embed_query(make_user(), "查询").status == "local_fallback"


@pytest.mark.parametrize("input_type", ["query", "document"])
def test_local_runtime_routes_without_key_and_binds_revision(tmp_path, monkeypatch, input_type):
    prepare_files(tmp_path)
    monkeypatch.setattr("importlib.util.find_spec", lambda name: object())
    embed = Mock(return_value=[[1.0] * 512])
    monkeypatch.setattr(LocalEmbeddingProvider, "embed", embed)
    service = make_service(tmp_path)
    runtime = service.resolve_embedding_runtime_config(make_user())
    assert runtime.can_use_model and MODEL_REVISION in runtime.embedding_model
    assert runtime.dimensions == 512 and runtime.api_key is None
    service.embedding_vectors(make_user(), ["合成资料"], input_type=input_type)
    assert embed.call_args.kwargs["input_type"] == input_type
    service.provider.embed_texts.assert_not_called()


def test_local_corrupt_weights_fail_without_cloud_fallback(tmp_path, monkeypatch):
    prepare_files(tmp_path)
    monkeypatch.setattr("importlib.util.find_spec", lambda name: object())
    service = make_service(tmp_path)
    with pytest.raises(ModelProviderError, match="校验失败"):
        service.embedding_vectors(make_user(), ["合成资料"])
    service.provider.embed_texts.assert_not_called()


def test_local_profile_does_not_depend_on_host_path_or_main_key(tmp_path, monkeypatch):
    monkeypatch.setattr("importlib.util.find_spec", lambda name: object())
    first = make_service(tmp_path, system_model_api_key="synthetic-one")
    second = make_service(tmp_path / "elsewhere", system_model_api_key="synthetic-two")
    assert (first.resolve_embedding_runtime_config(make_user()).profile_hash
            == second.resolve_embedding_runtime_config(make_user()).profile_hash)
