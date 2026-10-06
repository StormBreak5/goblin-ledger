# Requisitos

> Fonte: documento do TC *TCII-N2-IND-Itzac Albertin-Guiliano Rangel Alves* (Google Drive), exportado em 06/10/2026, já com as atualizações pós-implementação. O documento do TC é a fonte da verdade: se houver divergência, atualize este arquivo a partir dele.

## Requisitos funcionais (Quadro 04)

| ID | Nome | Descrição |
| --- | --- | --- |
| RF01 | Autenticação de Usuário | O sistema deve permitir que os usuários criem contas, realizem login e recuperem senhas de acesso. |
| RF02 | Busca de Itens | O sistema deve prover uma barra de pesquisa para que o usuário localize itens da Auction House por nome ou ID. |
| RF03 | Visualização de Histórico | O sistema deve renderizar gráficos interativos exibindo a série temporal histórica de preços (Bid e Buyout) e volume de um item selecionado. |
| RF04 | Projeção Preditiva (ML) | O sistema deve calcular e exibir no gráfico uma linha de tendência preditiva baseada no modelo de Machine Learning. |
| RF05 | Configuração de Alertas | O sistema deve permitir que um usuário autenticado configure alertas de preço (alvo de compra ou venda) para itens específicos que estejam presentes em sua lista de favoritos, podendo estabelecer limites numéricos para gatilhos. |
| RF06 | Disparo de Notificações Ativa | O sistema deve notificar o usuário (via interface web ou e-mail) quando o preço atual de um item favoritado e monitorado cruzar o limite configurado no alerta (RF05), consultando a última base consolidada pelo Provider. |
| RF07 | Ingestão de Dados via Providers | O sistema deve, de forma autônoma e assíncrona, consumir os dados de mercado através de uma interface de Provider (inicialmente configurada para a API da Blizzard). A rotina deve lidar com paginação e falhas de rede antes de repassar o payload para o banco de dados. |
| RF08 | Retreinamento do Modelo | O sistema deve possuir um trabalho automatizado para retreinar periodicamente os algoritmos preditivos com os dados mais recentes ingeridos. |
| RF09 | Gestão de Itens Favoritos | O sistema deve permitir que o usuário autenticado adicione, remova e visualize uma lista customizada de "Itens Favoritos", criando um dashboard de acesso rápido para monitoramento focado. |
| RF10 | Sanitização e Padronização de Dados | A camada de backend deve aplicar transformações nos dados brutos recebidos pelos Providers, padronizando moedas (conforme RN01) e removendo anomalias estruturais antes do armazenamento persistente, garantindo a qualidade do dataset para o modelo de Machine Learning. |
| RF11 | Ingestão do Histórico Passado do Preço de Itens | O sistema deverá consumir o histórico de preço dos itens e também dos eventos/atualizações via dados expostos por sites ou serviços como TSM/Undermine Journal (itens) e scrapping de sites como Wowhead/WoW Wiki serviços como a Undermine Exchange (itens) e por páginas como a Wikipedia e a Warcraft Wiki, além da API da Blizzard (eventos). |
| RF12 | Treinamento Inicial | O sistema deve possuir uma rotina dedicada para processar o histórico consolidado de dados (proveniente do RF11) e realizar o treinamento primário dos algoritmos de Machine Learning, estabelecendo o modelo preditivo inicial para cada item antes de sua disponibilização no ambiente de produção. |

> Atenção: nas linhas do RF03, RF07 e RF11 deste quadro ainda aparecem trechos que o autor marcou para remoção na revisão de 06/10/2026: "(Bid e Buyout)", "paginação" e a lista antiga de fontes do RF11 (TSM/Undermine Journal, Wowhead/WoW Wiki). Para a implementação, valem as especificações detalhadas abaixo (Quadros 11, 15 e 19) e os casos de uso.

## Requisitos não funcionais (Quadro 05)

