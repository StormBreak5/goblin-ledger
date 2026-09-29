import calendar
import logging
import os
from datetime import date, timedelta
from typing import Optional

from src.models.evento import (
    ORIGEM_REGRA,
    REGIAO_GLOBAL,
    TIPO_EVENTO_SAZONAL,
    TIPO_RECORRENTE,
)
from src.services.eventos.base import EventoExtraido

logger = logging.getLogger(__name__)

SEGUNDA, TERCA, QUARTA, QUINTA, SEXTA, SABADO, DOMINGO = range(7)
_DIAS_DA_SEMANA = {
    "monday": SEGUNDA, "tuesday": TERCA, "wednesday": QUARTA, "thursday": QUINTA,
    "friday": SEXTA, "saturday": SABADO, "sunday": DOMINGO,
}

# Reinício semanal dos EUA: toda terça-feira às 7:00 PDT (informado pelo autor). Como data (UTC), é a própria terça.
FONTE_REINICIO_US = "Regra: reinício semanal dos EUA, toda terça-feira às 7:00 PDT (informado pelo autor)"
# O autor só informou o dos EUA: o da Europa é uma sugestão (quarta-feira), configurável e marcada como pendente.
FONTE_REINICIO_EU = "Regra: reinício semanal da Europa, quarta-feira (sugestão pendente de confirmação; EVENTOS_REINICIO_SEMANAL_EU)"
FONTE_FEIRA = "Regra (Warcraft Wiki): a Feira de Negrilua abre no domingo da primeira semana cheia do mês e dura uma semana"
FONTE_POSTO = "Regra (Warcraft Wiki): o estoque do Posto de Troca gira no dia 1º de cada mês"
FONTE_NOBLEGARDEN = "Aproximação: a página só diz que varia com a Páscoa; início no domingo de Páscoa e duração de 7 dias"
FONTE_LUNAR = "Aproximação: a página só diz que varia com o Ano Novo Lunar; início nessa data e duração de 14 dias"

# Ano Novo Lunar (calendário chinês): a página da wiki não traz as datas do Lunar Festival, que acompanha esse feriado.
ANO_NOVO_LUNAR = {
    2020: date(2020, 1, 25), 2021: date(2021, 2, 12), 2022: date(2022, 2, 1), 2023: date(2023, 1, 22),
    2024: date(2024, 2, 10), 2025: date(2025, 1, 29), 2026: date(2026, 2, 17), 2027: date(2027, 2, 6),
    2028: date(2028, 1, 26), 2029: date(2029, 2, 13), 2030: date(2030, 2, 3),
}


def dia_do_reinicio_da_europa(valor: Optional[str] = None) -> Optional[int]:
    """Lê EVENTOS_REINICIO_SEMANAL_EU: um dia da semana em inglês (padrão: wednesday), ou "off" para não gerar o da Europa."""
    texto = (valor if valor is not None else os.getenv("EVENTOS_REINICIO_SEMANAL_EU", "wednesday")).strip().lower()
    if texto in ("", "off", "none", "desligado"):
        return None
    if texto not in _DIAS_DA_SEMANA:
        logger.warning("EVENTOS_REINICIO_SEMANAL_EU inválido ('%s'); usando quarta-feira.", texto)
        return QUARTA
    return _DIAS_DA_SEMANA[texto]


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (calendário gregoriano, algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def _meses(ano_inicial: int, ano_final: int):
    for ano in range(ano_inicial, ano_final + 1):
        for mes in range(1, 13):
            yield ano, mes


def _dias_da_semana(ano_inicial: int, ano_final: int, dia_da_semana: int):
    dia = date(ano_inicial, 1, 1)
    dia += timedelta(days=(dia_da_semana - dia.weekday()) % 7)
    while dia.year <= ano_final:
        yield dia
        dia += timedelta(days=7)


class Recorrentes:
    """
    CU10-C2 passo 2 (fonte "REGRA"): eventos que se repetem por regra de calendário, gerados de `ano_inicial` a
    `ano_final`: o reinício semanal (um por semana e região), a Feira de Negrilua (Darkmoon Faire) e a virada mensal do
    Posto de Troca. Nenhuma página é lida: as regras vêm da wiki e do autor e estão nas constantes acima.
    """
    origem = ORIGEM_REGRA

    def __init__(self, ano_inicial: int, ano_final: int, reinicio_eu: Optional[int] = QUARTA):
        self.ano_inicial = ano_inicial
        self.ano_final = ano_final
        self.reinicio_eu = reinicio_eu

    def extrair(self) -> list[EventoExtraido]:
        eventos: list[EventoExtraido] = []
        regioes = [("US", TERCA, FONTE_REINICIO_US)]
        if self.reinicio_eu is not None:
            regioes.append(("EU", self.reinicio_eu, FONTE_REINICIO_EU))
        for regiao, dia_da_semana, fonte in regioes:
            for dia in _dias_da_semana(self.ano_inicial, self.ano_final, dia_da_semana):
                eventos.append(EventoExtraido(
                    tipo=TIPO_RECORRENTE, nome="Weekly reset", data_inicio=dia, regiao=regiao, origem=ORIGEM_REGRA, fonte=fonte,
                ))

        for ano, mes in _meses(self.ano_inicial, self.ano_final):
            primeiro_domingo = date(ano, mes, 1) + timedelta(days=(DOMINGO - date(ano, mes, 1).weekday()) % 7)
            eventos.append(EventoExtraido(
                tipo=TIPO_RECORRENTE, nome="Darkmoon Faire", data_inicio=primeiro_domingo,
                data_fim=primeiro_domingo + timedelta(days=6), regiao=REGIAO_GLOBAL, origem=ORIGEM_REGRA, fonte=FONTE_FEIRA,
            ))
            eventos.append(EventoExtraido(
                tipo=TIPO_RECORRENTE, nome="Trading Post monthly rotation", data_inicio=date(ano, mes, 1),
                data_fim=date(ano, mes, calendar.monthrange(ano, mes)[1]), regiao=REGIAO_GLOBAL,
                origem=ORIGEM_REGRA, fonte=FONTE_POSTO,
            ))
        return eventos


def feriados_variaveis(ano_inicial: int, ano_final: int) -> list[EventoExtraido]:
    """Noblegarden (Páscoa) e Lunar Festival (Ano Novo Lunar): a Warcraft Wiki só diz que "variam", então as datas são
    aproximações marcadas no nome. Anos sem data conhecida do Ano Novo Lunar ficam de fora."""
    eventos: list[EventoExtraido] = []
    for ano in range(ano_inicial, ano_final + 1):
        domingo = pascoa(ano)
        eventos.append(EventoExtraido(
            tipo=TIPO_EVENTO_SAZONAL, nome="Noblegarden (aproximado)", data_inicio=domingo,
            data_fim=domingo + timedelta(days=7), regiao=REGIAO_GLOBAL, origem=ORIGEM_REGRA, fonte=FONTE_NOBLEGARDEN,
        ))
        lunar = ANO_NOVO_LUNAR.get(ano)
        if lunar is None:
            logger.warning("CU10-C2: sem a data do Ano Novo Lunar de %d; o Lunar Festival desse ano não foi gerado.", ano)
            continue
        eventos.append(EventoExtraido(
            tipo=TIPO_EVENTO_SAZONAL, nome="Lunar Festival (aproximado)", data_inicio=lunar,
            data_fim=lunar + timedelta(days=14), regiao=REGIAO_GLOBAL, origem=ORIGEM_REGRA, fonte=FONTE_LUNAR,
        ))
    return eventos
