import os

import requests

from src.services.eventos.base import FonteDeEventosIndisponivelError

TIMEOUT_SEGUNDOS = 30


def _user_agent() -> str:
    """Identifica o projeto para quem mantém a página. O contato (EVENTOS_CONTATO) é opcional e vem do ambiente."""
    contato = os.getenv("EVENTOS_CONTATO", "").strip()
    return "GoblinLedger/1.0 (projeto academico UEG" + (f"; {contato}" if contato else "") + ")"


def baixar_pagina(url: str) -> str:
    """CU10-C2 passo 2: o HTML da página de referência. Rede fora do ar, tempo limite esgotado ou HTTP diferente de 200
    são FonteDeEventosIndisponivelError (fluxo de exceção 1)."""
    try:
        resposta = requests.get(url, headers={"User-Agent": _user_agent(), "Accept": "text/html"}, timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException as e:
        raise FonteDeEventosIndisponivelError(f"{type(e).__name__}: {e}") from e
    if resposta.status_code != 200:
        raise FonteDeEventosIndisponivelError(f"HTTP {resposta.status_code} em {url}")
    return resposta.text
