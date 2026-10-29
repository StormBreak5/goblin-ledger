"""Calendário dos dias previstos (etapa 2h): o que se sabe em D sobre D+1 a D+7, como entrada da rede (X_fut).

Hoje as variáveis 9 a 14 só entram com os 30 dias passados. Este script monta, para cada dia de origem D, seis colunas
por dia previsto (D+h, h = 1 a 7), todas só da data e de evento_jogo, sem preço:

    fut_dia_sin, fut_dia_cos   dia da semana de D+h (a mesma variável 9, calculada em D+h)
    fut_patch                  1 se algum patch cai entre D+1 e D+h (a lista de patches das variáveis 10 e 11)
    fut_expansao               1 se algum marco de expansão (pré-patch ou lançamento) cai entre D+1 e D+h (variável 12)
    fut_temporada              1 se alguma temporada começa entre D+1 e D+h (variável 13)
    fut_evento                 1 se algum evento sazonal está ativo em D+h (a variável 14 agregada, calculada em D+h)

RN25: um patch só é conhecido `antecedencia_anuncio_dias` (14) antes da data. Como D+h fica a no máximo `horizonte` (7)
dias, todo patch do horizonte já é conhecido em D; o script recusa um horizonte maior que a antecedência. O calendário
dos festivais e das temporadas é conhecido antecipadamente, como no resto do estudo. Nenhuma coluna olha além de D+7, e
nenhuma constante é ajustada (os valores já ficam entre −1 e 1), então o período de teste não influencia nada.

Antes de gravar, as variáveis 9 a 14 são recalculadas com os eventos lidos agora e comparadas com as da base: se não
baterem, os eventos mudaram depois da preparação da base, e o script para.

Arquivos (em --saida)
    calendario_futuro.parquet  uma linha por região e dia de origem: as colunas fut_<variável>_h<h> e
                               com_evento_no_horizonte (patch, marco, início de temporada ou início/fim de evento
                               sazonal entre D+1 e D+7; usado por eventos_no_horizonte.py)
    calendario_futuro.json     colunas, horizonte, a conferência, as amostras com cada coluna diferente de zero e a
                               assinatura do calendário

Uso
    python calendario_futuro.py --banco --pasta saida/treino01_agr --saida saida/calendario2h
    python calendario_futuro.py --csv dados_sinteticos --pasta saida/sintetico --saida saida/sintetico_cal
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import PERIODOS, Config
from dataset import assinatura_normalizacao
from preparar_dados import datas_de_patch_e_marcos, variaveis_de_calendario

logger = logging.getLogger("calendario_futuro")

COLUNAS_FUTURAS: tuple[str, ...] = ("fut_dia_sin", "fut_dia_cos", "fut_patch", "fut_expansao", "fut_temporada",
                                    "fut_evento")
COLUNA_EVENTO_NO_HORIZONTE = "com_evento_no_horizonte"
# Variáveis 9 a 14, na forma agregada: as que a conferência recalcula.
VARIAVEIS_CALENDARIO: tuple[str, ...] = ("f_dia_sin", "f_dia_cos", "f_dias_desde_patch", "f_dias_ate_patch",
                                         "f_expansao", "f_temporada_ativa", "f_dias_temporada", "f_evento")
UM_DIA = np.timedelta64(1, "D")


def colunas(horizonte: int) -> list[str]:
    """Na ordem do tensor [horizonte, variáveis]: primeiro as seis de h1, depois as de h2..."""
    return [f"{c}_h{h}" for h in range(1, horizonte + 1) for c in COLUNAS_FUTURAS]


def _houve_entre(marcas: np.ndarray, d: np.ndarray, alvo: np.ndarray) -> np.ndarray:
    """[n, H]: 1 se alguma das `marcas` cai entre D+1 e D+h."""
    return (np.searchsorted(marcas, alvo, side="right") - np.searchsorted(marcas, d, side="right")[:, None]) > 0


def calcular(datas: pd.DatetimeIndex, eventos: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Etapa 2h / RN25: uma linha por dia de origem D, com as colunas de D+1 a D+horizonte conhecidas em D."""
    H = cfg.horizonte
    if H > cfg.antecedencia_anuncio_dias:
        raise ValueError(f"horizonte de {H} dias passa da antecedência de {cfg.antecedencia_anuncio_dias} dias com que "
                         "um patch é conhecido (RN25): o patch do fim do horizonte ainda não seria conhecido em D")
    d = np.unique(np.asarray(datas.values, dtype="datetime64[D]"))
    alvo = d[:, None] + np.arange(1, H + 1)[None, :] * UM_DIA
    if not d.size:
        return pd.DataFrame(columns=["data", *colunas(H), COLUNA_EVENTO_NO_HORIZONTE])
    # Dia da semana e evento sazonal: as próprias variáveis 9 e 14, calculadas em cada dia de D a D+H.
    grade = pd.DatetimeIndex(np.arange(d.min(), d.max() + (H + 1) * UM_DIA, UM_DIA))
    cal = variaveis_de_calendario(grade, eventos, replace(cfg, eventos_detalhados=False))
    pos_alvo = ((alvo - grade.values[0].astype("datetime64[D]")) / UM_DIA).astype(int)
    pos_d = ((d - grade.values[0].astype("datetime64[D]")) / UM_DIA).astype(int)

    patches, marcos = datas_de_patch_e_marcos(eventos)
    temporadas = eventos.loc[eventos["tipo"] == "TEMPORADA", "data_inicio"].dropna()
    inicios = np.unique(temporadas.values.astype("datetime64[D]"))
    evento = cal["f_evento"].to_numpy()
    blocos = {
        "fut_dia_sin": cal["f_dia_sin"].to_numpy()[pos_alvo],
        "fut_dia_cos": cal["f_dia_cos"].to_numpy()[pos_alvo],
        "fut_patch": _houve_entre(patches, d, alvo),
        "fut_expansao": _houve_entre(marcos, d, alvo),
        "fut_temporada": _houve_entre(inicios, d, alvo),
        "fut_evento": evento[pos_alvo],
    }
    out = pd.DataFrame({f"{c}_h{h}": blocos[c][:, h - 1].astype("float32")
                        for h in range(1, H + 1) for c in COLUNAS_FUTURAS})
    out.insert(0, "data", pd.DatetimeIndex(d))
    muda_evento = (evento[pos_alvo] != evento[pos_d][:, None]).any(axis=1)
    out[COLUNA_EVENTO_NO_HORIZONTE] = (blocos["fut_patch"][:, -1] | blocos["fut_expansao"][:, -1] |
                                       blocos["fut_temporada"][:, -1] | muda_evento)
    return out


