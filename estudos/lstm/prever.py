"""Previsão com um modelo já treinado sobre outra base (etapa 2c): é o que o sistema fará com um item qualquer.

O modelo não sabe qual item está prevendo: recebe a janela de 30 dias já normalizada e os atributos do item. Então
basta preparar a base dos itens novos com a MESMA normalização da versão do modelo
(`preparar_dados.py --normalizacao-de <base do treino>`) e passar as janelas pelo modelo. O script confere a
assinatura da normalização antes de prever e recusa uma base incompatível.

Só prevê a validação: o teste é usado uma única vez, no CU11 (RN25).

Uso
    python prever.py --modelo saida/treino2c/modelos/c_todos_s42 --pasta saida/fora2c --rotulo c_todos_s42
    python avaliar.py --pasta saida/fora2c --periodo validacao --previsoes saida/fora2c/previsoes_validacao_c_todos_s42.parquet
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from avaliar import salvar_previsoes
from dataset import DadosPreparados, assinatura_normalizacao


def conferir_compatibilidade(norm_modelo: dict[str, Any], norm_base: dict[str, Any]) -> None:
    """A base precisa ter sido normalizada exatamente como a versão do modelo (cortes, constantes, vocabulário, alvo,
    variáveis, janela e horizonte)."""
    a, b = assinatura_normalizacao(norm_modelo), assinatura_normalizacao(norm_base)
    if a != b:
        raise ValueError(f"normalização incompatível (modelo {a}, base {b}): prepare a base com "
                         "preparar_dados.py --normalizacao-de <pasta da base do treino>")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", type=Path, required=True, help="pasta do modelo (modelo.keras e normalizacao.json)")
    ap.add_argument("--pasta", type=Path, required=True, help="base preparada com --normalizacao-de")
    ap.add_argument("--periodo", choices=["validacao"], default="validacao")
    ap.add_argument("--rotulo", help="sufixo do arquivo de previsões (padrão: nome da pasta do modelo)")
    args = ap.parse_args(argv)

    import keras

    from treinar import prever

    norm_modelo = json.loads((args.modelo / "normalizacao.json").read_text(encoding="utf-8"))
    dados = DadosPreparados(args.pasta)
    conferir_compatibilidade(norm_modelo, dados.normalizacao)
    modelo = keras.models.load_model(args.modelo / "modelo.keras", compile=False)
    jan = dados.janelas(args.periodo)
    ids, yhat = prever(modelo, dados, jan)
    rotulo = args.rotulo or args.modelo.name
    destino = args.pasta / f"previsoes_{args.periodo}_{rotulo}.parquet"
    salvar_previsoes(ids, yhat, destino)
    print(f"{len(ids):,} previsões de {jan['item_id'].nunique():,} itens em {destino}. Avalie com:\n"
          f"  python avaliar.py --pasta {args.pasta} --periodo {args.periodo} --previsoes {destino} --rotulo {rotulo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
