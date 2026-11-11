"""RN01: todo valor monetário é guardado em Cobre (1 Prata = 100 Cobre; 1 Ouro = 10.000 Cobre); a conversão para Ouro,
Prata e Cobre acontece só na exibição. Mesmo formato do `frontend/lib/moeda.ts`, para o e-mail do CU08-C2."""
COBRE_POR_PRATA = 100
COBRE_POR_OURO = 10_000


def formatar_moeda(cobre: int) -> str:
    """Valor em Cobre no formato do jogo, sem as partes zeradas: `12g 49s 30c`, `286.541g`, `45s`, `0c`."""
    if cobre < 0:
        raise ValueError(f"Valor monetário negativo: {cobre}")
    ouro, resto = divmod(int(cobre), COBRE_POR_OURO)
    prata, cobre_restante = divmod(resto, COBRE_POR_PRATA)
    partes: list[str] = []
    if ouro > 0:
        partes.append(f"{ouro:,}".replace(",", ".") + "g")  # milhar com ponto, como o toLocaleString("pt-BR")
    if prata > 0:
        partes.append(f"{prata}s")
    if cobre_restante > 0:
        partes.append(f"{cobre_restante}c")
    return " ".join(partes) if partes else "0c"
