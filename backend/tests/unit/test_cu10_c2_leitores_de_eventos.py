"""
CU10 – Cenário 02: peças sem banco dos extratores de eventos (leitor de tabelas HTML, datas, Páscoa e regras de calendário).
Os fluxos completos do cenário estão em tests/integration/test_cu10_c2_eventos.py.
"""
from datetime import date

import pytest

from src.services.eventos.datas import data_br, data_em_ingles, dias_e_meses, formatar_data_br
from src.services.eventos.leitor_html import ler_tabelas
from src.services.eventos.recorrentes import (
    QUARTA,
    Recorrentes,
    dia_do_reinicio_da_europa,
    feriados_variaveis,
    pascoa,
)
from src.services.eventos.temporadas_blizzard import _dia


def test_cu10_c2_passo3_datas_em_ingles_viram_datas():
    assert data_em_ingles("January 16, 2007") == date(2007, 1, 16)
    assert data_em_ingles("Sept 3, 2020") == date(2020, 9, 3)
    assert data_em_ingles("  released on March 2 2026 [ 4 ]") == date(2026, 3, 2)
    for invalida in ("", "Foo 3, 2020", "February 30, 2020", "TBD", "2026-03-02", "March 2026"):
        assert data_em_ingles(invalida) is None, invalida


def test_cu10_c2_passo3_data_no_formato_padrao_dd_mm_aaaa():
    assert data_br("25/02/2025") == date(2025, 2, 25)
    assert data_br(" 01/01/2004 ") == date(2004, 1, 1)
    for invalida in ("", "31/02/2026", "2026-02-25", "25/2/2025", "25-02-2025", "00/01/2025", None):
        assert data_br(invalida) is None, invalida
    assert formatar_data_br(date(2026, 3, 2)) == "02/03/2026" and formatar_data_br(None) is None


def test_cu10_c2_periodos_anuais_em_dia_e_mes():
    assert dias_e_meses("7th Feb - 20th Feb") == [(2, 7), (2, 20)]
    assert dias_e_meses("31st Dec - 1st Jan") == [(12, 31), (1, 1)]
    assert dias_e_meses("19th Sept") == [(9, 19)]
    assert dias_e_meses("21st June - 5th July") == [(6, 21), (7, 5)]
    assert dias_e_meses("Varies (Easter)") == [] and dias_e_meses("") == []


def test_cu10_c2_leitor_de_tabelas_ignora_notas_scripts_e_le_tabelas_aninhadas():
    html = """
    <html><body><script>var t = "<table><tr><td>de mentira</td></tr></table>";</script>
    <table class="externa"><caption>Expansions for <i>WoW</i></caption>
      <tr><th>Title</th><th>Release date</th></tr>
      <tr><td><i><a href="#">Legion</a></i><sup>nota</sup><sup>[1]</sup></td>
          <td>August 30, 2016 <span>[ 2 ]</span><br>EU: later</td></tr>
      <tr><td colspan="2"><table><tr><td>aninhada</td></tr></table></td></tr>
    </table></body></html>
    """

    tabelas = ler_tabelas(html)

    assert [tabela.legenda for tabela in tabelas] == ["", "Expansions for WoW"]  # a aninhada termina primeiro
    assert tabelas[0].linhas == [["aninhada"]]
    externa = tabelas[1]
    assert externa.cabecalho == ["title", "release date"]
    assert externa.linhas[1] == ["Legion", "August 30, 2016 EU: later"]  # sem a nota "[1]" nem "[ 2 ]"


@pytest.mark.parametrize(
    "html",
    ["", "sem tabela nenhuma", "<table><tr><td>aberta", "<tr><td>solta</td></tr>", "<table></table>", "<td>x</td></table>"],
)
def test_cu10_c2_leitor_de_tabelas_nunca_levanta_erro_com_html_malformado(html):
    assert isinstance(ler_tabelas(html), list)


def test_cu10_c2_pascoa_do_calendario_gregoriano():
    conhecidas = {
        2022: date(2022, 4, 17), 2023: date(2023, 4, 9), 2024: date(2024, 3, 31), 2025: date(2025, 4, 20),
        2026: date(2026, 4, 5), 2027: date(2027, 3, 28),
    }
    assert {ano: pascoa(ano) for ano in conhecidas} == conhecidas
    assert all(pascoa(ano).weekday() == 6 for ano in range(2000, 2100))  # sempre um domingo


def test_cu10_c2_feriados_variaveis_sao_marcados_como_aproximados_e_pulam_anos_sem_data():
    eventos = {(e.nome, e.data_inicio.year): e for e in feriados_variaveis(2029, 2031)}

    assert eventos[("Noblegarden (aproximado)", 2029)].data_inicio == date(2029, 4, 1)
    assert eventos[("Lunar Festival (aproximado)", 2029)].data_fim == date(2029, 2, 27)
    assert ("Noblegarden (aproximado)", 2031) in eventos  # a Páscoa se calcula sempre
    assert ("Lunar Festival (aproximado)", 2031) not in eventos  # a data do Ano Novo Lunar de 2031 não é conhecida
    assert all(evento.origem == "REGRA" and "Aproximação" in evento.fonte for evento in eventos.values())


def test_cu10_c2_reinicio_semanal_da_europa_vem_do_ambiente(monkeypatch):
    assert dia_do_reinicio_da_europa("wednesday") == QUARTA
    assert dia_do_reinicio_da_europa(" THURSDAY ") == 3
    assert dia_do_reinicio_da_europa("off") is None and dia_do_reinicio_da_europa("") is None
    assert dia_do_reinicio_da_europa("quarta") == QUARTA  # valor inválido volta à sugestão
    monkeypatch.delenv("EVENTOS_REINICIO_SEMANAL_EU", raising=False)
    assert dia_do_reinicio_da_europa() == QUARTA


def test_cu10_c2_feira_de_negrilua_abre_no_primeiro_domingo_de_cada_mes():
    eventos = Recorrentes(2025, 2025).extrair()
    feira = {e.data_inicio: e.data_fim for e in eventos if e.nome == "Darkmoon Faire"}

    assert feira[date(2025, 2, 2)] == date(2025, 2, 8)  # fevereiro começou num sábado
    assert feira[date(2025, 6, 1)] == date(2025, 6, 7)  # junho começou num domingo
    assert all(inicio.weekday() == 6 and inicio.day <= 7 for inicio in feira)
    assert len(feira) == 12


def test_cu10_c2_data_de_temporada_da_api_so_aceita_marcas_validas():
    assert _dia(1786460400000) == date(2026, 8, 11)
    for invalida in (None, 0, -5, "1786460400000", True, 10**30):
        assert _dia(invalida) is None, invalida