def regiao_da_serie(pasta: Path) -> dict[str, str]:
    """Série → região, de linhas_originais.parquet (só as duas colunas)."""
    o = pd.read_parquet(Path(pasta) / "linhas_originais.parquet", columns=["serie", "regiao"]).drop_duplicates("serie")
    return dict(zip(o["serie"].astype(str), o["regiao"].astype(str)))


def _eventos_da_regiao(eventos: pd.DataFrame, regiao: str) -> pd.DataFrame:
    return eventos[eventos["regiao"].isin(["GLOBAL", regiao])]


def conferir(pasta: Path, eventos: pd.DataFrame, cfg: Config) -> dict[str, Any]:
    """As variáveis 9 a 14 recalculadas com `eventos` têm de ser as da base, em todas as datas e regiões. Uma diferença
    quer dizer que evento_jogo mudou depois da preparação: o calendário futuro não seria o que a rede viu no passado."""
    pasta = Path(pasta)
    norm = pd.read_parquet(pasta / "linhas_normalizadas.parquet", columns=["serie", "data", *VARIAVEIS_CALENDARIO])
    regiao = norm["serie"].astype(str).map(regiao_da_serie(pasta))
    diferencas: dict[str, list[str]] = {}
    datas_conferidas = 0
    for r in sorted(regiao.unique()):
        base = norm[(regiao == r).to_numpy()].drop_duplicates("data").sort_values("data")
        agora = variaveis_de_calendario(pd.DatetimeIndex(base["data"]), _eventos_da_regiao(eventos, r),
                                        replace(cfg, eventos_detalhados=False))
        datas_conferidas += len(base)
        for col in VARIAVEIS_CALENDARIO:
            a = base[col].to_numpy(dtype="float32")
            b = agora[col].to_numpy(dtype="float32")
            difere = ~np.isclose(a, b, rtol=0, atol=1e-6, equal_nan=True)
            if difere.any():
                dias = pd.DatetimeIndex(base["data"].to_numpy()[difere])
                diferencas[f"{r}:{col}"] = [str(x.date()) for x in dias[:10]] + ([f"... {difere.sum()} dias"]
                                                                                    if difere.sum() > 10 else [])
    if diferencas:
        raise ValueError(f"as variáveis 9 a 14 recalculadas com os eventos atuais não batem com as da base {pasta}: "
                         f"{json.dumps(diferencas, ensure_ascii=False)}")
    return {"datas_conferidas": int(datas_conferidas), "variaveis": list(VARIAVEIS_CALENDARIO), "diferencas": 0}


