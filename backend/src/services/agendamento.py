from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Mapping, Optional

from src.services.ingestao_config import INTERVALO_MINIMO, LIMITE_DA_LACUNA

# Folga sobre o intervalo mínimo: o disparo não pode cair alguns milissegundos antes de completar os 60 minutos
# (o que faria a coleta ser cancelada pelo CU09-C1-FA1 e adiada por mais uma hora).
MARGEM_DO_DISPARO = timedelta(seconds=5)
# Espera mínima antes de tentar de novo, para uma falha antes do registro do ciclo não virar um laço apertado.
ESPERA_MINIMA = timedelta(seconds=60)
# A recuperação pelo backfill não se repete em menos que isso: se a Blizzard ficar fora do ar por dias, o backfill
# (milhares de requisições à Undermine Exchange) não pode rodar a cada hora.
INTERVALO_ENTRE_RECUPERACOES = timedelta(hours=6)


@dataclass(frozen=True)
class Plano:
    """O que o worker faz agora."""
    recuperar_com_backfill: bool
    mercados_a_coletar: tuple[str, ...]  # chaves dos endpoints cujo intervalo mínimo (RN05) já passou


def planejar(
    agora: datetime,
    ultima_coleta: Optional[datetime],
    ultimas_requisicoes: Mapping[str, Optional[datetime]],
    ultimo_backfill_iniciado: Optional[datetime] = None,
) -> Plano:
    """
    Regras de agendamento da ingestão (CU09-C1, ativação), válidas ao iniciar o worker e a cada execução:

    - Cada endpoint sem requisição ou com a última há 60 minutos ou mais é coletado agora (RN05). Ao iniciar, isso
      faz a coleta acontecer na hora se a última foi há mais de uma hora; senão, o endpoint espera o seu horário.
    - Sem nenhuma coleta de histórico (de qualquer origem: ciclo da Blizzard ou backfill) há mais de 48 h, o
      histórico é recomposto pelo backfill antes do ciclo: em 48 h um leilão pode ter nascido e expirado sem passar
      por nenhum snapshot nosso (RN04).
    """
    lacuna = ultima_coleta is None or agora - ultima_coleta > LIMITE_DA_LACUNA
    tentou_ha_pouco = (
        ultimo_backfill_iniciado is not None and agora - ultimo_backfill_iniciado < INTERVALO_ENTRE_RECUPERACOES
    )
    devidos = tuple(
        chave for chave, ultima in ultimas_requisicoes.items() if ultima is None or agora - ultima >= INTERVALO_MINIMO
    )
    return Plano(recuperar_com_backfill=lacuna and not tentou_ha_pouco, mercados_a_coletar=devidos)


def proximo_disparo(agora: datetime, ultimas_requisicoes: Mapping[str, Optional[datetime]]) -> datetime:
    """Quando o worker roda de novo: quando o primeiro endpoint voltar a poder ser consultado (RN05), com folga."""
    liberacoes = [ultima + INTERVALO_MINIMO for ultima in ultimas_requisicoes.values() if ultima is not None]
    alvo = min(liberacoes) + MARGEM_DO_DISPARO if liberacoes else agora
    return max(alvo, agora + ESPERA_MINIMA)
