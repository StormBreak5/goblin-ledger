from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.models.evento import EXTRACAO_FALHA, EventoJogo, ExtracaoEvento
from src.services.eventos.base import EventoExtraido

EVENTOS_POR_INSERT = 2000


class EventoRepository:
    """Acesso a dados do CU10-C2: eventos do jogo (RN17) e o registro de cada extração."""

    def __init__(self, session: Session):
        self.session = session

    def ultima_extracao(self, fonte: str, url: Optional[str]) -> Optional[datetime]:
        """Início da última tentativa de extração da fonte (e do endereço), qualquer que tenha sido o resultado."""
        consulta = self.session.query(func.max(ExtracaoEvento.iniciada_em)).filter(ExtracaoEvento.fonte == fonte)
        consulta = consulta.filter(ExtracaoEvento.url.is_(None) if url is None else ExtracaoEvento.url == url)
        return consulta.scalar()

    def registrar_extracao(
        self, fonte: str, url: Optional[str], iniciada_em: datetime, concluida_em: datetime, status: str,
        encontrados: int = 0, registrados: int = 0, ignorados: int = 0, erro: Optional[str] = None,
    ) -> None:
        self.session.add(ExtracaoEvento(
            fonte=fonte, url=url, iniciada_em=iniciada_em, concluida_em=concluida_em, status=status,
            eventos_encontrados=encontrados, eventos_registrados=registrados, eventos_ignorados=ignorados,
            erro=(erro or None) if status == EXTRACAO_FALHA else None,
        ))

    def registrar(self, eventos: Sequence[EventoExtraido], agora: datetime) -> tuple[list[EventoJogo], int]:
        """
        CU10-C2 passos 4 e 5 / FA1: registra os eventos que ainda não constam na base histórica (o mesmo tipo, nome,
        data e região) e ignora os demais. Devolve os eventos registrados e quantos foram ignorados. Não confirma a transação.
        """
        unicos: dict[tuple, EventoExtraido] = {}
        for evento in eventos:
            unicos.setdefault(evento.chave, evento)  # o mesmo evento repetido na própria fonte também é ignorado

        registrados: list[EventoJogo] = []
        pendentes = list(unicos.values())
        for inicio in range(0, len(pendentes), EVENTOS_POR_INSERT):
            linhas = [
                {
                    "tipo": e.tipo, "nome": e.nome, "versao": e.versao, "data_inicio": e.data_inicio,
                    "data_fim": e.data_fim, "regiao": e.regiao, "origem": e.origem, "fonte": e.fonte[:255] if e.fonte else None,
                    "criado_em": agora,
                }
                for e in pendentes[inicio:inicio + EVENTOS_POR_INSERT]
            ]
            instrucao = insert(EventoJogo).values(linhas).on_conflict_do_nothing(constraint="uq_evento_jogo").returning(EventoJogo)
            registrados.extend(self.session.scalars(instrucao).all())
        return registrados, len(eventos) - len(registrados)

    def listar(
        self, tipo: Optional[str] = None, regiao: Optional[str] = None, limite: int = 100, deslocamento: int = 0
    ) -> tuple[int, list[EventoJogo]]:
        """Os eventos registrados, do mais recente para o mais antigo, com o total do filtro."""
        consulta = self.session.query(EventoJogo)
        if tipo:
            consulta = consulta.filter(EventoJogo.tipo == tipo)
        if regiao:
            consulta = consulta.filter(EventoJogo.regiao == regiao)
        total = consulta.count()
        eventos = (
            consulta.order_by(EventoJogo.data_inicio.desc(), EventoJogo.id_evento.desc()).offset(deslocamento).limit(limite).all()
        )
        return total, eventos