def assinatura(tabela: pd.DataFrame) -> str:
    """Identifica o conteúdo do calendário (regiões, datas e valores), independente dos tipos lidos do parquet."""
    h = hashlib.sha256()
    chaves = tabela["regiao"].astype(str) + ":" + pd.to_datetime(tabela["data"]).dt.strftime("%Y-%m-%d")
    h.update("|".join(chaves).encode("utf-8"))
    valores = [c for c in tabela.columns if c.startswith("fut_")] + [COLUNA_EVENTO_NO_HORIZONTE]
    h.update("|".join(valores).encode("utf-8"))
    h.update(np.ascontiguousarray(tabela[valores].to_numpy(dtype=np.float32)).tobytes())
    return h.hexdigest()[:16]


def gerar(pasta: Path, eventos: pd.DataFrame, saida: Path, origem: str = "") -> dict[str, Any]:
    """Confere a base, monta o calendário de todas as datas de origem da base e grava os dois arquivos."""
    pasta, saida = Path(pasta), Path(saida)
    normalizacao = json.loads((pasta / "normalizacao.json").read_text(encoding="utf-8"))
    campos = set(Config.__dataclass_fields__)
    cfg = Config(**{k: v for k, v in normalizacao["config"].items() if k in campos})
    conferencia = conferir(pasta, eventos, cfg)

    series = regiao_da_serie(pasta)
    janelas = {p: pd.read_parquet(pasta / f"janelas_{p}.parquet", columns=["serie", "data_origem"]) for p in PERIODOS}
    partes = []
    for r in sorted(set(series.values())):
        datas = pd.concat([j.loc[j["serie"].astype(str).map(series) == r, "data_origem"] for j in janelas.values()])
        tab = calcular(pd.DatetimeIndex(datas.unique()), _eventos_da_regiao(eventos, r), cfg)
        tab.insert(0, "regiao", r)
        partes.append(tab)
    tabela = pd.concat(partes, ignore_index=True)

    # Amostras de cada período com cada coluna diferente de zero em algum h (pelo número de amostras por dia de origem).
    nao_zero: dict[str, dict[str, Any]] = {}
    for p, j in janelas.items():
        por_dia = (j.assign(regiao=j["serie"].astype(str).map(series), data=pd.to_datetime(j["data_origem"]))
                   .groupby(["regiao", "data"]).size().rename("amostras").reset_index())
        t = por_dia.merge(tabela.assign(data=pd.to_datetime(tabela["data"])), on=["regiao", "data"], how="left")
        if t[COLUNA_EVENTO_NO_HORIZONTE].isna().any():
            raise AssertionError(f"dias de origem de {p} sem calendário futuro")
        nao_zero[p] = {"amostras": int(t["amostras"].sum())}
        for c in COLUNAS_FUTURAS[2:]:
            algum = (t[[f"{c}_h{h}" for h in range(1, cfg.horizonte + 1)]] != 0).any(axis=1)
            nao_zero[p][c] = int(t.loc[algum, "amostras"].sum())
        nao_zero[p][COLUNA_EVENTO_NO_HORIZONTE] = int(t.loc[t[COLUNA_EVENTO_NO_HORIZONTE].astype(bool), "amostras"].sum())
    info = {
        "gerado_em": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "origem": origem,
        "base": str(pasta),
        "assinatura_base": assinatura_normalizacao(normalizacao),
        "horizonte": cfg.horizonte,
        "antecedencia_anuncio_dias": cfg.antecedencia_anuncio_dias,
        "colunas_base": list(COLUNAS_FUTURAS),
        "colunas": colunas(cfg.horizonte),
        "regioes": sorted(set(series.values())),
        "datas": {"primeira": str(tabela["data"].min().date()), "ultima": str(tabela["data"].max().date())},
        "conferencia": conferencia,
        "amostras_com_valor_diferente_de_zero": nao_zero,
        "assinatura": assinatura(tabela),
    }
    saida.mkdir(parents=True, exist_ok=True)
    tabela.to_parquet(saida / "calendario_futuro.parquet", index=False)
    (saida / "calendario_futuro.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    return info


class CalendarioFuturo:
    """O X_fut [n, horizonte, 6] de cada amostra, pela região da série e pelo dia de origem."""

    def __init__(self, tabela: pd.DataFrame, horizonte: int, regiao_da_serie: dict[str, str],
                 assinatura: str = "") -> None:
        self.horizonte = horizonte
        self.colunas = colunas(horizonte)
        self.assinatura = assinatura
        self._regiao_da_serie = regiao_da_serie
        self._por_regiao: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for r, t in tabela.groupby("regiao", sort=True):
            t = t.sort_values("data")
            valores = t[self.colunas].to_numpy(dtype=np.float32).reshape(len(t), horizonte, len(COLUNAS_FUTURAS))
            self._por_regiao[str(r)] = (t["data"].to_numpy(dtype="datetime64[D]"), valores,
                                        t[COLUNA_EVENTO_NO_HORIZONTE].to_numpy(dtype=bool))

    @classmethod
    def carregar(cls, arquivo: Path, pasta: Path, horizonte: int) -> "CalendarioFuturo":
        arquivo = Path(arquivo)
        info = json.loads(arquivo.with_suffix(".json").read_text(encoding="utf-8"))
        if int(info["horizonte"]) != horizonte:
            raise ValueError(f"calendário de {info['horizonte']} dias para um modelo de {horizonte}")
        tabela = pd.read_parquet(arquivo)
        if assinatura(tabela) != info["assinatura"]:
            raise ValueError(f"{arquivo} não confere com a assinatura de {arquivo.with_suffix('.json')}")
        return cls(tabela, horizonte, regiao_da_serie(pasta), info["assinatura"])

    def _posicoes(self, series: pd.Series, datas: pd.Series) -> tuple[np.ndarray, list[tuple[np.ndarray, str, np.ndarray]]]:
        reg = np.asarray(pd.Series(series).astype(str).map(self._regiao_da_serie), dtype=object)
        d = np.asarray(pd.Series(datas).to_numpy(), dtype="datetime64[D]")
        grupos = []
        for r in pd.unique(reg):
            if r not in self._por_regiao:
                raise KeyError(f"região {r} sem calendário futuro")
            sel = np.flatnonzero(reg == r)
            dias = self._por_regiao[r][0]
            pos = np.clip(np.searchsorted(dias, d[sel]), 0, len(dias) - 1)
            if not (dias[pos] == d[sel]).all():
                raise KeyError(f"dias de origem sem calendário futuro na região {r}")
            grupos.append((sel, r, pos))
        return reg, grupos

    def tensor(self, series: pd.Series, datas: pd.Series) -> np.ndarray:
        _, grupos = self._posicoes(series, datas)
        out = np.empty((len(series), self.horizonte, len(COLUNAS_FUTURAS)), dtype=np.float32)
        for sel, r, pos in grupos:
            out[sel] = self._por_regiao[r][1][pos]
        return out

    def com_evento(self, series: pd.Series, datas: pd.Series) -> np.ndarray:
        _, grupos = self._posicoes(series, datas)
        out = np.zeros(len(series), dtype=bool)
        for sel, r, pos in grupos:
            out[sel] = self._por_regiao[r][2][pos]
        return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fonte = ap.add_mutually_exclusive_group(required=True)
    fonte.add_argument("--banco", action="store_true", help="lê evento_jogo do PostgreSQL (variáveis DB_* ou --db-url)")
    fonte.add_argument("--csv", type=Path, help="pasta com eventos.csv")
    ap.add_argument("--db-url", help="URL do SQLAlchemy; padrão: montada com DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME")
    ap.add_argument("--pasta", type=Path, required=True, help="a base preparada (as datas de origem e a conferência)")
    ap.add_argument("--saida", type=Path, required=True)
    args = ap.parse_args(argv)

    from io_dados import carregar_eventos_banco, carregar_eventos_csv, url_do_banco

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.banco:
        eventos, origem = carregar_eventos_banco(args.db_url or url_do_banco()), "banco"
    else:
        eventos, origem = carregar_eventos_csv(args.csv), "csv"
    info = gerar(args.pasta, eventos, args.saida, origem)
    print(json.dumps({k: info[k] for k in ("conferencia", "datas", "amostras_com_valor_diferente_de_zero",
                                           "assinatura")}, indent=2, ensure_ascii=False))
    print(f"\nGravado em {args.saida}. Treine com --calendario-futuro {args.saida / 'calendario_futuro.parquet'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
