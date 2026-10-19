"""CU11 (RN25): artefatos de cada versão do modelo, em `modelos/v{versao}/`.

- `modelo.keras`: a rede treinada;
- `normalizacao.json`: datas de corte, constantes, vocabulário, escala do alvo, variáveis e assinatura. Para prever
  com uma versão, use sempre as constantes dela;
- `treino.json`: parâmetros, épocas, tempos, contagens e o resumo da avaliação no período de teste;
- `avaliacao_teste.parquet`: as métricas e a situação de cada item elegível nessa versão.

Os arquivos são gravados numa pasta temporária e só ganham o nome da versão no passo 11, antes do commit. Se o registro
falhar, a pasta é removida (CU11-C1-FE1 e FE2: o modelo em treinamento é descartado).
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional

import pandas as pd

ARQUIVO_MODELO = "modelo.keras"
ARQUIVO_NORMALIZACAO = "normalizacao.json"
ARQUIVO_TREINO = "treino.json"
ARQUIVO_AVALIACAO = "avaliacao_teste.parquet"


def pasta_dos_modelos() -> Path:
    """MODELO_PASTA (padrão `modelos`, relativo à pasta de trabalho do serviço: /app/modelos no container)."""
    return Path(os.getenv("MODELO_PASTA", "").strip() or "modelos")


class Artefatos:
    def __init__(self, raiz: Path, id_execucao: int) -> None:
        self.raiz = Path(raiz)
        self.temporaria = self.raiz / f".execucao-{id_execucao}"
        self.publicada: Optional[Path] = None

    def iniciar(self) -> Path:
        if self.temporaria.exists():
            shutil.rmtree(self.temporaria)
        self.temporaria.mkdir(parents=True)
        return self.temporaria

    def gravar_json(self, nome: str, conteudo: dict[str, Any]) -> None:
        (self.temporaria / nome).write_text(json.dumps(conteudo, indent=2, ensure_ascii=False, default=str),
                                            encoding="utf-8")

    def gravar_avaliacao(self, por_item: pd.DataFrame) -> None:
        por_item.to_parquet(self.temporaria / ARQUIVO_AVALIACAO, index=False)

    def publicar(self, versao: int) -> Path:
        """Dá à pasta temporária o nome da versão (passo 11)."""
        destino = self.raiz / f"v{versao}"
        if destino.exists():
            raise FileExistsError(f"{destino} já existe: a pasta de modelos não corresponde ao banco")
        os.replace(self.temporaria, destino)
        self.publicada = destino
        return destino

    def confirmar(self) -> None:
        """Depois do commit do passo 11: a pasta publicada pertence à versão registrada e não é mais descartada."""
        self.publicada = None

    def descartar(self) -> None:
        """Remove o que foi gravado nesta execução (a pasta temporária ou a já publicada, se o commit falhou)."""
        for pasta in (self.temporaria, self.publicada):
            if pasta is not None and pasta.exists():
                shutil.rmtree(pasta, ignore_errors=True)
        self.publicada = None
