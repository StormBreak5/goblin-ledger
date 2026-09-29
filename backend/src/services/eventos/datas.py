import re
from datetime import date
from typing import Optional

MESES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DATA_POR_EXTENSO = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b")  # "January 16, 2007"
_DIA_E_MES = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\b")  # "7th Feb", "20th Sept"
_DATA_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _mes(nome: str) -> Optional[int]:
    return MESES.get(nome[:3].lower())


def data_em_ingles(texto: str) -> Optional[date]:
    """CU10-C2 passo 3: "January 16, 2007" (o formato das páginas de referência) → data. None se não for uma data."""
    encontrada = _DATA_POR_EXTENSO.search(texto or "")
    if encontrada is None:
        return None
    mes = _mes(encontrada.group(1))
    if mes is None:
        return None
    try:
        return date(int(encontrada.group(3)), mes, int(encontrada.group(2)))
    except ValueError:
        return None


def dias_e_meses(texto: str) -> list[tuple[int, int]]:
    """Períodos anuais como "31st Dec - 1st Jan" ou "19th Sept": lista de (mês, dia) na ordem em que aparecem."""
    resultado = []
    for dia, nome_do_mes in _DIA_E_MES.findall(texto or ""):
        mes = _mes(nome_do_mes)
        if mes is not None:
            resultado.append((mes, int(dia)))
    return resultado


def data_br(texto: str) -> Optional[date]:
    """CU10-C2 passo 3 e FA2: "DD/MM/AAAA" → data; None se o formato ou a data for inválido (ex.: 31/02/2026)."""
    encontrada = _DATA_BR.fullmatch((texto or "").strip())
    if encontrada is None:
        return None
    try:
        return date(int(encontrada.group(3)), int(encontrada.group(2)), int(encontrada.group(1)))
    except ValueError:
        return None


def formatar_data_br(valor: Optional[date]) -> Optional[str]:
    """CU10-C2 passo 3: o formato padrão do documento (DD/MM/AAAA)."""
    return valor.strftime("%d/%m/%Y") if valor else None
