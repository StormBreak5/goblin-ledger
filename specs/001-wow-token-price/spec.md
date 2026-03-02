# Especificação de Funcionalidade: wow-token-price

**Feature Branch**: `001-wow-token-price`  
**Criada em**: 2026-03-01  
**Status**: Rascunho  
**Input**: Descrição do usuário: "eu preciso construir uma aplicação que inicialmente, quero que pegue dados da casa de leilões de world of warcraft e guarde esses dados. Eu vou utilizar o docker para subir o meu banco de dados e guardar os dados. o documento PDF na raiz do projeto especifica melhor o meu objetivo, mas no momento quero que foque em trazer o preço atual ou mais atualizado da WoW token (ficha de wow), lembre de fazer tudo em portuguÊs brasileiro"

## Cenários de Usuário e Testes *(obrigatório)*

### User Story 1 - Obter Preço Atual da Ficha de WoW (Prioridade: P1)

Como um jogador de World of Warcraft (WoW) ou economista virtual, quero ser capaz de consultar o preço atualizado da "Ficha de WoW" (WoW Token) no mercado da casa de leilões do jogo, para que eu possa planejar minhas compras de tempo de jogo ou ouro de forma eficiente.

**Por que esta prioridade**: Obter a informação central da Ficha de WoW é o núcleo do pedido inicial, sendo essencial para habilitar qualquer análise ou cruzamento de dados posterior. Sem esta coleta básica, o aplicativo não entrega seu valor mínimo.

**Teste Independente**: A história pode ser testada ativando o serviço de busca de dados; ele deve acessar com sucesso a fonte de informações de World of Warcraft e salvar o valor atualizado da Ficha de WoW sem erros no banco de dados isolado.

**Cenários de Aceitação**:

1. **Dado** que o serviço de busca de preços está programado para executar e o banco de dados está online, **Quando** for o momento de uma nova checagem, **Então** o sistema deverá salvar pelo menos um novo registro contendo com sucesso o valor em ouro da Ficha de WoW no banco de dados.
2. **Dado** que um usuário deseja verificar os dados armazenados, **Quando** o banco de dados for consultado por preços da Ficha, **Então** o sistema deverá retornar o último preço encontrado e a respectiva data/hora do registro de forma legível.

---

### Casos de Borda (Edge Cases)

- **O que acontece quando a API da casa de leilões / fonte de dados oficial fica indisponível?** O sistema deve lidar com falhas de conexão de forma graciosa e registrar tentativas falhas sem travar ou interromper ciclos futuros de captura de dados.
- **O que acontece se o token de serviço ou credencial de acesso tiver expirado?** O sistema deve registrar um alerta crítico e pausar a execução até a renovação correta das políticas de acesso para evitar o bloqueio total da fonte consumida.

## Requisitos *(obrigatório)*

### Requisitos Funcionais

- **FR-001**: O Sistema DEVE comunicar-se com uma fonte de dados oficial (como a API oficial da Blizzard) de onde consiga extrair as listagens públicas de "WoW Token" atreladas à Casa de Leilões (Auction House).
- **FR-002**: O Sistema DEVE permitir apenas a extração e o registro não-intrusivo e de apenas leitura (método "Read Only") destas informações, sem alterar o estado do jogo do lado do servidor oficial.
- **FR-003**: O Sistema DEVE registrar os preços focando inicialmente na Região das Américas (US/LA/SA). O design do banco de dados e as chamadas da API devem ser concebidos de forma extensível, prevendo que no futuro o sistema rastreará outros itens além da ficha de WoW (WoW Token).
- **FR-004**: O Sistema DEVE gravar dados do token persistidos unicamente num banco de dados conteinerizado, garantindo assim isolamento da infraestrutura base da máquina.
- **FR-005**: O Sistema DEVE possuir uma forma rudimentar de exibição do último preço atualizado para garantir facilidade de validação (ex. logs consolidados).

### Entidades Chave *(incluir se a feature envolver dados)*

- **Registro de Preço de Item (Genérico)**: Representa um ponto de preço único no tempo para um item específico. Atributos chave: ID do Item (ex: Token ID vs Ore ID), Preço (Valor em ouro/Gold), Timestamp da checagem.
- **Região/Reino**: Metadado atrelado de onde os dados de leilão foram puxados (foco inicial: Americas).
- **Fonte do Leilão Central**: Metadados atrelados à requisição da API de onde vêm os tokens.

## Critérios de Sucesso *(obrigatório)*

### Resultados Mensuráveis

- **SC-001**: O sistema é capaz de salvar um novo preço atualizado da Ficha do WoW com sucesso pelo menos 1 vez ininterruptamente nas varreduras pré-determinadas (100% de taxa de conclusão viável em cenários com conexão normal).
- **SC-002**: Verificação de disponibilidade da Ficha se dá em até 3 segundos após uma requisição disparada pelo software.
- **SC-003**: O sistema de persistência isolado (Banco operando via Container) recupera do zero seus próprios esquemas para recebimento de dados sem falhar em uma inicialização limpa.
