"""Avaliação das estimativas: desfaz a normalização, volta para o preço em Cobre e confronta com a linha original.

Caminho de uma previsão até o erro
    yhat normalizado (saída da Dense(7))
      → log-retorno: r = yhat · desvio_h + media_h            (normalizacao.json → "alvo")
      → preço:       p̂ = preco_base · exp(r), arredondado     (Cobre, RN01)
      → real:        linhas_originais[id_linha_origem + h]     (só dias observados; preenchidos e RN03 ficam de fora)

Arquivo de previsões: parquet ou csv com id_amostra e yhat_1 ... yhat_7 na escala normalizada (use salvar_previsoes).

Uso
    python avaliar.py --pasta saida/estudo01 --periodo validacao --previsoes previsoes_validacao.parquet
    python avaliar.py --pasta saida/estudo01 --periodo validacao --ingenuo     # modelo ingênuo (amanhã = hoje)
    python avaliar.py --pasta saida/estudo01 --periodo validacao --verificar   # ida e volta: tem de dar erro zero

Etapa 2c: com itens.parquet na base, o resumo traz "por_grupo" (itens reservados ou não, commodity, apto pela RN15,
líquido pela RN02) e "por_idade" (erro pela idade do item no dia da previsão, para definir o histórico mínimo).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import PERIODOS
from dataset import DadosPreparados

COBRE_POR_OURO = 10_000  # RN01


@dataclass
class Avaliacao:
    detalhe: pd.DataFrame       # uma linha por amostra e por dia do horizonte
    por_item: pd.DataFrame
    por_horizonte: pd.DataFrame
    resumo: dict[str, Any]


def salvar_previsoes(id_amostra: np.ndarray, yhat_normalizado: np.ndarray, caminho: Path) -> None:
    """Grava a saída do modelo com o id de cada amostra, que é o que liga a previsão à linha original."""
    df = pd.DataFrame(yhat_normalizado, columns=[f"yhat_{h}" for h in range(1, yhat_normalizado.shape[1] + 1)])
    df.insert(0, "id_amostra", np.asarray(id_amostra, dtype=np.int64))
    if str(caminho).endswith(".csv"):
        df.to_csv(caminho, index=False)
    else:
        df.to_parquet(caminho, index=False)


def desnormalizar(yhat: np.ndarray, normalizacao: dict[str, Any]) -> np.ndarray:
    media = np.asarray(normalizacao["alvo"]["media"], dtype=np.float64)
    desvio = np.asarray(normalizacao["alvo"]["desvio"], dtype=np.float64)
    return np.asarray(yhat, dtype=np.float64) * desvio + media


def para_cobre(preco_base: np.ndarray, log_retorno: np.ndarray) -> np.ndarray:
    return np.rint(preco_base[:, None].astype(np.float64) * np.exp(log_retorno)).astype(np.int64)


def avaliar(dados: DadosPreparados, periodo: str, id_amostra: np.ndarray, yhat: np.ndarray,
            limiar: Optional[float] = None, metrica: Optional[str] = None,
            minimo_dias: Optional[int] = None) -> Avaliacao:
    H = dados.horizonte
    cfg = dados.normalizacao["config"]
    # Bases preparadas antes da decisão da RN10 só têm "limiar_mape"; a regra nova vale para elas também.
    limiar = float(limiar if limiar is not None else cfg.get("limiar_rn10", cfg.get("limiar_mape", 0.15)))
    metrica = metrica or cfg.get("metrica_rn10", "mdape")
    minimo_dias = int(minimo_dias if minimo_dias is not None else cfg.get("minimo_dias_rn10", 30))
    if metrica not in ("mdape", "mape"):
        raise ValueError("metrica deve ser 'mdape' ou 'mape'")
    jan = dados.janelas(periodo).set_index("id_amostra")
    faltando = np.setdiff1d(id_amostra, jan.index.to_numpy())
    if faltando.size:
        raise KeyError(f"{faltando.size} id_amostra não pertencem a janelas_{periodo} (ex.: {faltando[:5].tolist()})")
    jan = jan.loc[id_amostra]

    base = jan["preco_base"].to_numpy(dtype=np.int64)
    previsto = para_cobre(base, desnormalizar(yhat, dados.normalizacao))
    origem = jan["id_linha_origem"].to_numpy(dtype=np.int64)
    alvo = origem[:, None] + np.arange(1, H + 1)[None, :]

    orig = dados.originais
    serie_o = orig["serie"].to_numpy()
    if not (serie_o[alvo] == serie_o[origem][:, None]).all():
        raise AssertionError("alvo fora da série da amostra: a ordem dos arquivos foi alterada")
    real = orig["preco_cobre"].to_numpy(dtype="float64", na_value=np.nan)[alvo]
    avaliavel = orig["observado"].to_numpy()[alvo] & np.isfinite(real)

    idade = jan["dias_de_historico"].to_numpy() if "dias_de_historico" in jan.columns else np.full(len(jan), -1)
    det = pd.DataFrame({
        "id_amostra": np.repeat(id_amostra, H),
        "id_linha_origem": np.repeat(origem, H),
        "serie": np.repeat(jan["serie"].to_numpy(), H),
        "item_id": np.repeat(jan["item_id"].to_numpy(), H),
        "data_origem": np.repeat(jan["data_origem"].to_numpy(), H),
        "h": np.tile(np.arange(1, H + 1), len(id_amostra)),
        "id_linha_alvo": alvo.ravel(),
        "data_alvo": orig["data"].to_numpy()[alvo].ravel(),
        "preco_base": np.repeat(base, H),
        "preco_real": real.ravel(),
        "preco_previsto": previsto.ravel(),
        "avaliavel": avaliavel.ravel(),
        "dias_de_historico": np.repeat(idade, H),
    })
    det["preco_ingenuo"] = det["preco_base"]
    det["erro_abs"] = (det["preco_previsto"] - det["preco_real"]).abs()
    det["erro_pct"] = det["erro_abs"] / det["preco_real"]
    det["erro_abs_ingenuo"] = (det["preco_ingenuo"] - det["preco_real"]).abs()
    det["erro_pct_ingenuo"] = det["erro_abs_ingenuo"] / det["preco_real"]
    det.loc[~det["avaliavel"], ["erro_abs", "erro_pct", "erro_abs_ingenuo", "erro_pct_ingenuo"]] = np.nan

    ok = det[det["avaliavel"]]
    por_item = ok.groupby(["serie", "item_id"]).agg(
        n=("erro_pct", "size"),
        dias_avaliados=("data_origem", "nunique"),
        mape=("erro_pct", "mean"),
        mape_ingenuo=("erro_pct_ingenuo", "mean"),
        mdape=("erro_pct", "median"),
        mdape_ingenuo=("erro_pct_ingenuo", "median"),
        mae_ouro=("erro_abs", lambda e: e.mean() / COBRE_POR_OURO),
        mae_ingenuo_ouro=("erro_abs_ingenuo", lambda e: e.mean() / COBRE_POR_OURO),
        rmse_ouro=("erro_abs", lambda e: float(np.sqrt((e ** 2).mean())) / COBRE_POR_OURO),
    ).reset_index()
    # Erro relativo ao ingênuo (MAE do modelo ÷ MAE do ingênuo nos mesmos dias): < 1 = melhor que o ingênuo. É livre de
    # escala, como o erro escalado de Hyndman e Athanasopoulos (2018, seção 3.4).
    por_item["erro_relativo_ingenuo"] = por_item["mae_ouro"] / por_item["mae_ingenuo_ouro"].where(
        por_item["mae_ingenuo_ouro"] > 0)
    # Mantido como no relatório da etapa 2: o item "supera o ingênuo" quando o MAPE é menor que o do ingênuo.
    por_item["supera_ingenuo"] = por_item["mape"] < por_item["mape_ingenuo"]
    # RN10: projeção liberada se a métrica do item (MdAPE por padrão) ficar no limiar e abaixo da do modelo ingênuo,
    # com pelo menos `minimo_dias` dias de previsões avaliadas.
    supera_na_metrica = por_item[metrica] < por_item[f"{metrica}_ingenuo"]
    no_limiar = por_item[metrica] <= limiar
    suficiente = por_item["dias_avaliados"] >= minimo_dias
    aprovado = no_limiar & supera_na_metrica
    por_item["situacao"] = np.where(aprovado & suficiente, "Liberada", "Bloqueada")
    por_item["motivo_bloqueio"] = np.select(
        [~suficiente, ~no_limiar, ~supera_na_metrica],
        ["avaliação insuficiente", "acima do limiar", "não supera o ingênuo"], default="")
    por_item = juntar_info_dos_itens(por_item, dados.itens)

    por_h = ok.groupby("h").agg(n=("erro_pct", "size"), mape=("erro_pct", "mean"),
                                mape_ingenuo=("erro_pct_ingenuo", "mean"),
                                mediana_erro_pct=("erro_pct", "median")).reset_index()
    resumo = {
        "periodo": periodo,
        "amostras": int(len(id_amostra)),
        "alvos_avaliados": int(len(ok)),
        "alvos_ignorados_nao_observados": int((~det["avaliavel"]).sum()),
        "itens": int(len(por_item)),
        "mape_medio_por_item": float(por_item["mape"].mean()) if len(por_item) else None,
        "mape_ingenuo_medio_por_item": float(por_item["mape_ingenuo"].mean()) if len(por_item) else None,
        "mape_geral": float(ok["erro_pct"].mean()) if len(ok) else None,
        "itens_que_superam_ingenuo": int(por_item["supera_ingenuo"].sum()),
        "rn10": {"metrica": metrica, "limiar": limiar, "minimo_dias": minimo_dias},
        "itens_liberados_rn10": int((por_item["situacao"] == "Liberada").sum()),
        "itens_liberados_rn10_sem_minimo_de_dias": int(aprovado.sum()),
        "itens_com_avaliacao_insuficiente": int((~suficiente).sum()),
        "mediana_mape_por_item": float(por_item["mape"].median()) if len(por_item) else None,
        "mediana_mdape_por_item": float(por_item["mdape"].median()) if len(por_item) else None,
        "mediana_erro_relativo_ingenuo": float(por_item["erro_relativo_ingenuo"].median()) if len(por_item) else None,
        "itens_com_erro_relativo_menor_que_1": int((por_item["erro_relativo_ingenuo"] < 1).sum()),
        # Quantos itens seriam liberados com outras métricas e limiares (sempre exigindo superar o ingênuo na mesma
        # métrica). Serve para decidir a RN10; não muda a situação calculada acima.
        "liberacao_por_limiar": curva_de_liberacao(por_item),
    }
    grupos = resumo_por_grupo(por_item)
    if grupos:
        resumo["por_grupo"] = grupos
    if (idade >= 0).any():
        resumo["por_idade"] = resumo_por_idade(ok)
    return Avaliacao(det, por_item, por_h, resumo)


GRUPOS = ("reservado", "commodity", "apto_rn15", "liquido_rn02")
# Idade do item (dias desde o primeiro registro) no dia da previsão. A primeira amostra de um item sai por volta do
# 60º dia: 30 dias até a padronização móvel valer (RN24) mais a janela de 30 dias.
FAIXAS_IDADE: tuple[tuple[int, float, str], ...] = ((0, 90, "até 89 dias"), (90, 120, "90 a 119 dias"),
                                                    (120, 180, "120 a 179 dias"), (180, 365, "180 a 364 dias"),
                                                    (365, np.inf, "365 dias ou mais"))


def juntar_info_dos_itens(por_item: pd.DataFrame, itens: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Acrescenta ao resultado por item os critérios de seleção e a reserva (itens.parquet), quando existirem."""
    if itens is None or por_item.empty:
        return por_item
    cols = [c for c in GRUPOS if c in itens.columns]
    info = itens[["serie", "item_id"] + cols].astype({"serie": str})
    out = por_item.astype({"serie": str}).merge(info, on=["serie", "item_id"], how="left")
    return out