| ID | Característica (ISO/IEC 25010) | Descrição |
| --- | --- | --- |
| RNF01 | Eficiência de Desempenho — Comportamento Temporal | A interface com o usuário deve ser desenvolvida em Next.js, garantindo renderização otimizada (SSR/SSG) e componentização reativa. |
| RNF02 | Manutenibilidade — Reusabilidade | A camada de regras de negócio, integração de APIs e processamento de Machine Learning deve ser implementada em Python, aproveitando seu ecossistema de bibliotecas de dados. |
| RNF03 | Confiabilidade — Maturidade | A persistência de dados transacionais e das séries temporais deve ser realizada em um banco de dados relacional. |
| RNF04 | Eficiência de Desempenho — Capacidade | O processo de ingestão de dados deve ser capaz de processar e persistir o payload JSON das APIs. |
| RNF05 | Usabilidade — Operabilidade | A aplicação web deve seguir os princípios de Design Responsivo, garantindo usabilidade adequada em desktops, tablets e smartphones. |
| RNF06 | Segurança — Confidencialidade | As senhas dos usuários devem ser armazenadas utilizando algoritmos de hashing seguros, e a comunicação cliente-servidor deve ocorrer via HTTPS. |
| RNF07 | Confiabilidade — Disponibilidade / Tolerância a Falhas | A arquitetura do sistema deve ser desenhada para suportar eventuais indisponibilidades das APIs dos sistemas, exibindo mensagens de erro amigáveis e o último dado em cache. |
| RNF08 | Manutenibilidade — Modularidade | O código-fonte deve estar versionado e organizado segundo padrões de arquitetura limpa, facilitando futuras extensões para mercados reais. |

## Especificação detalhada dos RFs (Quadros 09 a 20)

### RF01 – Autenticação de Usuário

O sistema deve permitir que os usuários criem contas, realizem login e recuperem senhas de acesso. Intenção do usuário: "Quero acessar minha conta de forma segura para gerenciar meus alertas de preços e minha lista de itens favoritos. "O sistema deve validar as credenciais. Caso a senha esteja incorreta ou o e-mail não exista, uma mensagem de erro genérica ("Credenciais inválidas") deve ser exibida. Durante o cadastro, a senha será criptografada (hash Bcrypt). A sessão autenticada é mantida por um token JWT válido por 24 horas, contadas a partir do login.

**Regras de negócio:** RN11; RN18; RN19; RN20; RN21; RN22

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| E-mail | Texto | 150 | Sim | Formato de e-mail válido |
| Senha | Texto | 255 | Sim | Alfanumérico e Caracteres Especiais (mínimo de 8 caracteres) |
| Região (US/EU) | Texto | 2 | Sim (Cadastro) | Domínio Geográfico válido |

### RF02 – Busca de Itens

O sistema deve prover uma barra de pesquisa para que o usuário localize itens da Auction House por nome ou ID.Intenção do usuário: "Quero pesquisar um item específico para visualizar seu gráfico de histórico e a projeção de preços do Machine Learning. "Se o item buscado for localizado, o sistema renderiza a página de detalhes.

**Regras de negócio:** Não se aplica

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| Termo de Busca | Texto | 100 | Sim | Alfanumérico |

### RF03 – Visualização de Histórico

O sistema deve renderizar gráficos interativos exibindo a série temporal histórica de preços e volume de um item selecionado. Intenção do usuário: "Quero ver como o preço e o volume de negociação desse item se comportaram no último mês para entender se ele está valorizando ou perdendo valor. "A interface gráfica deve construir a linha de preço atual utilizando o primeiro quartil (25%) dos preços dos leilões ativos para representar o custo real de aquisição. Além disso, a aplicação deve classificar e alertar o usuário caso os dados exibidos apresentem latência em relação à fonte oficial.

**Regras de negócio:** RN06; RN09

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Item | Inteiro | - | Sim | Numérico |
| Janela de Tempo | Texto | 10 | Sim | '14D', '30D', '90D', '365D' ou 'ALL' |

### RF04 – Projeção Preditiva

O sistema deve calcular e exibir no gráfico uma linha de tendência preditiva baseada no modelo de Machine Learning. Intenção do usuário: "Quero visualizar a projeção matemática para o preço desse item nos próximos dias para decidir se estoco ou vendo meus materiais agora. "A projeção só deve ser calculada e renderizada para itens que tenham um volume de negociação aceitável (mais de 50 unidades nos últimos 7 dias). O sistema omitirá a linha preditiva caso a acurácia matemática do modelo para aquele item não atinja o limiar mínimo exigido.

