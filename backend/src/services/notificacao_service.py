"""CU08 – Manter Notificações (RF06): verificar os alertas ativos a cada ciclo de ingestão e disparar as notificações dos
atingidos (C1, RN07), enviar por e-mail as que têm esse canal (C2, RN18) e consultá-las pelo sino do cabeçalho (C3)."""
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.api_models import MarcarLidasRequest, NaoLidasResponse, NotificacoesResponse
from src.models.api_models import Notificacao as NotificacaoDaTela
from src.models.favorito import CANAL_WEB, TIPO_COMPRA, TIPO_VENDA
from src.models.item_price import REGIAO_DA_FICHA, WOW_TOKEN_ID
from src.models.notificacao import ENVIO_ENVIADO, ENVIO_FALHOU, ENVIO_PENDENTE, Notificacao
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.notificacao_repository import NotificacaoRepository
from src.services import mensagens, security
from src.services.email_de_alerta import montar_email_de_alerta
from src.services.email_service import EmailService

logger = logging.getLogger(__name__)

# CU08-C2-FA1: tentativas de envio de cada e-mail, uma por execução do C2; depois da última, o envio é marcado "Falhou".
NOTIFICACAO_EMAIL_TENTATIVAS = int(os.getenv("NOTIFICACAO_EMAIL_TENTATIVAS", "3"))


@dataclass(frozen=True)
class ValorDoCiclo:
    """Um item atualizado no ciclo: o valor de mercado do ponto gravado (RN06, em Cobre) e a marca de anomalia de volume
    desse ponto (RN12)."""
    item_id: int
    valor_de_mercado: int
    anomalo: bool = False


@dataclass
class ResultadoDaVerificacao:
    """CU08-C1 passo 8: o que vai para o log da conclusão."""
    itens_verificados: int = 0
    itens_anomalos: int = 0
    alertas_atingidos: int = 0
    encaminhadas_para_email: int = 0
    falhou: bool = False


@dataclass
class ResultadoDoEnvio:
    """CU08-C2: os e-mails enviados, as tentativas sem sucesso que continuam pendentes e os marcados como "Falhou"."""
    enviados: int = 0
    pendentes_de_nova_tentativa: int = 0
    falharam: int = 0
    falhou: bool = False


def gatilho_atingido(tipo: str, preco_alvo: int, valor_de_mercado: int) -> bool:
    """RN07: um alerta de compra é atingido quando o valor de mercado for igual ou inferior ao preço-alvo; um de venda,
    quando for igual ou superior."""
    if tipo == TIPO_COMPRA:
        return valor_de_mercado <= preco_alvo
    if tipo == TIPO_VENDA:
        return valor_de_mercado >= preco_alvo
    return False


