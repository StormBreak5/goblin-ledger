from dataclasses import dataclass, field
from typing import Any, Optional

from src.services.ingestao_config import TIPO_COMMODITIES

COBRE_POR_PRATA = 100  # RN01
COBRE_POR_OURO = 10000  # RN01


class PayloadForaDoFormatoError(Exception):
    """CU09-C2-FE1: a estrutura do payload não corresponde ao formato esperado da API (ex.: a API mudou)."""


def para_cobre(ouro: int = 0, prata: int = 0, cobre: int = 0) -> int:
    """CU09-C2 passo 3 (RN01): converte para Cobre, o único formato armazenado. 1 Ouro = 10000 Cobre; 1 Prata = 100."""
    return ouro * COBRE_POR_OURO + prata * COBRE_POR_PRATA + cobre


@dataclass(frozen=True)
class LeilaoPadronizado:
    """Leilão sanitizado, com preços em Cobre, pronto para a consolidação (CU09-C3)."""
    id_origem: int
    item_id: int
    quantidade: int
    preco_bid: Optional[int]
    preco_buyout: Optional[int]  # total do leilão
    preco_unitario: Optional[int]  # buyout por unidade (base do valor de mercado, RN06)
    tempo_restante: Optional[str]


@dataclass
class ResultadoSanitizacao:
    leiloes: list[LeilaoPadronizado] = field(default_factory=list)
    descartados: int = 0

    @property
    def total(self) -> int:
        return len(self.leiloes) + self.descartados

    @property
    def taxa_de_descarte(self) -> float:
        return self.descartados / self.total if self.total else 0.0


def _inteiro_positivo(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def _inteiro_nao_negativo(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def _padronizar(registro: Any, tipo: str) -> Optional[LeilaoPadronizado]:
    """CU09-C2 passos 2 e 3: devolve o leilão padronizado em Cobre, ou None se o registro for estruturalmente
    inválido (campo obrigatório ausente ou tipo incompatível)."""
    if not isinstance(registro, dict):
        return None
    item = registro.get("item")
    id_do_item = item.get("id") if isinstance(item, dict) else None
    quantidade = registro.get("quantity")
    if not (_inteiro_positivo(registro.get("id")) and _inteiro_positivo(id_do_item) and _inteiro_positivo(quantidade)):
        return None
    tempo = registro.get("time_left")
    tempo_restante = tempo if isinstance(tempo, str) else None

    if tipo == TIPO_COMMODITIES:
        preco_unitario = registro.get("unit_price")
        if not _inteiro_positivo(preco_unitario):
            return None
        return LeilaoPadronizado(
            registro["id"], id_do_item, quantidade, None, para_cobre(cobre=preco_unitario) * quantidade,
            preco_unitario, tempo_restante,
        )

    bid, buyout = registro.get("bid"), registro.get("buyout")
    if (bid is not None and not _inteiro_nao_negativo(bid)) or (buyout is not None and not _inteiro_nao_negativo(buyout)):
        return None
    preco_buyout = para_cobre(cobre=buyout) if buyout else None  # leilão só com lance não tem preço de compra
    preco_unitario = (preco_buyout + quantidade // 2) // quantidade if preco_buyout else None
    return LeilaoPadronizado(
        registro["id"], id_do_item, quantidade, para_cobre(cobre=bid) if bid else None, preco_buyout,
        preco_unitario, tempo_restante,
    )


def sanitizar(payload: Any, tipo: str) -> ResultadoSanitizacao:
    """
    CU09-C2: valida a estrutura do payload bruto, descarta os registros inválidos e padroniza os valores em Cobre
    (a API da Blizzard já entrega em cobre; a conversão de Ouro/Prata fica em `para_cobre`).

    - FE1 (passo 1): payload que não é um objeto com a lista `auctions` levanta PayloadForaDoFormatoError.
    - A marcação de anomalias (passo 4, RN12) precisa do histórico do item e é feita em `valor_de_mercado`.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("auctions"), list):
        raise PayloadForaDoFormatoError("O payload não tem a lista 'auctions' esperada.")

    resultado = ResultadoSanitizacao()
    for registro in payload["auctions"]:
        leilao = _padronizar(registro, tipo)
        if leilao is None:
            resultado.descartados += 1
        else:
            resultado.leiloes.append(leilao)
    return resultado
