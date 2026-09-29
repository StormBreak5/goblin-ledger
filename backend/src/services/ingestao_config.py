import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from src.models.mercado import REGIOES_DE_MERCADO

logger = logging.getLogger(__name__)

# CU09-C1 passo 2 (RN05): intervalo mínimo entre requisições ao mesmo endpoint da Casa de Leilões.
INTERVALO_MINIMO = timedelta(minutes=60)
# Regra de recuperação: sem nenhuma coleta há mais de 48 h (o prazo máximo de um leilão, RN04), o histórico é
# recomposto pelo backfill dos .bin antes do próximo ciclo.
LIMITE_DA_LACUNA = timedelta(hours=48)
# CU09-C3 passo 3 (RN04): leilão sem atualização há mais de 48 h vira "Expirado/Vendido".
PRAZO_DO_LEILAO = timedelta(hours=48)

# Convenção do sistema para o "reino" das commodities de cada região (as commodities não pertencem a um reino).
COMMODITIES_ID_POR_REGIAO = {"US": 32512, "EU": 32513}

TIPO_LEILOES = "LEILOES"
TIPO_COMMODITIES = "COMMODITIES"


def _int_do_ambiente(nome: str, padrao: int) -> int:
    return int(os.getenv(nome, str(padrao)))


def _float_do_ambiente(nome: str, padrao: float) -> float:
    return float(os.getenv(nome, str(padrao)))


# CU09-C2-FA1: proporção de descarte acima da qual o lote vai para o log de auditoria (o documento não define).
LIMITE_DE_DESCARTE = _float_do_ambiente("INGESTAO_LIMITE_DESCARTE", 0.05)
# CU09-C3: por quantos dias os leilões brutos "Expirado/Vendido" ficam no banco; o resumo horário permanece.
RETENCAO_DE_LEILOES = timedelta(days=_int_do_ambiente("INGESTAO_RETENCAO_LEILOES_DIAS", 7))
# CU09-C2 passo 4 (RN12): volume anômalo = mais de FATOR vezes a mediana dos últimos 7 dias, com piso de volume e
# um mínimo de pontos anteriores para haver base de comparação.
ANOMALIA_FATOR = _int_do_ambiente("INGESTAO_ANOMALIA_FATOR", 10)
ANOMALIA_VOLUME_MINIMO = _int_do_ambiente("INGESTAO_ANOMALIA_VOLUME_MINIMO", 100)
ANOMALIA_MINIMO_DE_PONTOS = 24
ANOMALIA_JANELA = timedelta(days=7)

# CU04-C1-FA1 (RN09): idade do último ciclo de ingestão do mercado do item a partir da qual os dados são "Desatualizados". O
# documento não define o limiar (sugeria 2 h); o autor adotou 24 h.
LIMIAR_DE_DADOS_DESATUALIZADOS = timedelta(hours=_int_do_ambiente("DADOS_DESATUALIZADOS_HORAS", 24))

# CU09-C1-FE1: retentativas (só erro de rede e 5xx) com espera crescente, dentro do mesmo ciclo.
ESPERAS_ENTRE_TENTATIVAS = (5, 15, 45)


@dataclass(frozen=True)
class Mercado:
    """Um endpoint monitorado: os leilões de um reino conectado ou as commodities de uma região."""
    tipo: str
    regiao: str
    id_reino: int
    nome: str

    @property
    def chave(self) -> str:
        """Identifica o endpoint no controle do intervalo mínimo (RN05) e no frescor (RN09)."""
        if self.tipo == TIPO_COMMODITIES:
            return f"commodities:{self.regiao.lower()}"
        return f"auctions:{self.regiao.lower()}:{self.id_reino}"


def carregar_mercados(valor: Optional[str] = None) -> list[Mercado]:
    """
    CU09-C1 (pré-condição e FA2): lê MONITORED_REALMS ("us:3209,eu:1305") e devolve os endpoints a monitorar: cada
    reino configurado e as commodities de cada região presente. Reino de região fora de US/EU (RN11) é ignorado e
    registrado em log; as demais entradas seguem.
    """
    bruto = valor if valor is not None else os.getenv("MONITORED_REALMS", "us:3209")
    mercados: list[Mercado] = []
    regioes: list[str] = []
    for entrada in (parte.strip() for parte in bruto.split(",")):
        if not entrada:
            continue
        regiao, _, id_texto = entrada.partition(":")
        regiao = regiao.strip().upper()
        if regiao not in REGIOES_DE_MERCADO:
            logger.warning("CU09-C1-FA2: reino '%s' fora das regiões US/EU (RN11); ignorado.", entrada)
            continue
        if not id_texto.strip().isdigit():
            logger.warning("CU09-C1: entrada de MONITORED_REALMS inválida '%s'; ignorada.", entrada)
            continue
        id_reino = int(id_texto)
        mercados.append(Mercado(TIPO_LEILOES, regiao, id_reino, f"{regiao} reino {id_reino}"))
        if regiao not in regioes:
            regioes.append(regiao)

    for regiao in regioes:
        mercados.append(Mercado(TIPO_COMMODITIES, regiao, COMMODITIES_ID_POR_REGIAO[regiao], f"{regiao} commodities"))
    return mercados
