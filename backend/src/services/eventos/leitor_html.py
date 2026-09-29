import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

# Marcas de nota de rodapé que sobram no texto ("[ 2 ]", "[a]").
_NOTA_DE_RODAPE = re.compile(r"\[\s*[\w\s]{1,4}\s*\]")
_IGNORADAS = {"script", "style", "sup"}  # sup: referências e notas


@dataclass
class Tabela:
    """Uma tabela HTML reduzida ao texto: a legenda e as linhas (cabeçalhos e dados), célula a célula."""
    legenda: str = ""
    linhas: list[list[str]] = field(default_factory=list)

    @property
    def cabecalho(self) -> list[str]:
        return [celula.lower() for celula in self.linhas[0]] if self.linhas else []


@dataclass
class _Rascunho:
    tabela: Tabela = field(default_factory=Tabela)
    linha: list[str] | None = None
    celula: list[str] | None = None
    legenda: list[str] | None = None


def limpar_texto(texto: str) -> str:
    """Espaços normalizados e sem notas de rodapé."""
    return re.sub(r"\s+", " ", _NOTA_DE_RODAPE.sub("", texto)).strip()


class _LeitorDeTabelas(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tabelas: list[Tabela] = []
        self._pilha: list[_Rascunho] = []  # tabelas aninhadas (como as caixas de navegação da wiki)
        self._ignorando = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _IGNORADAS:
            self._ignorando += 1
            return
        if tag == "table":
            self._pilha.append(_Rascunho())
            return
        if not self._pilha:
            return
        atual = self._pilha[-1]
        if tag == "tr":
            self._fechar_linha(atual)
            atual.linha = []
        elif tag in ("td", "th"):
            self._fechar_celula(atual)
            if atual.linha is None:
                atual.linha = []
            atual.celula = []
        elif tag == "caption":
            atual.legenda = []
        elif tag in ("br", "li", "p", "div") and atual.celula is not None:
            atual.celula.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORADAS:
            self._ignorando = max(0, self._ignorando - 1)
            return
        if not self._pilha:
            return
        atual = self._pilha[-1]
        if tag in ("td", "th"):
            self._fechar_celula(atual)
        elif tag == "tr":
            self._fechar_linha(atual)
        elif tag == "caption" and atual.legenda is not None:
            atual.tabela.legenda = limpar_texto("".join(atual.legenda))
            atual.legenda = None
        elif tag == "table":
            self._fechar_linha(atual)
            self.tabelas.append(self._pilha.pop().tabela)

    def handle_data(self, data: str) -> None:
        if self._ignorando or not self._pilha:
            return
        atual = self._pilha[-1]
        if atual.celula is not None:
            atual.celula.append(data)
        elif atual.legenda is not None:
            atual.legenda.append(data)

    @staticmethod
    def _fechar_celula(atual: _Rascunho) -> None:
        if atual.celula is not None and atual.linha is not None:
            atual.linha.append(limpar_texto("".join(atual.celula)))
        atual.celula = None

    def _fechar_linha(self, atual: _Rascunho) -> None:
        self._fechar_celula(atual)
        if atual.linha:
            atual.tabela.linhas.append(atual.linha)
        atual.linha = None


def ler_tabelas(html: str) -> list[Tabela]:
    """Todas as tabelas da página, na ordem em que terminam (as aninhadas antes das que as contêm), só com a biblioteca
    padrão. Um HTML malformado nunca levanta erro: o que não puder ser lido simplesmente não vira tabela."""
    leitor = _LeitorDeTabelas()
    leitor.feed(html)
    leitor.close()
    return leitor.tabelas
