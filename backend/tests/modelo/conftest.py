"""
Testes do pipeline do CU11 (serviço `modelo`). Precisam de pandas e TensorFlow, que só existem na imagem do serviço:
no host, cada módulo é ignorado por `pytest.importorskip`. Rode com `docker compose run --rm modelo-testes` (a partir
de backend/). Este arquivo não importa pandas, para a coleta no host continuar funcionando.
"""
from datetime import datetime, timedelta, timezone

import pytest


class RelogioFixo:
    """Relógio dos treinamentos: o banco grava as datas do pedido, do início e do fim."""

    def __init__(self) -> None:
        self.agora = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, **duracao: float) -> None:
        self.agora += timedelta(**duracao)


@pytest.fixture
def relogio() -> RelogioFixo:
    return RelogioFixo()