def resumo_do_grupo(pi: pd.DataFrame) -> dict[str, Any]:
    n = int(len(pi))
    if not n:
        return {"itens": 0}
    rel = pi["erro_relativo_ingenuo"]
    liberados = int((pi["situacao"] == "Liberada").sum())
    return {
        "itens": n,
        "mediana_mdape_por_item": float(pi["mdape"].median()),
        "mediana_mdape_ingenuo_por_item": float(pi["mdape_ingenuo"].median()),
        "mediana_mape_por_item": float(pi["mape"].median()),
        "mediana_erro_relativo_ingenuo": float(rel.median()) if rel.notna().any() else None,
        "itens_com_erro_relativo_menor_que_1": int((rel < 1).sum()),
        "pct_erro_relativo_menor_que_1": round(float((rel < 1).sum()) / n, 4),
        "itens_liberados_rn10": liberados,
        "pct_liberados_rn10": round(liberados / n, 4),
    }


def resumo_por_grupo(por_item: pd.DataFrame) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for col in GRUPOS:
        if col not in por_item.columns or por_item[col].isna().all():
            continue
        valores = por_item[col].astype("object").where(por_item[col].notna(), "desconhecido")
        out[col] = {str(v): resumo_do_grupo(por_item[valores == v]) for v in sorted(valores.unique(), key=str)}
    return out


