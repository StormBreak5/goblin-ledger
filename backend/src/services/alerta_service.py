"""CU07 – Manter Alerta (RF05): criar (C1), alterar ou reativar (C2) e excluir (C3) alertas de preço dos itens favoritos,
com a cota de alertas ativos por usuário (RN08) e o preço-alvo em Cobre (RN01)."""
import math
import os
from datetime import datetime
from typing import Callable, Optional, Union

from sqlalchemy.orm import Session

from src.models.api_models import (Alerta, AlertaRequest, AlertaSalvoResponse, AlertasDoItemResponse,
                                   FormularioDoAlertaResponse)
from src.models.favorito import CANAIS_DE_ALERTA, SITUACAO_ATIVO, SITUACAO_DISPARADO, TIPOS_DE_ALERTA, AlertaPreco
from src.repositories.alerta_repository import AlertaRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.services import mensagens, security
from src.services.erros import (AlertaNaoEncontradoError, DadosDoAlertaInvalidosError, ItemForaDosFavoritosError,
                                LimiteDeAlertasError)
from src.services.item_service import ItemService

# RN08: alertas com a situação "Ativo" por usuário; os disparados não contam até serem reativados.
ALERTAS_MAXIMO_ATIVOS = int(os.getenv("ALERTAS_MAXIMO_ATIVOS", "20"))
COBRE_POR_PRATA = 100
COBRE_POR_OURO = 10_000

Parte = Union[int, float, str, None]


def _parte(valor: Parte) -> int:
    """Uma parte do preço-alvo (Ouro, Prata ou Cobre): vazia vale zero; inteira e não negativa, ou inválida (FA3)."""
    if valor is None or (isinstance(valor, str) and valor.strip() == ""):
        return 0
    if isinstance(valor, bool):
        raise DadosDoAlertaInvalidosError()
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto.isdigit():
            raise DadosDoAlertaInvalidosError()
        return int(texto)
    if isinstance(valor, float):
        if not math.isfinite(valor) or not valor.is_integer():
            raise DadosDoAlertaInvalidosError()
        valor = int(valor)
    if valor < 0:
        raise DadosDoAlertaInvalidosError()
    return int(valor)


def validar(dados: AlertaRequest) -> tuple[str, str, int]:
    """CU07-C1 passo 6 / C2 passo 4 (FA3) e RN01: o tipo de gatilho e o canal escolhidos e o preço-alvo maior que zero,
    convertido para Cobre (1 Ouro = 10.000 Cobre; 1 Prata = 100 Cobre). Prata e Cobre vão de 0 a 99."""
    if dados.tipo not in TIPOS_DE_ALERTA or dados.canal not in CANAIS_DE_ALERTA:
        raise DadosDoAlertaInvalidosError()
    ouro, prata, cobre = _parte(dados.ouro), _parte(dados.prata), _parte(dados.cobre)
    if prata >= COBRE_POR_PRATA or cobre >= COBRE_POR_PRATA:
        raise DadosDoAlertaInvalidosError()
    preco = ouro * COBRE_POR_OURO + prata * COBRE_POR_PRATA + cobre
    if preco <= 0:
        raise DadosDoAlertaInvalidosError()
    return dados.tipo, dados.canal, preco


def _como_resposta(alerta: AlertaPreco) -> Alerta:
    return Alerta(id_alerta=alerta.id_alerta, item_id=alerta.item_id, tipo=alerta.tipo, preco_alvo=int(alerta.preco_alvo),
                  canal=alerta.canal, situacao=alerta.situacao, disparado_em=alerta.disparado_em)