**Regras de negócio:** RN02; RN03; RN07; RN10; RN17

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Item | Inteiro | - | Sim | Numérico |
| Data da Projeção | Data | - | Sim | DD/MM/AAAA |

### RF05 – Configuração de Alertas

O sistema deve permitir que um usuário autenticado configure alertas de preço (alvo de compra ou venda) para itens específicos que estejam presentes em sua lista de favoritos, podendo estabelecer limites numéricos para gatilhos. Intenção do usuário: "Quero criar uma regra para o sistema me avisar automaticamente quando um item que eu quero flipar atingir o valor que eu considero barato. "O sistema deve checar se o limite de rastreadores ativos do usuário não foi excedido (Cota de Alertas) e filtrar injeções artificiais de itens por bots antes de consolidar o monitoramento.

**Regras de negócio:** RN08; RN12

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| Chave externa do usuário | UUID | - | Sim | Alfanumérico |
| ID do Item | Inteiro | - | Sim | Numérico |
| Preço Alvo | Inteiro | - | Sim | Numérico |
| Tipo de Gatilho | Texto | 10 | Sim | ‘COMPRA’ ou ‘VENDA’ |

### RF06 – Disparo de Notificações Ativa

O sistema deve notificar o usuário (via interface web ou e-mail) quando o preço atual de um item favoritado e monitorado cruzar o limite configurado no alerta (RF05), consultando a última base consolidada pelo Provider .Intenção do usuário: "Quero receber uma mensagem no meu e-mail ou na tela do app assim que a condição de preço que eu configurei for atingida, para que eu possa logar no jogo e realizar a transação. "Para evitar falsos positivos causados por anomalias (como um único item postado muito barato), o gatilho só deve ser ativado validando o "Preço Atual" baseado no primeiro quartil (25%) dos preços dos leilões ativos.

**Regras de negócio:** RN06

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Alerta | Inteiro | - | Sim | Numérico |
| ID do Usuário | UUID | - | Sim | Alfanumérico |
| Canal de Envio | Texto | 20 | Sim | ‘WEB’ ou ‘EMAIL’ |
| Preço de Disparo | Inteiro | - | Sim | Numérico |

### RF07 – Ingestão de Dados via Providers

O sistema deve, de forma autônoma e assíncrona, consumir os dados de mercado através de uma interface de Provider (atualmente configurada para a API da Blizzard). A rotina deve lidar com falhas de rede antes de repassar o payload para o banco de dados. Intenção do sistema: "Coletar os dados mais recentes de leilões periodicamente para manter a base atualizada, garantindo que os usuários e modelos de IA tenham acesso à cotação mais recente. "O trabalho de ingestão deve respeitar o intervalo mínimo de 60 minutos para não estourar o limite de requisições da Blizzard (Rate Limit). Caso a API falhe, o Provider deve isolar o erro para não derrubar a aplicação, permitindo que a interface continue exibindo os dados em cache. O processo também atualiza os leilões que expiraram. O preço da Ficha do WoW (Token WoW) é coletado em endpoint próprio da API a cada 15 minutos e armazenado em série separada dos demais itens.

**Regras de negócio:** RN04; RN05; RN06; RN09; RN11; RN14

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Reino/Servidor | Inteiro | - | Sim | Numérico |
| Região (US/EU) | Texto | 2 | Sim | Alfabético (RN11) |
| Payload JSON | JSON | - | Sim | Estrutura de dados da API |

### RF08 – Retreinamento do Modelo

O sistema deve possuir um trabalho automatizado para retreinar periodicamente os algoritmos preditivos com os dados mais recentes ingeridos. Intenção do sistema: "Atualizar os pesos matemáticos do modelo de Machine Learning baseando-se nas últimas flutuações do mercado, para evitar que a linha de tendência fique defasada. "Antes do retreinamento, o sistema deve garantir que o conjunto de dados esteja higienizado: descartando valores absurdos (outliers gerados por spoofing/market manipulation), ignorando itens sem volume de negociação suficiente e focando em equipamentos que ainda tenham relevância no jogo (iLvl).

