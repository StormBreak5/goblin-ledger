import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.models.cobertura import AptidaoTreinamento
from src.repositories.cobertura_repository import AptidaoDoItem, CoberturaRepository
from src.services import security

logger = logging.getLogger(__name__)

# RN15: período contínuo mínimo para o treinamento inicial: 6 meses, em dias (o documento não fixa os dias).
MINIMO_DE_DIAS = int(os.getenv("COBERTURA_MINIMO_DIAS", "180"))
# CU10-C3 passo 3 ("desconsiderando lacunas na série"): dias seguidos sem registro que ainda não interrompem o período.
# O documento não define a tolerância; a sugestão é 3 dias.
LACUNA_MAXIMA_DIAS = int(os.getenv("COBERTURA_LACUNA_MAXIMA_DIAS", "3"))
WOW_TOKEN_ID = 122284  # a Ficha do WoW tem série própria (item_prices), fora do histórico da Casa de Leilões

SITUACAO_APTO = "APTO"
SITUACAO_INAPTO = "INAPTO"


@dataclass
class ResumoDaCobertura:
    """CU10-C3 passo 6: aptos e inaptos, com o período contínuo de cada item."""
    validado_em: Optional[datetime]
    total: int
    aptos: int
    inaptos: int
    itens: list[AptidaoDoItem]
    pagina: int
    tamanho_da_pagina: int


class CoberturaService:
    """CU10-C3 – Validar cobertura histórica dos itens (RF11 / RN15)."""

    def __init__(
        self,
        session: Session,
        relogio: Callable[[], datetime] = security.agora,
        minimo_de_dias: Optional[int] = None,
        lacuna_maxima_dias: Optional[int] = None,
    ):
        self.session = session
        self.relogio = relogio
        self.minimo_de_dias = MINIMO_DE_DIAS if minimo_de_dias is None else minimo_de_dias
        self.lacuna_maxima_dias = LACUNA_MAXIMA_DIAS if lacuna_maxima_dias is None else lacuna_maxima_dias
        self.repository = CoberturaRepository(session)

    def validar(self, pagina: int = 1, tamanho_da_pagina: int = 50) -> ResumoDaCobertura:
        """
        Passos 1 a 6: para cada item ativo, calcula o maior período contínuo de registros e o classifica como apto
        (período de pelo menos 6 meses) ou inapto (FA1: a predição continua bloqueada). Tudo é gravado numa única
        transação: se o banco falhar (FE1), nenhuma classificação é alterada e o erro propaga.
        """
        try:
            itens = self.repository.itens_ativos(excluir=(WOW_TOKEN_ID,))
            periodos = self.repository.periodos_continuos(list(itens), self.lacuna_maxima_dias)
            momento = self.relogio()
            aptidoes = []
            for item_id in itens:
                periodo = periodos.get(item_id)
                dias = periodo.periodo_dias if periodo else 0
                aptidoes.append(AptidaoTreinamento(
                    item_id=item_id,
                    apto=dias >= self.minimo_de_dias,  # passo 4 / FA1
                    periodo_continuo_dias=dias,
                    inicio_periodo=periodo.inicio if periodo else None,
                    fim_periodo=periodo.fim if periodo else None,
                    dias_com_dados=periodo.dias_com_dados if periodo else 0,
                    validado_em=momento,
                ))
            self.repository.substituir_resultado(aptidoes)
            self.session.commit()
        except Exception:
            self.session.rollback()
            logger.exception("CU10-C3-FE1: falha ao validar a cobertura histórica; a classificação anterior foi mantida.")
            raise
        aptos = sum(1 for aptidao in aptidoes if aptidao.apto)
        logger.info("CU10-C3: %d itens validados: %d aptos e %d inaptos ao treinamento.", len(aptidoes), aptos, len(aptidoes) - aptos)
        return self.consultar(None, pagina, tamanho_da_pagina)

    def consultar(self, situacao: Optional[str], pagina: int = 1, tamanho_da_pagina: int = 50) -> ResumoDaCobertura:
        """A última validação, com a página pedida da relação de itens (filtrada por APTO ou INAPTO, se informado)."""
        apto = {SITUACAO_APTO: True, SITUACAO_INAPTO: False}.get((situacao or "").strip().upper())
        pagina = max(pagina, 1)
        total, aptos, inaptos, validado_em, itens = self.repository.resultado(apto, (pagina - 1) * tamanho_da_pagina, tamanho_da_pagina)
        return ResumoDaCobertura(validado_em, total, aptos, inaptos, itens, pagina, tamanho_da_pagina)