class NotificacaoService:
    def __init__(
        self,
        session: Session,
        relogio: Callable[[], datetime] = security.agora,
        email_service: Optional[EmailService] = None,
        tentativas: int = NOTIFICACAO_EMAIL_TENTATIVAS,
    ):
        self.session = session
        self.relogio = relogio
        self.email_service = email_service or EmailService()
        self.tentativas = tentativas
        self.repositorio = NotificacaoRepository(session)

    # ------------------------------------------------------------------ C1 e C2 (o sistema)

    def processar_ciclo(self, valores: Sequence[ValorDoCiclo], origem: str) -> None:
        """CU08-C1 seguido do C2, logo depois de um ciclo de ingestão concluído (CU09-C3) ou de uma nova cotação da Ficha
        do WoW. O C2 roda mesmo se a verificação falhar: ele também processa as pendentes de ciclos anteriores. Nunca
        levanta exceção: quem chama (o CU09) não tem o resultado alterado por uma falha aqui."""
        try:
            self.verificar_alertas(valores, origem)
        except Exception:
            self._desfazer()
            logger.exception("CU08-C1: erro inesperado na verificação dos alertas de %s.", origem)
        try:
            self.enviar_pendentes()
        except Exception:
            self._desfazer()
            logger.exception("CU08-C2: erro inesperado no envio das notificações por e-mail.")

    def processar_coleta_da_ficha(self, preco: int) -> None:
        """CU08-C1 para a Ficha do WoW, cuja cotação é coletada a cada 15 minutos fora do ciclo do CU09: a mesma
        verificação e o mesmo envio, a cada preço novo. A RN12 não se aplica (a Ficha não tem volume)."""
        self.processar_ciclo([ValorDoCiclo(WOW_TOKEN_ID, int(preco), anomalo=False)], f"ficha:{REGIAO_DA_FICHA}")

    def verificar_alertas(self, valores: Sequence[ValorDoCiclo], origem: str) -> ResultadoDaVerificacao:
        """CU08-C1, numa transação própria: recupera os alertas ativos dos itens do ciclo (passo 2), confere o gatilho com o
        valor de mercado do ciclo (passos 3 e 4, RN07), registra a notificação (passo 5) e passa o alerta a "Disparado"
        uma única vez (passo 6, RN07); com e-mail, a notificação fica pendente de envio (passo 7). FA2: os itens com o
        ponto do ciclo marcado como anomalia de volume (RN12) não são verificados. FE1: uma falha de banco desfaz tudo; os
        alertas continuam ativos e são verificados de novo no próximo ciclo. Passo 8 (e FA1): o log da conclusão."""
        resultado = ResultadoDaVerificacao()
        verificaveis: dict[int, int] = {}
        for valor in valores:
            if valor.anomalo:
                resultado.itens_anomalos += 1  # FA2
            else:
                verificaveis[valor.item_id] = valor.valor_de_mercado
        resultado.itens_verificados = len(verificaveis)

        agora = self.relogio()
        try:
            for alerta in self.repositorio.alertas_ativos_dos_itens(list(verificaveis)):
                valor_de_mercado = verificaveis[alerta.item_id]
                if not gatilho_atingido(alerta.tipo, int(alerta.preco_alvo), valor_de_mercado):
                    continue
                canal = self.repositorio.disparar(alerta, agora)
                if canal is None:  # já disparado por outro ciclo, ou alterado pelo usuário nesse meio tempo
                    continue
                envio = None if canal == CANAL_WEB else ENVIO_PENDENTE  # passo 7: encaminhada para o C2
                self.repositorio.registrar(Notificacao(
                    id_alerta=alerta.id_alerta, id_usuario=alerta.id_usuario, item_id=alerta.item_id, tipo=alerta.tipo,
                    preco_alvo=int(alerta.preco_alvo), valor_mercado=valor_de_mercado, canal=canal, disparada_em=agora,
                    envio_email=envio, tentativas_email=0,
                ))
                resultado.alertas_atingidos += 1
                resultado.encaminhadas_para_email += envio is not None
            self.session.commit()
        except SQLAlchemyError:
            self._desfazer()
            logger.exception("CU08-C1-FE1: falha de banco na verificação dos alertas de %s; nada foi gravado e a "
                             "verificação se repete no próximo ciclo.", origem)
            return ResultadoDaVerificacao(itens_verificados=resultado.itens_verificados,
                                          itens_anomalos=resultado.itens_anomalos, falhou=True)

        if resultado.alertas_atingidos == 0:
            logger.info("CU08-C1-FA1: verificação de %s concluída: %d itens verificados, %d ignorados por anomalia de "
                        "volume (RN12), nenhum alerta atingido.", origem, resultado.itens_verificados,
                        resultado.itens_anomalos)
        else:
            logger.info("CU08-C1: verificação de %s concluída: %d itens verificados, %d ignorados por anomalia de volume "
                        "(RN12), %d alertas atingidos, %d notificações encaminhadas para e-mail.", origem,
                        resultado.itens_verificados, resultado.itens_anomalos, resultado.alertas_atingidos,
                        resultado.encaminhadas_para_email)
        return resultado

    def enviar_pendentes(self) -> ResultadoDoEnvio:
        """CU08-C2: recupera as notificações com e-mail ainda não enviadas, inclusive as de ciclos anteriores (passo 1),
        monta a mensagem (passo 2, RN01), envia ao e-mail cadastrado do usuário (passo 3, RN18) e registra a data e a hora
        do envio (passo 4). Cada notificação é travada só durante o próprio envio, fora da transação do C1.
        FA1: a falha soma uma tentativa e a notificação continua pendente; na última, o envio é marcado "Falhou" e vai
        para o log. A falha de um e-mail não impede os outros. FE1: a falha de banco vai para o log e as pendentes ficam
        para a próxima execução."""
        resultado = ResultadoDoEnvio()
        try:
            pendentes = self.repositorio.pendentes_de_envio()
            itens = FavoritoRepository(self.session).itens(sorted({p.item_id for p in pendentes}))
            self.session.commit()  # encerra a leitura: nenhuma transação fica aberta durante os envios
        except SQLAlchemyError:
            self._desfazer()
            logger.exception("CU08-C2-FE1: falha de banco ao recuperar as notificações pendentes de envio; ficam para a "
                             "próxima execução.")
            resultado.falhou = True
            return resultado

        for pendente in pendentes:
            try:
                notificacao = self.repositorio.travar_pendente(pendente.id_notificacao, pendente.tentativas)
                if notificacao is None:  # outra rotina já a pegou
                    self.session.rollback()
                    continue
                item = itens.get(pendente.item_id)
                notificacao.tentativas_email = pendente.tentativas + 1
                try:
                    mensagem = montar_email_de_alerta(
                        item.name if item is not None else f"Item {pendente.item_id}", pendente.item_id, pendente.tipo,
                        pendente.preco_alvo, pendente.valor_mercado, pendente.disparada_em,
                    )
                    self.email_service.enviar_notificacao_de_alerta(pendente.email, mensagem)
                except Exception as erro:  # FA1: o servidor de e-mail não aceitou a mensagem
                    if notificacao.tentativas_email >= self.tentativas:
                        notificacao.envio_email = ENVIO_FALHOU
                        resultado.falharam += 1
                        logger.error("CU08-C2-FA1: o e-mail da notificação %d falhou %d vezes e foi marcado como "
                                     "\"Falhou\": %s", pendente.id_notificacao, notificacao.tentativas_email, erro)
                    else:
                        resultado.pendentes_de_nova_tentativa += 1
                        logger.warning("CU08-C2-FA1: falha no envio do e-mail da notificação %d (tentativa %d de %d); "
                                       "fica pendente para o próximo ciclo: %s", pendente.id_notificacao,
                                       notificacao.tentativas_email, self.tentativas, erro)
                else:
                    notificacao.envio_email = ENVIO_ENVIADO
                    notificacao.enviada_em = self.relogio()
                    resultado.enviados += 1
                self.session.commit()
            except SQLAlchemyError:
                self._desfazer()
                resultado.falhou = True
                logger.exception("CU08-C2-FE1: falha de banco no envio da notificação %d; fica pendente para a próxima "
                                 "execução.", pendente.id_notificacao)

        if pendentes:
            logger.info("CU08-C2: %d e-mails enviados, %d pendentes de nova tentativa, %d marcados como \"Falhou\".",
                        resultado.enviados, resultado.pendentes_de_nova_tentativa, resultado.falharam)
        return resultado

    def _desfazer(self) -> None:
        try:
            self.session.rollback()
        except SQLAlchemyError:
            logger.exception("CU08: não foi possível desfazer a transação.")

    # ------------------------------------------------------------------ C3 (o usuário)

    def nao_lidas(self, id_usuario: int) -> NaoLidasResponse:
        """CU08-C3 passo 1: a quantidade de notificações não lidas, para o ícone de sino."""
        return NaoLidasResponse(nao_lidas=self.repositorio.nao_lidas(id_usuario))

    def listar(self, id_usuario: int) -> NotificacoesResponse:
        """CU08-C3 passos 3 e 4: as notificações do usuário com o canal tela, da mais recente para a mais antiga, com o
        item, o tipo de gatilho, o preço-alvo, o valor de mercado que o atingiu, a data e a hora e se já foi lida.
        FA1: nenhuma notificação. Não marca nada como lida: isso é o passo 5 (`marcar_como_lidas`)."""
        notificacoes = self.repositorio.da_tela(id_usuario)
        if not notificacoes:
            return NotificacoesResponse(notificacoes=[], nao_lidas=0, mensagem=mensagens.NOTIFICACOES_VAZIO)
        itens = FavoritoRepository(self.session).itens(sorted({n.item_id for n in notificacoes}))
        linhas = []
        for notificacao in notificacoes:
            item = itens.get(notificacao.item_id)
            linhas.append(NotificacaoDaTela(
                id_notificacao=notificacao.id_notificacao, item_id=notificacao.item_id,
                name=item.name if item is not None else f"Item {notificacao.item_id}",
                icon_url=item.icon_url if item is not None else None, tipo=notificacao.tipo,
                preco_alvo=int(notificacao.preco_alvo), valor_mercado=int(notificacao.valor_mercado),
                disparada_em=notificacao.disparada_em, lida=notificacao.lida_em is not None,
            ))
        return NotificacoesResponse(notificacoes=linhas, nao_lidas=sum(not linha.lida for linha in linhas))

    def marcar_como_lidas(self, id_usuario: int, dados: MarcarLidasRequest) -> NaoLidasResponse:
        """CU08-C3 passo 5: marca como lidas as notificações exibidas (só as do próprio usuário) e devolve o contador."""
        self.repositorio.marcar_lidas(id_usuario, dados.ids, self.relogio())
        self.session.commit()
        return NaoLidasResponse(nao_lidas=self.repositorio.nao_lidas(id_usuario))