**Regras de negócio:** RN02; RN03; RN07

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Item | Inteiro | - | Sim | Numérico |
| Data/Hora do Último Treino | Data/Hora | - | Sim | Timestamp |
| Histórico de Preços | Array de Inteiros | - | Sim | Numérico Absoluto |

### RF09 – Gestão de Itens Favoritos

O sistema deve permitir que o usuário autenticado adicione, remova e visualize uma lista customizada de "Itens Favoritos", criando um dashboard de acesso rápido para monitoramento focado. Intenção do usuário: "Quero favoritar os itens que eu mais negocio na Auction House para ter um painel de acesso rápido, sem precisar pesquisar o nome deles toda vez que eu entrar no sistema. "

**Regras de negócio:** —

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| Chave externa do usuário | UUID | - | Sim | Alfanumérico |
| ID do item | Inteiro | - | Sim | Numérico |
| Ação | Texto | 10 | Não | ‘ADICIONAR’ ou ‘REMOVER’ |

### RF10 – Sanitização e Padronização de Dados

A camada de backend deve aplicar transformações nos dados brutos recebidos pelos Providers, padronizando moedas (conforme RN01) e removendo anomalias estruturais antes do armazenamento persistente, garantindo a qualidade do dataset para o modelo de Machine Learning. Intenção do sistema: "Receber o arquivo bruto da API oficial, converter todos os valores financeiros para a menor unidade possível (Cobre) e limpar sujeiras nos dados antes de salvar no banco, para que o modelo de IA não aprenda com dados corrompidos. "Essa padronização exige que valores como Ouro e Prata sejam convertidos usando a lógica estrita de 1 Ouro = 10000 Cobre e 1 Prata = 100 Cobre.

**Regras de negócio:** RN01; RN12

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| Payload Bruto do Provider | JSON | - | Sim | Estrutura não tratada da API |
| Preço Original do Item | Numérico | - | Sim | Numérico |
| Preço Convertido (Saída) | Inteiro | - | Sim | Numérico Absoluto |

### RF11 – Ingestão do Histórico Passado do Preço de Itens

O sistema deverá consumir o histórico de preço dos itens e também dos eventos/atualizações via dados expostos por serviços como a Undermine Exchange (itens) e por páginas como a Wikipedia e a Warcraft Wiki, além da API da Blizzard (eventos). Intenção do sistema: "Necessito carregar uma grande base de dados retroativa (meses ou anos) de fontes de terceiros para não começar o banco de dados vazio, viabilizando o treinamento inicial da IA." Os dados obtidos de terceiros devem ser obrigatoriamente harmonizados, convertidos para o padrão de moeda do sistema (Cobre) e higienizados. Além disso, as datas de grandes atualizações (patches) capturadas via web scraping devem ser injetadas como variáveis categóricas, impedindo que o modelo interprete quedas abruptas de preço por obsolescência como flutuações naturais de mercado.

**Regras de negócio:** RN15; RN16; RN17; RN11; RN23

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| Região (US/EU) | Texto | 2 | Sim | US ou EU (RN11) |
| Identificador do item | Inteiro | - | Sim | Numérico |
| Arquivo de dados históricos | Binário | - | Sim | Estrutura de dados retroativa |
| Data do Evento/Patch | Data | - | Sim | DD/MM/AAAA |

### RF12 – Treinamento Inicial

O sistema deve possuir uma rotina dedicada para processar o histórico consolidado de dados (proveniente do RF11) e realizar o treinamento primário dos algoritmos de Machine Learning, estabelecendo o modelo preditivo inicial para cada item antes de sua disponibilização no ambiente de produção. Intenção do sistema: "Preciso analisar todo o histórico de preços já higienizado para gerar o primeiro modelo matemático preditivo de cada item, garantindo que o sistema já nasça com inteligência ao entrar em produção. "O treinamento utiliza a base harmonizada e aplica a marcação estocástica de eventos para refinar a precisão.

**Regras de negócio:** RN15; RN16; RN17

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Item | Inteiro | - | Sim | Numérico |
| Vetor de Preços Harmonizado | Array de Inteiros | - | Sim | Numérico Absoluto |
| Período Histórico Disponível | Inteiro | - | Sim | Dias contínuos |
| Variáveis Categóricas (Patches) | Array de Datas | - | Sim | Marcação Estocástica |