class AlertaService:
    def __init__(self, session: Session, relogio: Callable[[], datetime] = security.agora,
                 limite: int = ALERTAS_MAXIMO_ATIVOS):
        self.session = session
        self.relogio = relogio
        self.limite = limite
        self.repositorio = AlertaRepository(session)
        self.favoritos = FavoritoRepository(session)

    def do_item(self, id_usuario: int, item_id: int) -> AlertasDoItemResponse:
        """A seção "Alertas de preço": os alertas do usuário para o item e quantos ativos ele tem em todos os itens."""
        return AlertasDoItemResponse(
            alertas=[_como_resposta(a) for a in self.repositorio.do_item(id_usuario, item_id)],
            ativos_do_usuario=self.repositorio.ativos(id_usuario), limite=self.limite,
        )

    def _valor_de_mercado(self, item_id: int) -> Optional[int]:
        """O valor de mercado atual (RN06), o mesmo do cabeçalho da tela do item, como referência do formulário."""
        return ItemService(self.session, self.relogio).get_current_auctions(item_id).get("market_value")

    def _conferir_limite(self, id_usuario: int, ao_reativar: bool) -> None:
        """RN08 (C1 passo 3 e C2 passo 1.2): já há o máximo de alertas ativos? FA2 do cenário correspondente."""
        if self.repositorio.ativos(id_usuario) >= self.limite:
            raise LimiteDeAlertasError(self.limite, ao_reativar)

    def novo(self, id_usuario: int, item_id: int) -> FormularioDoAlertaResponse:
        """CU07-C1 passos 2 a 4, antes de abrir o formulário: o item está nos favoritos (FA1) e o usuário ainda pode criar
        um alerta (FA2, RN08)."""
        if not self.favoritos.existe(id_usuario, item_id):
            raise ItemForaDosFavoritosError()
        self._conferir_limite(id_usuario, ao_reativar=False)
        return FormularioDoAlertaResponse(item_id=item_id, market_value=self._valor_de_mercado(item_id))

    def criar(self, id_usuario: int, item_id: int, dados: AlertaRequest) -> AlertaSalvoResponse:
        """CU07-C1 passos 6 a 8: valida (FA3), confere de novo o favorito (FA1) e a cota (FA2) com a linha do usuário
        travada (RN08), converte o preço-alvo para Cobre (RN01) e grava o alerta como "Ativo". FE1: desfaz e propaga."""
        tipo, canal, preco = validar(dados)
        try:
            self.repositorio.travar_usuario(id_usuario)
            if not self.favoritos.existe(id_usuario, item_id):
                raise ItemForaDosFavoritosError()
            self._conferir_limite(id_usuario, ao_reativar=False)
            agora = self.relogio()
            alerta = AlertaPreco(id_usuario=id_usuario, item_id=item_id, tipo=tipo, preco_alvo=preco, canal=canal,
                                 situacao=SITUACAO_ATIVO, criado_em=agora, atualizado_em=agora)
            self.repositorio.incluir(alerta)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return AlertaSalvoResponse(alerta=_como_resposta(alerta), message=mensagens.ALERTA_CRIADO)

    def _do_usuario(self, id_usuario: int, id_alerta: int) -> AlertaPreco:
        alerta = self.repositorio.do_usuario(id_usuario, id_alerta)
        if alerta is None:
            raise AlertaNaoEncontradoError()
        return alerta

    def para_editar(self, id_usuario: int, id_alerta: int) -> FormularioDoAlertaResponse:
        """CU07-C2 passos 1 e 2: os dados atuais e o valor de mercado atual. FA1: o alerta disparado só é reativado se o
        usuário ainda puder ter mais um ativo (FA2, RN08)."""
        alerta = self._do_usuario(id_usuario, id_alerta)
        if alerta.situacao == SITUACAO_DISPARADO:
            self._conferir_limite(id_usuario, ao_reativar=True)
        return FormularioDoAlertaResponse(item_id=alerta.item_id, market_value=self._valor_de_mercado(alerta.item_id),
                                          alerta=_como_resposta(alerta))

    def alterar(self, id_usuario: int, id_alerta: int, dados: AlertaRequest) -> AlertaSalvoResponse:
        """CU07-C2 passos 4 a 6: valida (FA3); se o alerta estava disparado, confere de novo a cota com a linha do usuário
        travada (FA1/FA2, RN08); grava os dados com a situação "Ativo". FE1: desfaz, e o alerta fica como estava."""
        tipo, canal, preco = validar(dados)
        try:
            self.repositorio.travar_usuario(id_usuario)
            alerta = self._do_usuario(id_usuario, id_alerta)
            if alerta.situacao == SITUACAO_DISPARADO:
                self._conferir_limite(id_usuario, ao_reativar=True)
            self.repositorio.atualizar(alerta, {
                "tipo": tipo, "canal": canal, "preco_alvo": preco, "situacao": SITUACAO_ATIVO, "disparado_em": None,
                "atualizado_em": self.relogio(),
            })
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return AlertaSalvoResponse(alerta=_como_resposta(alerta), message=mensagens.ALERTA_ATUALIZADO)

    def excluir(self, id_usuario: int, id_alerta: int) -> str:
        """CU07-C3 passos 4 e 5 (a confirmação do passo 2 é da tela). FE1: desfaz, e o alerta é mantido."""
        alerta = self._do_usuario(id_usuario, id_alerta)
        try:
            self.repositorio.remover(alerta)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return mensagens.ALERTA_EXCLUIDO
