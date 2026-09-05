from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from exactsource_sft.data import prepare_dataset


class _Count:
    def __init__(self, value: int) -> None:
        self.value = value

    def sum(self) -> _Count:
        return self

    def item(self) -> int:
        return self.value


class _Weights:
    def __gt__(self, _other: object) -> _Count:
        return _Count(32)


class _PreparationRenderer:
    def build_supervised_example(
        self,
        _messages: list[dict[str, str]],
        *,
        train_on_what: object,
    ) -> tuple[SimpleNamespace, _Weights]:
        assert getattr(train_on_what, "name", None) == "LAST_ASSISTANT_MESSAGE"
        return SimpleNamespace(length=512), _Weights()


class _DatumRenderer:
    def __init__(self, length: int) -> None:
        self.length = length
        self.tokenizer = object()

    def build_supervised_example(
        self,
        _messages: list[dict[str, str]],
        *,
        train_on_what: object,
    ):
        import tinker
        import torch

        assert getattr(train_on_what, "name", None) == "LAST_ASSISTANT_MESSAGE"
        model_input = tinker.ModelInput.from_ints([1] * self.length)
        return model_input, torch.ones(self.length)


@pytest.fixture(scope="session")
def fake_formula_verifier() -> Callable[[object, Path, object], str]:
    def verify(_outputs: object, _work_root: Path, _soffice: object) -> str:
        return "LibreOffice test double 1.0"

    return verify


@pytest.fixture
def renderer_factory() -> Callable[[int], object]:
    return _DatumRenderer


@pytest.fixture(scope="session")
def prepared_output(
    tmp_path_factory: pytest.TempPathFactory,
    fake_formula_verifier: Callable[[object, Path, object], str],
) -> Path:
    output = tmp_path_factory.mktemp("prepared")
    manifest = prepare_dataset(
        output_dir=output,
        renderer=_PreparationRenderer(),
        formula_verifier=fake_formula_verifier,
    )
    assert len(manifest["ordered_train_ids"]) == 12
    assert len(manifest["ordered_tune_ids"]) == 4
    return output