def resumo_por_idade(ok: pd.DataFrame) -> list[dict[str, Any]]:
    """Erro de todos os alvos avaliados, por faixa de idade do item no dia da previsão (mediana sobre os alvos)."""
    linhas: list[dict[str, Any]] = []
    for ini, fim, rotulo in FAIXAS_IDADE:
        f = ok[(ok["dias_de_historico"] >= ini) & (ok["dias_de_historico"] < fim)]
        if f.empty:
            linhas.append({"faixa": rotulo, "alvos": 0})
            continue
        md, md_ing = float(f["erro_pct"].median()), float(f["erro_pct_ingenuo"].median())
        linhas.append({"faixa": rotulo, "alvos": int(len(f)), "itens": int(f["item_id"].nunique()),
                       "mdape": md, "mdape_ingenuo": md_ing, "razao_ingenuo": md / md_ing if md_ing > 0 else None})
    return linhas


LIMIARES = (0.10, 0.15, 0.20, 0.25, 0.30)


def curva_de_liberacao(por_item: pd.DataFrame) -> dict[str, dict[str, int]]:
    curva: dict[str, dict[str, int]] = {}
    for metrica in ("mape", "mdape"):
        melhor = por_item[metrica] < por_item[f"{metrica}_ingenuo"]
        curva[metrica] = {f"{round(lim * 100)}%": int(((por_item[metrica] <= lim) & melhor).sum()) for lim in LIMIARES}
    return curva


