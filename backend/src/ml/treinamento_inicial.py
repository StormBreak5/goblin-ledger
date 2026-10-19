"""CU11-C1 – Executar treinamento inicial, passos 2 a 12 (no serviço `modelo`).

O passo 1 (o pedido do Admin) e o FA2 estão em src/services/treinamento_service.py. Aqui:

- passo 2 (FA1): elegíveis à projeção e conjunto de treinamento (src/ml/selecao.py);
- passo 3 (FE2): série diária da Undermine (src/ml/dados.py);
- passos 4 a 7 (FA3): RN03, variáveis, normalização e períodos (src/ml/preparacao.py);
- passo 8 (FE1): treino da rede (src/ml/rede.py);
- passos 9 e 10 (FA4, FA5): avaliação no período de teste de todos os elegíveis e RN10 (src/ml/avaliacao.py);
- passo 11 (FE2): versão do modelo, vigência e situação de cada item, numa só transação;
- passo 12: o resumo fica em `execucao_treinamento`, que a tela do Admin consulta.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd
from sqlalchemy import delete, insert, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.ml.artefatos import ARQUIVO_MODELO, ARQUIVO_NORMALIZACAO, ARQUIVO_TREINO, Artefatos
from src.ml.avaliacao import Avaliacao, avaliar
from src.ml.configuracao import ConfigModelo
from src.ml.dados import carregar_banco
from src.ml.dataset import DadosPreparados
from src.ml.preparacao import BasePreparada, SemAmostrasDeTreino, preparar
from src.ml.rede import FalhaNoTreinamento, ResultadoDoTreino, Treinador
from src.ml.selecao import Selecao, selecionar
from src.models.modelo import (ETAPA_BANCO, ETAPA_INTERNA, ETAPA_SELECAO, ETAPA_TREINO, MOTIVO_ACIMA_DO_LIMIAR,
                               MOTIVO_AVALIACAO_INSUFICIENTE, MOTIVO_NAO_SUPERA_INGENUO, MOTIVO_SERIE_INSUFICIENTE,
                               SITUACAO_BLOQUEADA, SITUACAO_IGNORADA, SITUACAO_LIBERADA, STATUS_FALHA, STATUS_SUCESSO,
                               ExecucaoTreinamento, ModeloPreditivo, ProjecaoItem)
from src.services import security

logger = logging.getLogger(__name__)

AVISO_RN07_DESLIGADA = ("RN07 desligada: o nível mínimo dos equipamentos da temporada vigente (MODELO_ILVL_MINIMO) "
                        "não foi definido, e os equipamentos não foram filtrados pelo nível de item.")
METRICAS = ("dias_avaliados", "alvos_avaliados", "mdape", "mdape_ingenuo", "mape", "mape_ingenuo", "rmse_cobre",
            "rmse_ingenuo_cobre", "erro_relativo_ingenuo")


class _Falha(Exception):
    def __init__(self, etapa: str, erro: str) -> None:
        super().__init__(erro)
        self.etapa = etapa
        self.erro = erro


@dataclass
class Contagens:
    """Resumo do passo 12 (gravado em execucao_treinamento)."""
    itens_elegiveis: Optional[int] = None
    itens_treino: Optional[int] = None
    itens_liberados: Optional[int] = None
    itens_bloqueados: Optional[int] = None
    bloqueados_acima_do_limiar: Optional[int] = None
    bloqueados_nao_supera_ingenuo: Optional[int] = None
    bloqueados_avaliacao_insuficiente: Optional[int] = None
    itens_ignorados: Optional[int] = None
    liberados_fora_do_treino: Optional[int] = None
    liberados_sem_amostra_de_treino: Optional[int] = None
    ultimo_dia: Optional[date] = None  # RN25: último dia encerrado da série usada

    def como_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


def situacao_dos_itens(selecao: Selecao, base: BasePreparada, av: Avaliacao) -> pd.DataFrame:
    """CU11-C1 passos 9 e 10, FA3, FA4 e FA5: a situação de cada item elegível.

    - FA3: sem nenhuma amostra depois da higienização → IGNORADA, "série insuficiente" (fora do treino e da avaliação);
    - avaliado no teste → LIBERADA ou BLOQUEADA pela RN10, com as métricas (FA4: acima do limiar ou não supera o
      ingênuo; FA5: menos de 30 dias avaliados);
    - com amostras, mas sem nenhum dia avaliado no período de teste → BLOQUEADA, "avaliação insuficiente" (FA5).
    """
    eleg = selecao.elegiveis[["serie", "item_id", "integra_treino", "dias_de_historico"]].astype({"serie": str})
    amostras = base.itens[["serie", "item_id", "amostras_treino", "amostras_validacao", "amostras_teste"]]
    out = eleg.merge(amostras, on=["serie", "item_id"], how="left")
    for p in ("amostras_treino", "amostras_validacao", "amostras_teste"):
        out[p] = out[p].fillna(0).astype("int64")
    metricas = av.por_item[["serie", "item_id", *METRICAS, "situacao", "motivo"]].astype({"serie": str})
    out = out.merge(metricas, on=["serie", "item_id"], how="left")

    sem_amostras = (out["amostras_treino"] + out["amostras_validacao"] + out["amostras_teste"]) == 0
    nao_avaliado = out["situacao"].isna() & ~sem_amostras
    out.loc[sem_amostras, "situacao"] = SITUACAO_IGNORADA
    out.loc[sem_amostras, "motivo"] = MOTIVO_SERIE_INSUFICIENTE
    out.loc[nao_avaliado, "situacao"] = SITUACAO_BLOQUEADA
    out.loc[nao_avaliado, "motivo"] = MOTIVO_AVALIACAO_INSUFICIENTE
    out.loc[nao_avaliado, ["dias_avaliados", "alvos_avaliados"]] = 0
    return out


def contar(situacao: pd.DataFrame, selecao: Selecao) -> Contagens:
    """CU11-C1 passo 12: liberados, bloqueados por motivo e ignorados, os liberados fora do conjunto de treinamento e
    os liberados sem nenhuma amostra no período de treinamento (lançados depois do fim dele: integram o conjunto de
    treinamento pela RN15, mas não ajustaram os pesos)."""
    bloqueada = situacao["situacao"] == SITUACAO_BLOQUEADA
    liberada = situacao["situacao"] == SITUACAO_LIBERADA
    return Contagens(
        itens_elegiveis=int(selecao.itens["elegivel"].sum()),
        itens_treino=int(selecao.itens["integra_treino"].sum()),
        itens_liberados=int(liberada.sum()),
        itens_bloqueados=int(bloqueada.sum()),
        bloqueados_acima_do_limiar=int((bloqueada & (situacao["motivo"] == MOTIVO_ACIMA_DO_LIMIAR)).sum()),
        bloqueados_nao_supera_ingenuo=int((bloqueada & (situacao["motivo"] == MOTIVO_NAO_SUPERA_INGENUO)).sum()),
        bloqueados_avaliacao_insuficiente=int((bloqueada & (situacao["motivo"] == MOTIVO_AVALIACAO_INSUFICIENTE)).sum()),
        itens_ignorados=int((situacao["situacao"] == SITUACAO_IGNORADA).sum()),
        liberados_fora_do_treino=int((liberada & ~situacao["integra_treino"].astype(bool)).sum()),
        liberados_sem_amostra_de_treino=int((liberada & (situacao["amostras_treino"] == 0)).sum()),
        ultimo_dia=selecao.ultimo_dia,
    )


def _numero(valor: Any) -> Optional[float]:
    return None if valor is None or (isinstance(valor, float) and not np.isfinite(valor)) or pd.isna(valor) \
        else float(valor)


class TreinamentoInicial:
    """CU11-C1 passos 2 a 12. `treinador` é a rede (TreinadorKeras); os testes injetam um treinador falso."""

    def __init__(self, engine: Engine, cfg: ConfigModelo, pasta: Path, treinador: Optional[Treinador] = None,
                 relogio: Callable[[], Any] = security.agora) -> None:
        self.engine = engine
        self.abrir_sessao = sessionmaker(bind=engine)
        self.cfg = cfg
        self.pasta = Path(pasta)
        if treinador is None:
            from src.ml.rede import TreinadorKeras
            treinador = TreinadorKeras()
        self.treinador = treinador
        self.relogio = relogio

    # ------------------------------------------------------------------------------------------------- execução
    def executar(self, id_execucao: int, data_execucao: Optional[date] = None) -> None:
        """`data_execucao`: a data UTC da execução (padrão: a do relógio). RN25: só os dias anteriores a ela, os já
        encerrados, entram no histórico."""
        contagens = Contagens()
        artefatos = Artefatos(self.pasta, id_execucao)
        ate = data_execucao or self.relogio().date()
        try:
            regiao = self._regiao(id_execucao)

            # Passos 2 e 3: a seleção usa a própria série (RN02 e RN27), então a leitura vem antes.
            self._andamento(id_execucao, "Selecionando os itens elegíveis e o conjunto de treinamento")
            entrada = self._ler_banco(ate)
            selecao = selecionar(entrada, self.cfg, regiao)
            contagens.itens_elegiveis = int(selecao.itens["elegivel"].sum())
            contagens.itens_treino = int(selecao.itens["integra_treino"].sum())
            contagens.ultimo_dia = selecao.ultimo_dia
            if contagens.itens_treino == 0:
                raise _Falha(ETAPA_SELECAO, f"Nenhum dos {contagens.itens_elegiveis} itens elegíveis à projeção na "
                                            f"região {regiao} é apto ao treinamento (RN15).")

            # Passos 4 a 7.
            self._andamento(id_execucao, "Preparando as variáveis de entrada")
            try:
                base = preparar(entrada, selecao.precos, self.cfg, selecao.fora_do_treino)
            except SemAmostrasDeTreino as e:  # FA3 em todos os itens do conjunto de treinamento
                raise _Falha(ETAPA_SELECAO, f"Os itens do conjunto de treinamento não têm amostras suficientes depois "
                                            f"da higienização: {e}") from e
            del entrada
            selecao.precos = selecao.precos.iloc[0:0]
            dados = DadosPreparados(base)
            jan_tr = dados.janelas("treino")
            jan_va = dados.janelas("validacao")
            jan_tr = jan_tr[~jan_tr["fora_do_treino"].to_numpy(dtype=bool)].reset_index(drop=True)
            jan_va = jan_va[~jan_va["fora_do_treino"].to_numpy(dtype=bool)].reset_index(drop=True)

            # Passo 8 (FE1).
            self._andamento(id_execucao, "Treinando o modelo")
            try:
                treino = self.treinador.treinar(dados, jan_tr, jan_va, self.cfg,
                                                ao_fim_da_epoca=self._registrador_de_epocas(id_execucao))
            except (FalhaNoTreinamento, MemoryError) as e:
                raise _Falha(ETAPA_TREINO, str(e) or repr(e)) from e

            # Passos 9 e 10: todos os elegíveis, inclusive os que não integram o conjunto de treinamento.
            self._andamento(id_execucao, "Avaliando o modelo no período de teste")
            jan_te = dados.janelas("teste")
            ids, yhat = self.treinador.prever(treino.modelo, dados, jan_te)
            av = avaliar(dados, "teste", ids, yhat)
            situacao = situacao_dos_itens(selecao, base, av)
            contagens = contar(situacao, selecao)

            artefatos.iniciar()
            self.treinador.salvar(treino.modelo, artefatos.temporaria / ARQUIVO_MODELO)
            artefatos.gravar_json(ARQUIVO_NORMALIZACAO, base.normalizacao)
            artefatos.gravar_avaliacao(situacao)

            # Passo 11 (FE2).
            self._andamento(id_execucao, "Registrando a versão do modelo")
            self._registrar(id_execucao, regiao, selecao, base, treino, av, situacao, contagens, artefatos,
                            len(jan_te))
        except _Falha as f:
            artefatos.descartar()
            self._falhar(id_execucao, f.etapa, f.erro, contagens)
        except Exception as e:  # erro inesperado: registra e devolve a fila
            logger.exception("CU11-C1: erro inesperado no treinamento %s.", id_execucao)
            artefatos.descartar()
            self._falhar(id_execucao, ETAPA_INTERNA, repr(e), contagens)

    # ----------------------------------------------------------------------------------------------- passos
    def _regiao(self, id_execucao: int) -> str:
        try:
            with self.abrir_sessao() as s:
                execucao = s.get(ExecucaoTreinamento, id_execucao)
                if execucao is None:
                    raise _Falha(ETAPA_INTERNA, f"Treinamento {id_execucao} não encontrado.")
                return execucao.regiao
        except SQLAlchemyError as e:
            raise _Falha(ETAPA_BANCO, f"Falha ao ler o pedido do treinamento: {e}") from e

    def _ler_banco(self, ate: date):  # type: ignore[no-untyped-def]
        """CU11-C1 passo 3 (FE2: falha de I/O ou queda de conexão), só com os dias anteriores a `ate` (RN25)."""
        try:
            with self.abrir_sessao() as s:
                return carregar_banco(s.connection(), self.cfg, ate)
        except SQLAlchemyError as e:
            raise _Falha(ETAPA_BANCO, f"Falha ao ler a série histórica: {e}") from e

    def _registrar(self, id_execucao: int, regiao: str, selecao: Selecao, base: BasePreparada,
                   treino: ResultadoDoTreino, av: Avaliacao, situacao: pd.DataFrame, contagens: Contagens,
                   artefatos: Artefatos, amostras_teste: int) -> None:
        """CU11-C1 passo 11: a versão nova vira a vigente da região (a anterior, se houver, é substituída) e a situação
        de cada item elegível é gravada, numa só transação. A situação dos itens que deixaram de ser elegíveis sai
        junto: ela era da versão anterior."""
        cortes = base.normalizacao["cortes"]
        resumo = av.resumo
        with self.abrir_sessao() as s:
            try:
                agora = self.relogio()
                s.execute(update(ModeloPreditivo)
                          .where(ModeloPreditivo.regiao == regiao, ModeloPreditivo.vigente.is_(True))
                          .values(vigente=False, substituido_em=agora))
                modelo = ModeloPreditivo(
                    regiao=regiao, treinado_em=agora, id_execucao=id_execucao,
                    data_inicio=pd.Timestamp(cortes["inicio"]).date(),
                    corte_validacao=pd.Timestamp(cortes["corte_validacao"]).date(),
                    corte_teste=pd.Timestamp(cortes["corte_teste"]).date(), data_fim=pd.Timestamp(cortes["fim"]).date(),
                    itens_elegiveis=contagens.itens_elegiveis or 0, itens_treino=contagens.itens_treino or 0,
                    itens_avaliados=int(resumo["itens"]), amostras_treino=treino.amostras_treino,
                    amostras_validacao=treino.amostras_validacao, amostras_teste=amostras_teste,
                    epocas=treino.epocas, melhor_epoca=treino.melhor_epoca,
                    segundos_por_epoca=treino.segundos_por_epoca, duracao_segundos=treino.duracao_segundos,
                    mediana_mdape=_numero(resumo["mediana_mdape_por_item"]),
                    mediana_mdape_ingenuo=_numero(resumo["mediana_mdape_ingenuo_por_item"]),
                    mediana_mape=_numero(resumo["mediana_mape_por_item"]),
                    mediana_mape_ingenuo=_numero(resumo["mediana_mape_ingenuo_por_item"]),
                    mediana_rmse_cobre=_numero(resumo["mediana_rmse_cobre_por_item"]),
                    mediana_rmse_ingenuo_cobre=_numero(resumo["mediana_rmse_ingenuo_cobre_por_item"]),
                    itens_supera_ingenuo=int(resumo["itens_que_superam_ingenuo"]),
                    caminho_artefatos="", assinatura_normalizacao=base.normalizacao["assinatura"], vigente=True,
                )
                s.add(modelo)
                s.flush()
                artefatos.gravar_json(ARQUIVO_TREINO, self._info_do_treino(id_execucao, modelo.versao, regiao, treino,
                                                                           av, contagens, base))
                modelo.caminho_artefatos = artefatos.publicar(modelo.versao).as_posix()
                self._gravar_situacao(s, regiao, modelo.versao, situacao, agora)

                execucao = s.get(ExecucaoTreinamento, id_execucao)
                execucao.status = STATUS_SUCESSO
                execucao.concluido_em = agora
                execucao.versao = modelo.versao
                execucao.andamento = "Concluído"
                execucao.avisos = None if selecao.rn07_ativa else AVISO_RN07_DESLIGADA
                for campo, valor in contagens.como_dict().items():
                    setattr(execucao, campo, valor)
                versao = modelo.versao
                s.commit()
            except SQLAlchemyError as e:
                s.rollback()
                raise _Falha(ETAPA_BANCO, f"Falha ao registrar a versão do modelo: {e}") from e
            artefatos.confirmar()  # a versão está no banco: os artefatos dela não são mais descartados
        logger.info("CU11-C1: versão %s registrada como vigente em %s (%s).", versao, regiao, contagens.como_dict())

    def _gravar_situacao(self, s: Session, regiao: str, versao: int, situacao: pd.DataFrame, agora: Any) -> None:
        s.execute(delete(ProjecaoItem).where(ProjecaoItem.regiao == regiao))
        linhas = [
            {
                "serie": str(r["serie"]), "item_id": int(r["item_id"]), "regiao": regiao, "versao": versao,
                "integra_treino": bool(r["integra_treino"]),
                **{m: (None if pd.isna(r[m]) else (int(r[m]) if m in ("dias_avaliados", "alvos_avaliados")
                                                    else float(r[m]))) for m in METRICAS},
                "situacao": r["situacao"], "motivo": None if pd.isna(r["motivo"]) else str(r["motivo"]),
                "atualizado_em": agora,
            }
            for r in situacao.to_dict("records")
        ]
        if linhas:
            s.execute(insert(ProjecaoItem), linhas)

    def _info_do_treino(self, id_execucao: int, versao: int, regiao: str, treino: ResultadoDoTreino, av: Avaliacao,
                        contagens: Contagens, base: BasePreparada) -> dict[str, Any]:
        return {
            "versao": versao, "id_execucao": id_execucao, "regiao": regiao,
            "treinado_em": self.relogio().isoformat(timespec="seconds"),
            "parametros": self.cfg.como_dict(),
            "epocas_executadas": treino.epocas, "melhor_epoca": treino.melhor_epoca,
            "melhor_val_loss": treino.melhor_val_loss, "duracao_segundos": treino.duracao_segundos,
            "segundos_por_epoca": treino.segundos_por_epoca,
            "amostras": {"treino": treino.amostras_treino, "validacao": treino.amostras_validacao,
                         "validacao_parada_antecipada": treino.amostras_parada_antecipada,
                         "teste": av.resumo["amostras"]},
            "versoes": treino.versoes, "assinatura_normalizacao": base.normalizacao["assinatura"],
            "ultimo_dia": None if contagens.ultimo_dia is None else contagens.ultimo_dia.isoformat(),
            "contagens_da_preparacao": base.normalizacao["contagens"], "resumo_do_treinamento": contagens.como_dict(),
            "avaliacao_teste": av.resumo,
        }

    # ------------------------------------------------------------------------------------------ acompanhamento
    def _andamento(self, id_execucao: int, texto: str) -> None:
        """A etapa atual, gravada numa conexão à parte para a tela do Admin acompanhar."""
        try:
            with self.engine.begin() as conexao:
                conexao.execute(update(ExecucaoTreinamento).where(ExecucaoTreinamento.id == id_execucao)
                                .values(andamento=texto[:255]))
        except SQLAlchemyError:
            logger.warning("CU11-C1: não foi possível registrar o andamento do treinamento.", exc_info=True)

    def _registrador_de_epocas(self, id_execucao: int) -> Callable[[int, int, Optional[float]], None]:
        def registrar(epoca: int, maximo: int, val_loss: Optional[float]) -> None:
            perda = "" if val_loss is None else f" (erro na validação: {val_loss:.4f})".replace(".", ",")
            self._andamento(id_execucao, f"Treinando o modelo: época {epoca} de até {maximo}{perda}")

        return registrar

    def _falhar(self, id_execucao: int, etapa: str, erro: str, contagens: Contagens) -> None:
        """FA1, FE1 e FE2: os registros anteriores (versão vigente e situação dos itens) ficam como estavam; a falha
        vai para o log e para a execução, que a tela mostra com a mensagem do cenário."""
        logger.error("CU11-C1: treinamento %s não concluído (%s): %s", id_execucao, etapa, erro)
        try:
            with self.engine.begin() as conexao:
                conexao.execute(update(ExecucaoTreinamento).where(ExecucaoTreinamento.id == id_execucao).values(
                    status=STATUS_FALHA, concluido_em=self.relogio(), etapa_da_falha=etapa, erro=erro, andamento=None,
                    **contagens.como_dict()))
        except SQLAlchemyError:
            logger.exception("CU11-C1: não foi possível registrar a falha do treinamento %s.", id_execucao)


def preencher_liberados_sem_amostra_de_treino(engine: Engine) -> int:
    """CU11-C1 passo 12: as execuções concluídas antes da migração 0008 não têm os liberados sem amostra de treino.
    O número sai do artefato da versão (avaliacao_teste.parquet: liberados com `amostras_treino == 0`). Idempotente:
    só preenche o que está nulo. Devolve quantas execuções foram completadas."""
    from src.ml.artefatos import ARQUIVO_AVALIACAO

    completadas = 0
    with sessionmaker(bind=engine)() as s:
        pendentes = (
            s.query(ExecucaoTreinamento, ModeloPreditivo)
            .join(ModeloPreditivo, ModeloPreditivo.versao == ExecucaoTreinamento.versao)
            .filter(ExecucaoTreinamento.status == STATUS_SUCESSO,
                    ExecucaoTreinamento.liberados_sem_amostra_de_treino.is_(None))
            .all()
        )
        for execucao, modelo in pendentes:
            caminho = Path(modelo.caminho_artefatos) / ARQUIVO_AVALIACAO
            if not caminho.exists():
                logger.warning("CU11: %s não existe; liberados sem amostra de treino da execução %s ficam em branco.",
                               caminho, execucao.id)
                continue
            itens = pd.read_parquet(caminho, columns=["situacao", "amostras_treino"])
            execucao.liberados_sem_amostra_de_treino = int(
                ((itens["situacao"] == SITUACAO_LIBERADA) & (itens["amostras_treino"] == 0)).sum())
            completadas += 1
            logger.info("CU11: execução %s completada com %s liberados sem amostra de treino.", execucao.id,
                        execucao.liberados_sem_amostra_de_treino)
        s.commit()
    return completadas