def gravar(av: Avaliacao, pasta: Path, rotulo: str) -> None:
    base = pasta / f"avaliacao_{av.resumo['periodo']}_{rotulo}"
    av.detalhe.to_parquet(f"{base}_detalhe.parquet", index=False)
    av.por_item.to_csv(f"{base}_itens.csv", index=False)
    av.por_horizonte.to_csv(f"{base}_horizontes.csv", index=False)
    Path(f"{base}_resumo.json").write_text(json.dumps(av.resumo, indent=2, ensure_ascii=False), encoding="utf-8")


def ler_previsoes(caminho: Path, horizonte: int) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(caminho) if str(caminho).endswith(".csv") else pd.read_parquet(caminho)
    cols = [f"yhat_{h}" for h in range(1, horizonte + 1)]
    return df["id_amostra"].to_numpy(dtype=np.int64), df[cols].to_numpy(dtype=np.float64)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--periodo", choices=PERIODOS, default="validacao")
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--previsoes", type=Path, help="parquet/csv com id_amostra e yhat_1..yhat_7 (normalizados)")
    modo.add_argument("--ingenuo", action="store_true", help="avalia o modelo ingênuo (preço de hoje para os 7 dias)")
    modo.add_argument("--verificar", action="store_true", help="usa o próprio y verdadeiro: confere o mecanismo")
    ap.add_argument("--limiar", "--limiar-mape", dest="limiar", type=float,
                    help="RN10; padrão: o de normalizacao.json (15%%)")
    ap.add_argument("--metrica", choices=["mdape", "mape"], help="RN10; padrão: mdape")
    ap.add_argument("--minimo-dias", type=int, help="RN10: dias mínimos de previsões avaliadas; padrão: 30 (0 = sem mínimo)")
    ap.add_argument("--rotulo", help="sufixo dos arquivos de saída")
    args = ap.parse_args(argv)

    dados = DadosPreparados(args.pasta)
    jan = dados.janelas(args.periodo)
    if args.previsoes:
        ids, yhat = ler_previsoes(args.previsoes, dados.horizonte)
        rotulo = args.rotulo or args.previsoes.stem
    elif args.ingenuo:
        ids = jan["id_amostra"].to_numpy(dtype=np.int64)
        alvo = dados.normalizacao["alvo"]
        zero = (0.0 - np.asarray(alvo["media"])) / np.asarray(alvo["desvio"])  # log-retorno 0, já normalizado
        yhat = np.tile(zero, (len(ids), 1))
        rotulo = args.rotulo or "ingenuo"
    else:
        ids = jan["id_amostra"].to_numpy(dtype=np.int64)
        yhat = jan[dados.colunas_alvo()].to_numpy(dtype=np.float64)
        rotulo = args.rotulo or "verificacao"

    av = avaliar(dados, args.periodo, ids, yhat, args.limiar, args.metrica, args.minimo_dias)
    gravar(av, args.pasta, rotulo)
    print(json.dumps(av.resumo, indent=2, ensure_ascii=False))
    print(av.por_horizonte.to_string(index=False))
    if args.verificar:
        ok = av.detalhe[av.detalhe["avaliavel"]]
        pior = float(ok["erro_pct"].max()) if len(ok) else 0.0
        print(f"\nVerificação de ida e volta: maior erro relativo = {pior:.2e} "
              f"({'OK' if pior < 1e-5 else 'FALHOU'}; o resto vem do y gravado em float32)")
        return 0 if pior < 1e-5 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
