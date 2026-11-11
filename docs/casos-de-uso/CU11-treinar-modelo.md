# CU11 – Treinar Modelo

> **PROVISÓRIO.** O CU11 já está no TC (seção 6.4.11), mas o TC ainda não tem as mudanças de `docs/Alterações do TC - modelo global (para colar) v4.docx`, que separam os itens que treinam o modelo dos itens que recebem projeção. Este arquivo já traz o texto com a v4. Enquanto o TC e o `docs/` não forem reexportados, as regras deste arquivo prevalecem sobre `docs/regras-de-negocio.md` e sobre `docs/requisitos.md`. Qualquer divergência encontrada na implementação deve ser avisada ao autor, para que o texto do TC saia corrigido.

**Situação no código (20/10/2026):** C1, C2 e C3 implementados. O pipeline foi portado de `estudos/lstm/` para `backend/src/ml/` e roda no serviço `modelo` do docker-compose (pandas e TensorFlow), que consome a fila de `execucao_treinamento` e agenda o retreinamento. C1: commits `7cf75f2` (treinamento inicial, versão 1 na região US) e `c6816d5` (dias encerrados, situação "Ignorada" e liberados sem amostra de treino). C2: retreinamento semanal (commit `c9622de`). C3: consolidação diária das predições, agendada às 03:00 UTC. A série diária da Undermine passou a ser atualizada todo dia pelo CU10-C1 (commit `9a2b296`). Testes em `backend/tests/modelo/` (no container: `docker compose run --rm modelo-testes`) e em `backend/tests/integration/test_cu11_*.py`. Os relatórios das etapas 1 a 2f do estudo estão em `docs/relatorio-etapa*.md`.

## Descrição

Este caso de uso tem como principal função preparar o histórico consolidado dos itens, treinar o modelo preditivo global de preços com os itens do conjunto de treinamento e avaliá-lo individualmente para cada item elegível à projeção, inclusive os que não participaram do treinamento, liberando a projeção somente para os itens em que o modelo atinge o limiar mínimo de acurácia, além de mantê-lo atualizado por meio de retreinamentos periódicos e de registrar diariamente as predições e o seu desempenho para fins de auditoria.

- **Requisitos associados:** RF08 – Retreinamento do Modelo; RF12 – Treinamento Inicial
- **Cenários:**
  - Cenário 01 – Executar treinamento inicial
  - Cenário 02 – Retreinar o modelo periodicamente
  - Cenário 03 – Consolidar predições diárias
- **Diagramas de atividades:** `docs/diagramas-atualizados/cu11c01.svg`, `cu11c02.svg` e `cu11c03.svg`.

## Regras de negócio

Texto do TC atual, com as mudanças da v4 (RN10 e RN15 alteradas; RN27 nova).

- **RN02 – Filtro de Liquidez para Modelagem Preditiva:** Os algoritmos de Machine Learning só devem processar e gerar projeções preditivas para itens que possuam quantidade média ofertada superior a 50 unidades nos últimos 7 dias. A quantidade ofertada é utilizada como indicador de liquidez, pois a API oficial não informa as vendas realizadas. Itens com baixa liquidez não possuem dados estatísticos suficientes para inferências estocásticas confiáveis, devendo exibir apenas o histórico gráfico. Na prática, o critério restringe a projeção às commodities, negociadas em grande volume em toda a região; os equipamentos, vendidos em poucas unidades por reino, exibem apenas o histórico.
- **RN03 – Mitigação de Outliers e Market Spoofing:** Para evitar que o treinamento do modelo preditivo seja corrompido por manipulações de mercado, o pipeline de dados deve descartar registros cujo preço diário seja 300% superior ou 90% inferior à Média Móvel Exponencial (EMA) de 14 dias do referido item, calculada somente com os registros anteriores já aceitos. Quando o preço permanecer fora dessa faixa, do mesmo lado, por 7 registros seguidos, considera-se uma mudança real de patamar: os registros próximos da mediana dessa sequência são aceitos e a EMA recomeça a partir deles. Se a mudança for de 1.000 vezes ou mais em relação ao patamar anterior, são exigidos 28 registros seguidos. No início da série, o primeiro patamar só é considerado confirmado depois de 7 registros aceitos.
- **RN10 – Limiar de Precisão Preditiva:** O sistema deve omitir projeções de ML que não atinjam um padrão mínimo de acurácia matemática. A projeção de um item só é exibida se a mediana do erro percentual absoluto (MdAPE) das previsões do modelo para o item, medida no período de teste sobre os dias com preço observado, for igual ou inferior a 15% e menor que a do modelo ingênuo, que repete o último preço observado. A avaliação exige no mínimo 30 dias com previsões avaliadas; o item que ainda não os possui, como um item lançado recentemente, permanece com a projeção bloqueada e é reavaliado no retreinamento seguinte. A mediana é usada no lugar da média (MAPE) porque os erros percentuais crescem muito quando o valor real é pequeno (HYNDMAN; ATHANASOPOULOS, 2018), e o preço diário, por ser o menor anúncio do dia, está sujeito a quedas isoladas que distorceriam a média. *(alterada na v4)*
- **RN13 – Snapshot de Estado (Auditoria ML):** O sistema deve consolidar diariamente suas predições contra a realidade para fins de auditoria acadêmica, registrando, para cada item com projeção liberada, a data, a versão do modelo, o valor predito, o valor real observado e o erro. Se a mediana do erro percentual dos últimos 7 dias ultrapassar o limiar da RN10, a projeção do item é bloqueada até o próximo retreinamento.
- **RN15 – Volume Mínimo para Treinamento:** Um item só integra o conjunto de treinamento do modelo preditivo se a base de dados contiver um período histórico contínuo predeterminado de mínimo 6 meses de registros consolidados para o respectivo ativo. O período mínimo corresponde a 180 dias contínuos, e lacunas de até 3 dias sem registros não interrompem a continuidade do período. A regra seleciona os itens usados para ajustar o modelo; a projeção de um item que não integra o conjunto de treinamento segue a RN27. *(alterada na v4)*
- **RN16 – Harmonização de Dados de Terceiros:** Dados históricos retroativos obtidos via extração externa (Undermine Exchange, web scraping) devem obrigatoriamente ser convertidos, tipados e higienizados para o exato padrão relacional do SGBD do sistema e da padronização de moeda, garantindo a integridade do dataset antes do treinamento inicial. Cada registro identifica a sua origem e a sua granularidade (diária ou horária). As séries de origens diferentes não são misturadas no treinamento: o modelo utiliza a série diária da Undermine Exchange, única com histórico contínuo, e a série horária do ciclo da Blizzard não é incorporada a ela.
- **RN17 – Marcação Estocástica de Eventos:** Datas de grandes atualizações sistêmicas do jogo (patches/expansões) mapeadas no banco histórico devem ser injetadas como variáveis categóricas para o algoritmo. Isso impede que o modelo interprete quedas abruptas de preço causadas por obsolescência de itens como flutuações naturais de mercado. Além de patches e expansões, são registrados como eventos as temporadas, os eventos sazonais e os eventos recorrentes do jogo.
- **RN24 – Normalização das Variáveis do Modelo:** Para o treinamento e a predição, os preços e as quantidades recebem transformação logarítmica e são padronizados pela média e pelo desvio-padrão dos últimos 90 dias do próprio item; as variações de preço e os indicadores derivados são divididos por constantes globais. Em todos os casos, os valores resultantes são limitados ao intervalo entre −1 e 1. O dia da semana é representado por seno e cosseno, as contagens de dias são limitadas a 60 e divididas por 60 (exceto a distância até o próximo patch), e as categorias do item são representadas por vetores aprendidos (embeddings). Dias sem registro são preenchidos com o último valor observado por até 3 dias e marcados como não observados. A saída do modelo é padronizada pela média e pelo desvio-padrão de cada dia do horizonte, calculados no período de treinamento.
- **RN25 – Integridade Temporal do Treinamento:** Toda variável de entrada do modelo deve ser calculada apenas com informações disponíveis no dia da previsão. O histórico considera somente os dias já encerrados. Como a data de anúncio dos eventos não é registrada, um patch só é considerado conhecido a partir de 14 dias antes da sua data. O histórico é dividido em ordem cronológica, com as mesmas datas de corte para todos os itens, em 70% para treinamento, 20% para validação e 10% para teste (HYNDMAN; ATHANASOPOULOS, 2018). A validação é usada para interromper o treinamento e escolher a configuração do modelo; o teste é usado uma única vez, para medir o erro final e decidir a liberação da projeção de cada item. Amostras cujos dias previstos atravessem uma data de corte são descartadas. As constantes de normalização são calculadas exclusivamente com os dados do período de treinamento e armazenadas junto com a versão do modelo.
- **RN26 – Política de Retreinamento:** O modelo preditivo é retreinado semanalmente, após o reinício semanal do jogo, e só substitui o modelo vigente se apresentar erro menor que o dele no mesmo período de teste; caso contrário, o modelo vigente é mantido.
- **RN27 – Histórico Mínimo para Projeção:** A projeção de um item, tenha ele integrado ou não o conjunto de treinamento do modelo, só pode ser calculada e avaliada quando o item possuir ao menos 60 dias de histórico diário, necessários para a padronização móvel das variáveis e para compor a janela de entrada do modelo. Itens com histórico inferior exibem apenas o histórico gráfico. *(nova na v4)*

Mapeamento de rastreabilidade (seção 3.6.2, com a v4):

- **RF04 (Projeção Preditiva com ML):** Estritamente governado por RN02, RN10, RN13, RN27.
- **RF08 (Retreinamento do Modelo):** Validado por RN02, RN03, RN10, RN13, RN15, RN17, RN24, RN25, RN26, RN27.
- **RF11 (Ingestão do Histórico Passado):** Validado por RN11, RN15, RN16, RN17, RN23.
- **RF12 (Treinamento Inicial do Modelo):** Estritamente governado por RN02, RN03, RN10, RN15, RN16, RN17, RN24, RN25, RN27.

Termos do glossário (novos na v4):

- **Conjunto de Treinamento:** Itens elegíveis à projeção que também são aptos ao treinamento (RN15), cujo histórico é usado para ajustar os pesos do modelo preditivo.
- **Item Elegível à Projeção:** Item que atende ao filtro de liquidez (RN02) e ao histórico mínimo para projeção (RN27), tenha ou não integrado o conjunto de treinamento; a sua projeção é liberada ou bloqueada conforme a RN10.

## Requisito Funcional 04 – [RF 04]: Projeção Preditiva

O sistema deve calcular e exibir no gráfico uma linha de tendência preditiva baseada no modelo de *Machine Learning*.

**Intenção do usuário:** "Quero visualizar a projeção matemática para o preço desse item nos próximos dias para decidir se estoco ou vendo meus materiais agora."

A projeção cobre os próximos 7 dias e só deve ser calculada e renderizada para itens que tenham uma quantidade ofertada aceitável (RN02) e o histórico mínimo para projeção (RN27), tenham ou não sido utilizados no treinamento do modelo. O sistema omitirá a linha preditiva caso a acurácia matemática do modelo para aquele item não atinja o limiar mínimo exigido (RN10).

- **Regras de negócio:** RN02; RN10; RN13; RN27

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Item | Inteiro | - | Sim | Numérico |
| Data da Projeção | Data | - | Sim | DD/MM/AAAA |

## Requisito Funcional 08 – [RF 08]: Retreinamento do Modelo

O sistema deve possuir um trabalho automatizado para retreinar periodicamente os algoritmos preditivos com os dados mais recentes ingeridos.

**Intenção do sistema:** "Atualizar os pesos matemáticos do modelo de *Machine Learning* baseando-se nas últimas flutuações do mercado, para evitar que a linha de tendência fique defasada."

Antes do retreinamento, o sistema deve garantir que o conjunto de dados esteja higienizado: descartando valores absurdos (*outliers* gerados por *spoofing*/*market manipulation*) e ignorando itens sem quantidade ofertada suficiente. O retreinamento atualiza o modelo global com os dados mais recentes e só substitui o modelo vigente quando o novo apresenta desempenho superior (RN26). A cada retreinamento, a projeção de todos os itens elegíveis, inclusive os que não integram o conjunto de treinamento, é reavaliada (RN10, RN27).

- **Regras de negócio:** RN02; RN03; RN10; RN13; RN15; RN17; RN24; RN25; RN26; RN27

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Item | Inteiro | - | Sim | Numérico |
| Versão do Modelo | Inteiro | - | Sim | Numérico sequencial |
| Data/Hora do Treinamento | Data/Hora | - | Sim | Timestamp |
| Erro do Modelo por Item (MdAPE) | Decimal | - | Sim | Percentual |
| Situação da Projeção do Item | Texto | 9 | Sim | 'Liberada', 'Bloqueada' ou 'Ignorada' |

## Requisito Funcional 12 – [RF 12]: Treinamento Inicial

O sistema deve possuir uma rotina dedicada para processar o histórico consolidado de dados (proveniente do RF11) e realizar o treinamento primário dos algoritmos de *Machine Learning*, estabelecendo um modelo preditivo global, treinado com o histórico dos itens do conjunto de treinamento e avaliado individualmente para cada item elegível à projeção, inclusive os que não participaram do treinamento, antes de sua disponibilização no ambiente de produção.

**Intenção do sistema:** "Preciso analisar todo o histórico de preços já higienizado para gerar o primeiro modelo matemático preditivo, garantindo que o sistema já nasça com inteligência ao entrar em produção."

O treinamento utiliza a base harmonizada e aplica a marcação estocástica de eventos para refinar a precisão. As variáveis de entrada do modelo, a sua normalização e o treinamento estão descritos na seção 5.12.2.

- **Regras de negócio:** RN02; RN03; RN10; RN15; RN16; RN17; RN24; RN25; RN27

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Item | Inteiro | - | Sim | Numérico |
| Janela de Entrada | Inteiro | - | Sim | 30 dias |
| Variáveis de Entrada | Matriz numérica | - | Sim | Normalizadas entre −1 e 1 (RN24) |
| Período Histórico Disponível | Inteiro | - | Sim | Dias contínuos (RN15) |
| Divisão dos Períodos | Percentual | - | Sim | Treinamento 70%, validação 20% e teste 10% (RN25) |
| Variáveis Categóricas (Eventos) | Array de Datas | - | Sim | Marcação Estocástica (RN17) |
| Horizonte de Previsão | Inteiro | - | Sim | 7 dias |

## Variáveis de entrada do modelo (seção 5.12.2)

O quadro a seguir apresenta as variáveis de entrada do modelo preditivo global, agrupadas em variáveis de mercado observadas no passado, variáveis de calendário e de eventos conhecidas antecipadamente e atributos fixos do item, com a forma de cálculo e de normalização de cada uma (RN24). A saída do modelo corresponde aos log-retornos do preço do item em cada um dos próximos 7 dias, em relação ao último preço observado, posteriormente convertidos em valor absoluto na unidade Cobre (RN01).

| Nº | Variável | Tipo | Faixa | Cálculo e normalização |
| --- | --- | --- | --- | --- |
| 1 | Log-retorno diário do preço | Mercado (passado) | −1 a 1 | ln(pₜ ÷ pₜ₋₁), dividido por uma constante global (percentil 99 do módulo dos retornos no treinamento) e limitado ao intervalo. |
| 2 | Nível do preço | Mercado (passado) | −1 a 1 | (ln pₜ − média dos últimos 90 dias) ÷ desvio dos últimos 90 dias do próprio item, limitado a ±3 e dividido por 3. |
| 3 | Quantidade ofertada | Mercado (passado) | −1 a 1 | ln(1 + quantidade), padronizado como a variável 2. |
| 4 | Desvio em relação à média móvel | Mercado (passado) | −1 a 1 | ln(preço ÷ EMA de 14 dias da RN03), dividido por uma constante global e limitado ao intervalo. |
| 5 | Volatilidade de 7 dias | Mercado (passado) | 0 a 1 | Desvio-padrão dos log-retornos dos últimos 7 dias (com ao menos 5 dias), dividido pelo percentil 99 do treinamento e limitado ao intervalo. |
| 6 | Variação do índice da subclasse | Mercado (passado) | −1 a 1 | Média dos log-retornos dos demais itens da mesma classe e subclasse no dia, ponderada pela quantidade ofertada, dividida por uma constante global e limitada ao intervalo. A subclasse é identificada junto com a classe, porque o código da subclasse só é único dentro da classe. |
| 7 | Distância ao preço de venda ao vendedor | Mercado (passado) | −1 a 1 | ln(preço ÷ preço pago pelo vendedor do jogo), dividido por uma constante global e limitado; vale 0 para itens sem esse preço. |
| 8 | Dado observado | Mercado (passado) | 0 ou 1 | Indica se o registro do dia foi observado ou preenchido com o último valor (RN24). |
| 9 | Dia da semana | Calendário (futuro conhecido) | −1 a 1 | Seno e cosseno de 2π × dia ÷ 7. |
| 10 | Dias desde o último patch | Evento (futuro conhecido) | 0 a 1 | Limitado a 60 e dividido por 60. |
| 11 | Dias até o próximo patch | Evento (futuro conhecido) | 0 a 1 | Dias até o patch divididos por 14 quando ele está a até 14 dias; vale 1 quando o patch ainda não é considerado conhecido (RN25). |
| 12 | Expansão ou pré-patch nos próximos 14 dias | Evento (futuro conhecido) | 0 ou 1 | Indicador; o pré-patch é o primeiro patch de cada nova versão maior do jogo. |
| 13 | Temporada ativa e dias desde o seu início | Evento (futuro conhecido) | 0 a 1 | Indicador de temporada ativa e contagem de dias limitada a 60 e dividida por 60. |
| 14 | Evento sazonal ativo | Evento (futuro conhecido) | 0 ou 1 | Indicador. |
| 15 | Classe e subclasse do item | Item (fixa) | índice (0 = desconhecida) | A classe e o par classe e subclasse são convertidos em índices do vocabulário do período de treinamento (0 para os que não aparecem nele). Cada índice é convertido em um vetor aprendido pelo modelo (*embedding*), de 4 dimensões para a classe e 8 para a subclasse. Por ser categórica, a variável não é normalizada numericamente. |
| 16 | Qualidade e nível de item | Item (fixa) | 0 a 1 | Qualidade dividida por 5; nível de item normalizado pelo mínimo e pelo máximo do treinamento. |
| 17 | Possui preço de venda ao vendedor | Item (fixa) | 0 ou 1 | Indicador. |
| 18 | Item do tipo commodity | Item (fixa) | 0 ou 1 | Indicador; commodity é o item cujo histórico vem do arquivo de commodities da região. |

A rede neural é composta por uma camada LSTM de 64 unidades, que recebe a janela de entrada com as variáveis que variam no tempo (variáveis 1 a 14), seguida de uma camada de *dropout* de 20%. A saída da LSTM é combinada aos atributos fixos do item (variáveis 16 a 18) e aos vetores aprendidos da classe e da subclasse (variável 15) e passa por uma camada densa de 32 neurônios até a camada de saída, com um valor para cada dia do horizonte de previsão.

O modelo é treinado com os dados do período de treinamento dos itens do conjunto de treinamento, minimizando o erro absoluto médio (MAE) entre os log-retornos previstos e os observados, com o otimizador Adam e com a interrupção do treinamento quando o erro no período de validação deixa de diminuir (RN25). A minimização do erro absoluto leva o modelo a prever a mediana dos valores futuros, e não a sua média (HYNDMAN; ATHANASOPOULOS, 2018; GNEITING, 2011), o que torna o treinamento coerente com a métrica que decide a liberação da projeção de cada item, a mediana do erro percentual absoluto (RN10).

Fundamentação (seção 3.1.2.3): Quando há um grande número de séries temporais relacionadas, uma alternativa ao treinamento de um modelo por série é o treinamento de um modelo global, ajustado simultaneamente sobre todas as séries. Montero-Manso e Hyndman (2021) demonstram que modelos globais podem alcançar precisão igual ou superior à dos modelos locais, aproveitando padrões compartilhados entre as séries. Salinas et al. (2020) aplicam esse princípio a redes neurais recorrentes LSTM (HOCHREITER; SCHMIDHUBER, 1997) no método DeepAR, treinado sobre milhares de séries de demanda. No Goblin Ledger, o modelo global permite que efeitos raros na história de um único item, como o lançamento de um *patch*, sejam aprendidos a partir de sua ocorrência simultânea em milhares de itens. Além disso, como o modelo não recebe nenhum identificador do item, apenas variáveis em escala relativa ao histórico do próprio item e os seus atributos, ele também pode prever itens que não participaram do treinamento, como os lançados depois dele, desde que possuam histórico suficiente. Em todos os casos, a capacidade preditiva é avaliada individualmente para cada item.

## CU11 - C1 – Treinar Modelo - Cenário Executar Treinamento Inicial

- **Objetivo:** Gerar o primeiro modelo preditivo global a partir do histórico consolidado dos itens do conjunto de treinamento, liberando a projeção somente para os itens elegíveis em que o modelo atinge o limiar mínimo de acurácia, tenham ou não participado do treinamento.
- **Pré-condição:** O Admin deve possuir acesso às funções administrativas da plataforma e a cobertura histórica dos itens deve ter sido validada (CU10 - Cenário 03).
- **Pós-condição:** O modelo global é registrado com as suas métricas, e cada item elegível tem a sua projeção classificada como "Liberada" ou "Bloqueada".
- **Atores:** Admin
- **Ativação:** O Admin solicita a execução do treinamento inicial.

### Fluxo principal

1. O Admin solicita a execução do treinamento inicial, informando a região.
2. O sistema seleciona os itens elegíveis à projeção, que atendem ao filtro de liquidez, ao histórico mínimo para projeção e ao critério de relevância de equipamentos, e, entre eles, os itens do conjunto de treinamento, classificados como "Apto ao treinamento".
3. O sistema recupera a série histórica diária harmonizada de cada item selecionado.
4. O sistema descarta os registros cujo preço seja 300% superior ou 90% inferior à média móvel exponencial de 14 dias do item.
5. O sistema calcula as variáveis de entrada de cada item, incluindo as variáveis de calendário e as variáveis categóricas dos eventos do jogo registrados no período.
6. O sistema normaliza as variáveis de entrada.
7. O sistema separa o histórico em períodos de treinamento, validação e teste, com as mesmas datas de corte para todos os itens e preservando a ordem cronológica dos registros.
8. O sistema treina o modelo preditivo global com os dados do período de treinamento dos itens do conjunto de treinamento, interrompendo o treinamento quando o erro no período de validação deixa de diminuir.
9. O sistema avalia o modelo no período de teste de cada item elegível, inclusive os que não integram o conjunto de treinamento, calculando o erro das predições do item e o erro do modelo ingênuo.
10. O sistema verifica, para cada item elegível, se o modelo atinge o limiar mínimo de acurácia com o mínimo de dias de previsões avaliadas.
11. O sistema registra a versão do modelo, com a data e a hora do treinamento e as métricas obtidas, e libera a projeção dos itens aprovados.
12. O sistema apresenta ao Admin o resumo do treinamento, com a quantidade de itens com projeção liberada, de itens com projeção bloqueada e de itens ignorados.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Nenhum item apto ao treinamento

- **1.1** No passo 2, o sistema não encontra itens para o conjunto de treinamento.
- **1.2** O sistema exibe a mensagem: "Nenhum item apto ao treinamento. Verifique a validação da cobertura histórica".
- **1.3** Fim.

#### Fluxo Alternativo 2 - Treinamento em andamento

- **2.1** No passo 1, o sistema identifica que já existe um treinamento em andamento.
- **2.2** O sistema exibe a mensagem: "Já existe um treinamento em andamento".
- **2.3** Fim.

#### Fluxo Alternativo 3 - Série insuficiente após a higienização

- **3.1** No passo 4, o sistema identifica que os registros restantes do item não são suficientes para compor as amostras do modelo.
- **3.2** O sistema classifica a projeção do item como "Ignorada", registrando o motivo, e o exclui do treinamento e da avaliação.
- **3.3** Retorna ao passo 3 do fluxo principal para os demais itens.

#### Fluxo Alternativo 4 - Projeção do item reprovada na avaliação

- **4.1** No passo 10, o sistema identifica que o modelo não atinge o limiar mínimo de acurácia para o item.
- **4.2** O sistema registra as métricas do item e mantém a sua projeção bloqueada.
- **4.3** Retorna ao passo 10 do fluxo principal para os demais itens.

#### Fluxo Alternativo 5 - Avaliação insuficiente do item

- **5.1** No passo 10, o sistema identifica que o item não possui o mínimo de dias com previsões avaliadas no período de teste.
- **5.2** O sistema registra o motivo e mantém a projeção do item bloqueada até a sua reavaliação no próximo retreinamento.
- **5.3** Retorna ao passo 10 do fluxo principal para os demais itens.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha no treinamento do modelo

- **1.1** No passo 8, o treinamento não converge ou é interrompido por esgotamento de recursos.
- **1.2** O sistema descarta o modelo em treinamento, mantém os registros anteriores e registra a falha em log.
- **1.3** O sistema exibe a mensagem: "Não foi possível concluir o treinamento do modelo. Verifique o log de execução".
- **1.4** Fim.

#### Fluxo Exceção 2 - Falha na comunicação com o Banco de Dados

- **2.1** Nos passos 3 ou 11, o sistema não consegue acessar ou gravar os dados devido a uma falha interna de I/O ou queda de conexão.
- **2.2** O sistema interrompe o treinamento, mantém os registros anteriores e registra a falha em log.
- **2.3** O sistema exibe a mensagem: "Não foi possível concluir o treinamento no momento. Tente novamente mais tarde".
- **2.4** Fim.

## CU11 - C2 – Treinar Modelo - Cenário Retreinar o Modelo Periodicamente

- **Objetivo:** Atualizar o modelo preditivo global com os dados mais recentes ingeridos, evitando que a linha de tendência fique defasada em relação às últimas flutuações do mercado.
- **Pré-condição:** Deve existir um modelo preditivo treinado (Cenário 01).
- **Pós-condição:** O modelo vigente é substituído pelo novo modelo, quando este apresenta desempenho superior, ou é mantido, e a situação da projeção de cada item é atualizada.
- **Atores:** Admin
- **Ativação:** O agendador de tarefas dispara a rotina de retreinamento após o reinício semanal do jogo (RN26).

### Fluxo principal

1. O agendador de tarefas dispara a rotina de retreinamento.
2. O sistema seleciona os itens elegíveis à projeção, que atendem ao filtro de liquidez, ao histórico mínimo para projeção e ao critério de relevância de equipamentos, e, entre eles, os itens do conjunto de treinamento, que atendem à cobertura histórica mínima.
3. O sistema recupera a série histórica de cada item selecionado, incluindo os dados ingeridos desde o último treinamento.
4. O sistema higieniza, calcula, normaliza e separa as variáveis conforme os passos 4 a 7 do Cenário 01.
5. O sistema treina um novo modelo global com os itens do conjunto de treinamento.
6. O sistema avalia o novo modelo e o modelo vigente no mesmo período de teste.
7. O sistema verifica se o novo modelo apresenta erro menor que o do modelo vigente.
8. O sistema substitui o modelo vigente pelo novo, registrando a versão, a data e a hora do treinamento e as métricas obtidas.
9. O sistema atualiza a situação da projeção de cada item elegível, liberando os itens que atingem o limiar mínimo de acurácia com o mínimo de dias de previsões avaliadas e bloqueando os demais.
10. O sistema registra em log o resumo do retreinamento.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Item deixou de ser elegível à projeção

- **1.1** No passo 2, o sistema identifica que um item com projeção liberada não é mais elegível à projeção.
- **1.2** O sistema bloqueia a projeção do item.
- **1.3** Retorna ao passo 2 do fluxo principal para os demais itens.

#### Fluxo Alternativo 2 - Novo modelo com desempenho inferior

- **2.1** No passo 7, o sistema identifica que o novo modelo não supera o modelo vigente.
- **2.2** O sistema descarta o novo modelo, mantém o vigente e registra as métricas obtidas.
- **2.3** Retorna ao passo 9 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha durante o retreinamento

- **1.1** Nos passos 3 a 8, o sistema não consegue concluir o processamento devido a uma falha interna de I/O, queda de conexão ou esgotamento de recursos.
- **1.2** O sistema interrompe o retreinamento e mantém o modelo vigente.
- **1.3** O sistema registra a falha em log.
- **1.4** Fim.

## CU11 - C3 – Treinar Modelo - Cenário Consolidar Predições Diárias

- **Objetivo:** Registrar diariamente as predições do modelo para os itens com projeção liberada e confrontá-las com os valores reais observados, mantendo o histórico de desempenho para auditoria acadêmica e para a identificação de projeções defasadas.
- **Pré-condição:** Deve existir ao menos um item com a projeção liberada.
- **Pós-condição:** As predições do dia e o erro observado de cada item ficam registrados no banco de dados.
- **Atores:** Admin
- **Ativação:** O agendador de tarefas dispara a rotina diária de consolidação.

### Fluxo principal

1. O agendador de tarefas dispara a rotina diária de consolidação das predições.
2. O sistema atualiza o histórico diário dos itens com projeção liberada por meio da importação incremental do histórico (CU10 - Cenário 01).
3. O sistema recupera, para cada item com projeção liberada, as predições registradas para o dia encerrado.
4. O sistema recupera o preço diário consolidado do item no mesmo dia.
5. O sistema calcula o erro de cada predição em relação ao valor real.
6. O sistema registra o snapshot do dia, com a data, o item, a versão do modelo, o valor predito, o valor real e o erro (RN13).
7. O sistema gera, com o modelo vigente, as predições do item para os próximos 7 dias e as registra, deixando-as disponíveis para a consulta da projeção (CU05).
8. Após processar todos os itens, o sistema registra em log a conclusão da consolidação.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Nenhuma predição registrada para o dia

- **1.1** No passo 3, o sistema não encontra predições registradas para o dia encerrado, como no primeiro dia após a liberação da projeção.
- **1.2** Retorna ao passo 7 do fluxo principal.

#### Fluxo Alternativo 2 - Valor real indisponível

- **2.1** No passo 4, o sistema não encontra o preço diário consolidado do item, como em uma falha na importação do histórico.
- **2.2** O sistema registra o snapshot sem o valor real e sem o erro, marcando-os como "N/D".
- **2.3** Retorna ao passo 7 do fluxo principal.

#### Fluxo Alternativo 3 - Desempenho degradado do item

- **3.1** No passo 5, o sistema identifica que a mediana do erro percentual do item nos últimos 7 dias ultrapassa o limiar mínimo de acurácia (RN13).
- **3.2** O sistema bloqueia a projeção do item até o próximo retreinamento.
- **3.3** Retorna ao passo 3 do fluxo principal para os demais itens.

#### Fluxo Alternativo 4 - Degradação generalizada do modelo

- **4.1** No passo 8, o sistema identifica que a quantidade de itens com projeção bloqueada por degradação no dia ultrapassa 20% dos itens com projeção liberada.
- **4.2** O sistema antecipa o retreinamento do modelo (Cenário 02).
- **4.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 3, 4, 6 ou 7, o sistema não consegue acessar ou gravar os dados devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema desfaz os registros do dia e registra a falha em log.
- **1.3** O sistema reprocessa o dia não consolidado no próximo disparo da rotina.
- **1.4** Fim.

## Observações para a implementação

Este caso de uso ainda não está implementado no sistema. Abaixo estão as decisões tomadas no estudo, as sugestões de implementação e o que ainda precisa ser confirmado com o autor (CLAUDE.md, regra 3). Onde houver conflito com o texto acima, vale o que está aqui, e o autor deve ser avisado para corrigir o texto do TC.

### Resultados do estudo (validação)

A base completa tem 6.562 séries (6.547 commodities), cerca de 8,07 milhões de linhas e 3,79 milhões de amostras de treino. Todas as escolhas foram feitas na validação, com 3 sementes e regra de decisão definida antes de cada experimento. O teste não foi usado: ele é o do treinamento inicial no sistema (RN25).

| Modelo (6.484 itens, média de 3 sementes) | Mediana do MdAPE por item | Mediana do MAPE por item | Itens liberados (RN10, sem o mínimo de dias) |
| --- | --- | --- | --- |
| Ingênuo | 24,17% | 47,19% | — |
| Regressão linear | 28,02% | 44,51% | — |
| LSTM, perda Huber (etapa 2b) | 22,67% | 38,66% | 603 |
| **LSTM, perda MAE (configuração final, etapa 2e)** | **20,62%** | **37,92%** | **1.090** |

- **Configuração final (congelada):** variáveis 1 a 18 com a 14 agregada, sem máscara, perda MAE. Testadas e reprovadas: eventos detalhados e máscara (2b), item da expansão vigente e idade do item (2d), redução da taxa de aprendizado e LSTM de 128 unidades (2e).
- **Custo da perda MAE:** as medidas que dão peso aos erros grandes pioram um pouco (MAPE médio por item de 59,7% para 61,4%; MAPE h7 de 62,3% para 63,7%). Grave e relate as três medidas (MdAPE, MAPE e RMSE, risco R02).
- **Generalização (etapa 2f, perda MAE; a 2c mediu o mesmo com a perda Huber):**
  - itens reservados do treino tiveram o mesmo erro de quando foram vistos: diferença mediana de 0,00 a 0,02 ponto no MdAPE, menor que o ruído entre sementes;
  - os 755 itens sem nenhuma amostra de treino (quase todos da expansão Midnight) foram previstos melhor que pelo ingênuo em 76% a 81% dos casos;
  - itens fora da seleção empataram com o ingênuo, mas porque são ilíquidos: com a mesma liquidez, itens do treino e de fora se comportam igual. O modelo supera o ingênuo a partir de umas 20 unidades ofertadas em média, e o limiar de 50 da RN02 é conservador;
  - o mínimo de 30 dias da RN10 retirou 223 de 1.018 liberações na validação, quase todas de itens novos com só 8 dias avaliados (o corte da validação cai poucas semanas depois da expansão). No período de teste do sistema, esses itens já têm meses de histórico.
- **Tempo de treino:** de 20 a 35 minutos na CPU com a perda MAE (de 44 a 68 épocas de cerca de 30 s).

### Itens que treinam o modelo e itens que recebem projeção

É a principal mudança da v4.

| Conjunto | Critérios | Uso |
| --- | --- | --- |
| **Itens elegíveis à projeção** | RN02 (quantidade média > 50 nos últimos 7 dias) e RN27 (ao menos 60 dias de histórico diário) | são avaliados no período de teste e recebem a situação "Liberada" ou "Bloqueada" (RN10) |
| **Conjunto de treinamento** | os elegíveis que também são aptos ao treinamento (RN15, tabela `aptidao_treinamento`) | ajustam os pesos e as constantes de normalização |

- **Constantes e vocabulário (RN24 e RN25):** são calculados só com as linhas do período de treinamento do **conjunto de treinamento** e aplicados a todos os itens elegíveis. Uma classe ou subclasse que não existe no treino vira a categoria 0 (desconhecida). É exatamente o que o estudo faz com `preparar_dados.py --normalizacao-de` e `prever.py`.
- **Avaliação (passos 9 e 10 do C1):** o modelo prevê o período de teste de **todos** os itens elegíveis, inclusive os que não integram o conjunto de treinamento. A situação de cada um sai da RN10.
- **Variável 6 (índice da subclasse):** calcule-a com todos os itens selecionados no dia, não só com o conjunto de treinamento.
- **Subclasse pelo par (classe, subclasse) nas variáveis 6 e 15** (etapa 2i do estudo, `docs/relatorio-etapa2i.md`): a chave é classe × 1000 + subclasse, porque o código da subclasse da API só é único dentro da classe (a subclasse 5 é "Comida e bebida" nos consumíveis e "Tecido" nos materiais de profissão). Um par que não aparece no treino vira a subclasse desconhecida (0).
- **Itens novos:** um item lançado depois do treino entra como elegível quando completa 60 dias de histórico. Ele é avaliado no período de teste do próximo retreinamento e liberado quando tiver os 30 dias avaliados da RN10. Na prática, isso leva uns 3 meses a partir do lançamento, sem retreinar o modelo para isso.
- **Itens fora do treino no resumo do C1:** informe quantos itens liberados não integram o conjunto de treinamento.
- **Liberados sem amostra de treino (resumo do C1 e do C2):** informe também quantos itens liberados não têm nenhuma amostra no período de treinamento. São os lançados depois do fim desse período: integram o conjunto de treinamento pela RN15, mas não ajustaram os pesos. No treinamento inicial (versão 1, região US) foram 292 dos 1.307 liberados.

### Arquitetura

- **Código do pipeline.** Porte o código de `estudos/lstm/` para o backend, por exemplo em `backend/src/ml/`, e leve junto os testes do estudo. Correspondência:

  | Arquivo do estudo | Parte do pipeline |
  | --- | --- |
  | `preparar_dados.py` | variáveis, normalização (inclusive a de outra versão do modelo, `--normalizacao-de`) e janelas |
  | `dataset.py` | tensores e assinatura da normalização |
  | `treinar.py` | rede e treino (perda MAE por padrão) |
  | `prever.py` | previsão com uma versão já treinada, que confere a assinatura da normalização |
  | `avaliar.py` | desnormalização, métricas e RN10 (com o mínimo de dias) |

  Os scripts de experimento (`comparar.py`, `transicao.py`, `generalizacao.py`, `regressao_linear.py`) não precisam ir para o sistema. Se o estudo e as regras acima divergirem, vale o texto das regras, e o autor deve ser avisado.
- **Decisão pendente: onde o TensorFlow roda.** O worker usa a imagem `python:3.11-alpine`, e o TensorFlow não tem pacote para Alpine.
  - Sugestão: criar um serviço novo, `modelo`, no `docker-compose.yml`, com imagem `python:3.11-slim` e `tensorflow-cpu`. Ele acessa o mesmo banco e um volume `modelos/`, tem o seu próprio agendador e roda o treino (C1 e C2) e a consolidação diária (C3).
  - Alternativa: trocar a imagem do worker. Fica mais pesado, e o treino disputa processador com a ingestão.
- **Artefatos.** Cada versão do modelo fica em `modelos/v{versão}/`, com três arquivos: `modelo.keras`, `normalizacao.json` (constantes, vocabulário, escala do alvo, datas de corte e assinatura, RN25) e `treino.json`. Para prever com uma versão, use sempre as constantes dela.
- **Tabelas novas, via Alembic** (sugestão, a confirmar no plano):

  | Tabela | Conteúdo |
  | --- | --- |
  | `modelo_preditivo` | versão, região, data e hora do treinamento, datas de corte, mediana do MdAPE e do MAPE do modelo e do ingênuo no teste, caminho dos artefatos, se é a versão vigente |
  | `execucao_treinamento` | tipo (inicial ou retreinamento), origem (Admin ou agendado), status (`EXECUTANDO`, `SUCESSO`, `FALHA`), início, fim, resumo (liberados, bloqueados, ignorados e liberados fora do conjunto de treinamento), erro |
  | `projecao_item` | item, série/região, versão, se integra o conjunto de treinamento, dias avaliados, MdAPE, MdAPE do ingênuo, MAPE, situação (`LIBERADA`, `BLOQUEADA`, `IGNORADA`), motivo, data da atualização |
  | `predicao_diaria` (RN13) | data da previsão, item, série, versão, h (1 a 7), data prevista, preço previsto em Cobre, preço real, erro |

  - `execucao_treinamento` atende o C1-FA2. Como no CU10-C1-FA4, uma execução "em andamento" há mais de N horas deixa de bloquear.
  - Motivos de bloqueio em `projecao_item`: "acima do limiar", "não supera o ingênuo", "avaliação insuficiente" (C1-FA5), "deixou de ser elegível" (C2-FA1) e "degradação" (C3-FA3). Para `IGNORADA`, "série insuficiente" (C1-FA3).
  - Em `predicao_diaria`, preço real e erro nulos correspondem a "N/D". Chave única: (item, série, versão, data da previsão, h).
- **Mensagens ao usuário:** exatamente as dos cenários.

### C1 – Treinamento inicial

- **Disparo pelo Admin,** no mesmo padrão de `/admin/history-import`:
  - `POST /admin/model-training`, que responde 202 e roda de forma assíncrona;
  - `GET /admin/model-training/{id}` e `GET /admin/model-training`, para o resumo;
  - tela em `frontend/src/app/admin/treinamento`.
- **Passo 2 (seleção):**
  - elegíveis: RN02 pela quantidade média dos últimos 7 dias; RN27 pelo número de dias desde o primeiro registro diário do item;
  - conjunto de treinamento: os elegíveis que estão como aptos em `aptidao_treinamento` (RN15).
- **Passo 3 (RN16):** só entram registros com `origem = 'UNDERMINE'`, `granularidade = 'DIARIA'` e sem `anomalia`. O preço da Undermine é o menor preço do dia. A série horária da Blizzard (1º quartil, RN06) não entra.
- **Passo 4 (RN03):** como em `rn03_por_serie` do estudo:
  - a EMA de 14 dias usa só os preços anteriores já aceitos;
  - o preço é descartado se for maior que 4 × EMA ou menor que 0,1 × EMA;
  - 7 preços seguidos fora da faixa, do mesmo lado, confirmam um novo patamar, aceito a partir da mediana da sequência;
  - num salto de 1.000× ou mais, são exigidos 28;
  - o primeiro patamar da série só vale depois de 7 preços aceitos.
- **Passos 5 a 7:** como em `estudos/lstm/preparar_dados.py`:
  - variáveis 1 a 18, sempre calculadas item a item. A variável 14 é agregada (`f_evento`, "algum festival ativo"). O pré-patch é o primeiro patch de cada versão maior. Commodity é o item com `source_region` igual ao id de commodities da região;
  - preenchimento de até 3 dias;
  - divisão 70/20/10 por data de calendário;
  - constantes calculadas só com o treino do conjunto de treinamento;
  - descarte das amostras cujos dias previstos atravessam uma data de corte.
- **Passo 8 (rede e treino):**
  - arquitetura: LSTM(64) → Dropout(0,2) → junção com os atributos fixos e os embeddings de classe (4) e subclasse (8) → Dense(32, GELU) → Dense(7). A GELU é da etapa 2g do estudo (`docs/relatorio-etapa2g.md`);
  - **versões treinadas antes das etapas 2g e 2i** (v1 a v4 da região US): continuam com a ReLU e com o código da subclasse sozinho. O `normalizacao.json` delas não tem os campos `ativacao` e `subclasse_por_classe`, que são lidos como `relu` e `false`. O C2 avalia o vigente e o C3 faz as previsões com a chave da subclasse e a rede da própria versão;
  - **perda MAE**, sem máscara (decidido nas etapas 2b e 2e);
  - otimizador Adam, taxa fixa de 0,001;
  - lotes de 512 montados sob demanda, com 400 mil amostras sorteadas a cada época;
  - EarlyStopping na validação, com paciência 10 e volta para a melhor época.
- **Passos 9 e 10 (RN10, decidida):**
  - o erro é calculado por item, no período de teste, só sobre os dias observados (dias preenchidos e descartados pela RN03 não contam);
  - a projeção é liberada se o **MdAPE** for de no máximo 15%, menor que o MdAPE do ingênuo e medido em pelo menos **30 dias** com previsões avaliadas (datas de origem distintas, `dias_avaliados` no `avaliar.py`);
  - abaixo dos 30 dias, a projeção fica bloqueada com o motivo "avaliação insuficiente" (FA5);
  - grave também o MAPE, o RMSE e o erro relativo ao ingênuo, para o relatório.
- **FA3:** o item sem amostras suficientes depois da higienização tem a projeção `IGNORADA`, com o motivo.
- **Dias encerrados (RN25):** o C1, o C2 e o C3 usam só os registros anteriores à data UTC da execução, que é um parâmetro (`data_execucao`) para os testes. O resumo registra o último dia usado (`ultimo_dia`).
- **FE1:** cobre treino que produz NaN (TerminateOnNaN) e falta de memória.

### C2 – Retreinamento

- **Agendamento:** depois do reinício semanal, que nos EUA é na terça-feira. Configurável em `MODELO_RETREINO_CRON`; sugestão: terça, 18:00 UTC.
- **Novos períodos:** a divisão 70/20/10 é recalculada até a data mais recente.
- **Comparação (RN26):** o modelo vigente é avaliado no novo período de teste com as suas próprias constantes; o modelo novo, com as dele.
- **Situação dos itens (passo 9):** é recalculada para **todos** os elegíveis, com o modelo que ficar vigente. É aqui que itens novos passam a ser liberados, quando atingem os 30 dias avaliados.
- **Resultado:**
  - modelo novo melhor: vira o vigente;
  - modelo novo pior: é descartado, mas os artefatos e as métricas ficam registrados.

Decisões da implementação (19/10/2026):

- **Disparo (passo 1):** o agendador do serviço `modelo` (APScheduler, `MODELO_RETREINO_CRON`, padrão `0 18 * * tue`, em UTC) registra uma execução `RETREINAMENTO`/`AGENDADO` na fila para cada região com modelo vigente. Use o nome do dia: no APScheduler 3, o número 2 é quarta-feira, não terça.
  - Região sem modelo vigente não é retreinada; região que já tem uma execução aguardando ou em andamento não recebe outra. Os dois casos só vão para o log.
  - A checagem é por região. A fila executa um treinamento por vez, então US e EU podem esperar juntos. O FA2 do pedido do Admin (C1) continua valendo para qualquer região.
  - Disparo perdido: com o computador dormindo na terça às 18:00, o retreinamento é registrado ao acordar, uma vez só (coalesce, sem limite de atraso). Desligado, o APScheduler não guarda o disparo; ao iniciar, o serviço `modelo` registra o retreinamento de cada região com modelo vigente que não tem execução concluída desde o último disparo do cron, uma vez.
  - O comando `python -m src.modelo_worker --retreinar US` segue o mesmo caminho (sem região: todas com modelo vigente; `--aguardar` espera o fim e mostra o resumo). O C3-FA4 vai usá-lo.
- **Passos 2 a 5:** os mesmos do C1, com o mesmo código. A série considera só os dias encerrados (RN25), e a divisão 70/20/10 é recalculada até o último deles.
- **Passo 6 (RN26):** o modelo novo e o vigente preveem as **mesmas** amostras do período de teste novo. O vigente usa as próprias constantes, vocabulário, faixa de nível e escala do alvo (o `normalizacao.json` da versão dele), aplicados às mesmas variáveis brutas e aos cortes novos. A conferência é só a das constantes (a assinatura sem os cortes). A base é lida e higienizada uma vez só; se a configuração das variáveis brutas tiver mudado desde a versão vigente, elas são recalculadas para ela, a partir da mesma leitura.
- **Passo 7:** a mediana do MdAPE por item (a métrica da RN10), calculada só nos alvos avaliados pelos dois modelos (mesmo item, dia de origem e dia do horizonte). O novo substitui o vigente se a mediana for **estritamente menor**.
- **Passo 8:** o novo vira o vigente; o anterior recebe `substituido_em`.
- **FA2:** o modelo novo fica registrado em `modelo_preditivo` com `descartado = true` e as métricas, e os artefatos dele são mantidos (com `avaliacao_teste_vigente.parquet`, a avaliação do vigente no mesmo teste).
- **Passo 9:** a situação de **todos** os elegíveis é recalculada com o modelo que ficou vigente, na avaliação do período de teste novo (RN10 com o mínimo de 30 dias); os bloqueios por degradação (C3-FA3) caem aqui. Com o vigente mantido, "integra o conjunto de treinamento" e "liberado sem amostra de treino" se referem ao conjunto e ao período de treinamento dele.
- **FA1:** os itens da região em `projecao_item` que deixaram de ser elegíveis ficam `BLOQUEADA`, "deixou de ser elegível", com as métricas e a versão da última avaliação. O resumo conta quantos deixaram de ser elegíveis nesta execução e quantos deles estavam liberados. O FA1 é decidido no passo 2, mas gravado junto com o passo 9, para uma falha não mexer na situação dos itens.
- **Passo 10 (resumo, na execução e no log):** versão vigente anterior e versão nova, decisão, mediana do MdAPE de cada modelo e itens comparados, liberados, bloqueados por motivo e ignorados, liberados sem amostra de treino e fora do conjunto de treinamento, itens que deixaram de ser elegíveis e o último dia usado. A tela do Admin mostra o tipo e, no retreinamento, a comparação.
- **Aviso:** se o último dia encerrado da série tiver mais de 3 dias (`MODELO_SERIE_DESATUALIZADA_DIAS`), o resumo leva "série diária desatualizada". Não bloqueia. O C1 também o mostra.
- **FE1:** uma falha nos passos 3 a 8 (I/O, banco, NaN ou falta de memória) deixa a execução como `FALHA`. O vigente e `projecao_item` não mudam, e os artefatos do modelo novo são removidos. Um conjunto de treinamento vazio no retreinamento também é tratado como FE1, porque o C2 não tem o FA1 do C1. Como o ator do C2 é o Sistema, não há mensagem ao usuário: o resumo mostra a etapa e o erro do log.

### C3 – Consolidação diária

Decisões da implementação (20/10/2026):

- **Disparo (passo 1):** o agendador do serviço `modelo` roda a consolidação todo dia às 03:00 UTC (`MODELO_CONSOLIDACAO_CRON`), uma hora depois da importação diária do worker. Disparo perdido como no C2: com o computador dormindo, roda ao acordar uma vez só; desligado, o serviço confere ao iniciar e roda uma vez. O comando `python -m src.modelo_worker --consolidar` roda na hora. Duas consolidações nunca rodam juntas (trava do PostgreSQL).
- **Passo 2:** a consolidação não importa nada; usa a importação diária do worker (CU10-C1). Antes de começar, confere se a de hoje terminou; em andamento, ou ainda não começada (o computador acabou de ligar e o worker vai rodar a importação perdida), espera até `MODELO_CONSOLIDACAO_ESPERA_MINUTOS` (60). Se ela falhou ou não rodou, segue com um aviso no registro, e os valores reais que faltarem ficam "N/D" (FA2).
- **Dia de referência:** D é o último dia encerrado, a véspera da data UTC da execução.
- **Passos 3 a 6 (RN13):** cada predição com `data_prevista = D`, de qualquer versão do modelo (até 7 por item, uma por horizonte, feitas de D−7 a D−1), recebe o preço diário da Undermine do dia (o mesmo registro que o modelo usa, sem anomalia) e `erro_pct = |previsto − real| ÷ real`. Sem preço real, os dois ficam nulos e `consolidado_em` é preenchido: é o "N/D" do FA2, diferente de "ainda não consolidado".
- **FA1:** sem predição para D (como nos primeiros dias), o sistema segue para o passo 7; o FA3 também fica para o dia seguinte, como no diagrama.
- **FA3 (RN13):** o erro do item é a mediana do `erro_pct` das predições com `data_prevista` de D−6 a D (`MODELO_DEGRADACAO_DIAS`), em todos os horizontes, **só da versão que deu a situação atual do item** (decisão do autor: as de versões anteriores são preenchidas, mas não bloqueiam o modelo novo). Acima do limiar da RN10 (15%), com ao menos `MODELO_DEGRADACAO_MINIMO_ALVOS` (14) erros, a projeção fica `BLOQUEADA`, "degradação", até o próximo retreinamento (o passo 9 do C2 recalcula todos os elegíveis).
- **Passo 7:** cada item com projeção liberada depois do FA3 recebe as predições de D+1 a D+7, com o modelo vigente e a normalização dele, a partir da janela de 30 dias que termina em D (só dados até D, RN25). As variáveis são calculadas como no treinamento; a variável 6 usa todos os elegíveis do dia. É lido só o trecho de `MODELO_PREVISAO_HISTORICO_DIAS` (200) dias: a janela de 30, a padronização de 90 e uns 80 dias de aquecimento da EMA e do patamar da RN03, que é uma máquina de estado iniciada no primeiro preço lido. Conferido com os dados reais de 19/10/2026: lendo o histórico inteiro, os mesmos itens recebem previsão, 99,9% das previsões são idênticas e a maior diferença é 0,39% (num item); a leitura cai de 163 s para 27 s. Preço previsto em Cobre (RN01) = preço de D × exp(log-retorno previsto). O item liberado sem os 30 dias de janela válidos em D (como no treinamento: dia sem preço, com o preço descartado pela RN03 ou logo depois de um deles) não recebe previsão naquele dia e é contado no registro (`itens_sem_janela`).
- **Passo 8 e FA4:** a conclusão vai para o log e para `consolidacao_diaria`. Se os bloqueados por degradação no dia passarem de `MODELO_DEGRADACAO_GERAL` (20%) dos liberados no início do dia, o retreinamento é registrado pelo mesmo caminho do agendador do C2, que não duplica a execução que já está na fila.
- **FE1:** cada dia é consolidado numa transação; a falha desfaz o dia, vai para o log e para o registro (`FALHA`). O próximo disparo reprocessa, na ordem, os dias que não têm `SUCESSO`: os atrasados recebem os valores reais e o FA3; as previsões novas só são geradas para o dia de referência mais recente (sem previsões retroativas), e os dias sem previsão ficam como lacuna (FA1).
- **Trava comum:** o C1 (passo 11), o C2 (passo 9) e o C3 (FA3) gravam a situação dos itens com a mesma trava do PostgreSQL, nunca ao mesmo tempo.
- **CU05 (consulta da previsão) não faz parte do CU11:** o C3 só grava as previsões e o desempenho; não há tela de projeção.

### Valores configuráveis

Os valores marcados como decididos já foram fixados pelo autor. Os demais são sugestões a confirmar.

| Variável de ambiente | Valor | Regra |
| --- | --- | --- |
| `MODELO_JANELA_DIAS` | 30 | RF12 |
| `MODELO_HORIZONTE_DIAS` | 7 | RF04 |
| `MODELO_ZSCORE_DIAS` | 90 | RN24 |
| `MODELO_HISTORICO_MINIMO_DIAS` | 60 | RN27 |
| `MODELO_PROPORCAO_TREINO` / `MODELO_PROPORCAO_VALIDACAO` | 0,70 / 0,20 (decidido) | RN25 |
| `MODELO_ANTECEDENCIA_PATCH_DIAS` | 14 | RN25 |
| `MODELO_METRICA_RN10` / `MODELO_LIMIAR_RN10` | mdape / 0,15 (decidido) | RN10 |
| `MODELO_MINIMO_DIAS_RN10` | 30 | RN10 |
| `MODELO_RN03_CONFIRMACAO` / `MODELO_RN03_SALTO_ABSURDO` / `MODELO_RN03_CONFIRMACAO_ABSURDO` | 7 / 1000 / 28 (decidido) | RN03 |
| `MODELO_DEGRADACAO_DIAS` | 7 | RN13 |
| `MODELO_DEGRADACAO_GERAL` | 0,20 | C3-FA4 |
| `MODELO_EPOCAS_MAX` / `MODELO_PACIENCIA` / `MODELO_LOTE` | 100 / 10 / 512 | treino |
| `MODELO_AMOSTRAS_POR_EPOCA` | 400000 | treino |
| `MODELO_PERDA` / `MODELO_MASCARA` | mae / false (decidido) | treino |
| `MODELO_EVENTOS_DETALHADOS` | false (decidido) | variável 14 |

### Testes (um por fluxo)

Use dados sintéticos (`estudos/lstm/gerar_sinteticos.py`) e um modelo mínimo nos testes, por exemplo LSTM de 4 unidades e 1 época, para a suíte continuar rápida.

- C1:
  - `test_cu11_c1_fluxo_principal_treina_e_libera_itens` (inclua um item elegível fora do conjunto de treinamento e confira que ele é avaliado)
  - `test_cu11_c1_fa1_nenhum_item_apto`
  - `test_cu11_c1_fa2_treinamento_em_andamento`
  - `test_cu11_c1_fa3_serie_insuficiente_item_ignorado`
  - `test_cu11_c1_fa4_projecao_reprovada_rn10`
  - `test_cu11_c1_fa5_avaliacao_insuficiente_rn10`
  - `test_cu11_c1_fe1_falha_no_treinamento`
  - `test_cu11_c1_fe2_falha_no_banco`
- C2:
  - `test_cu11_c2_fluxo_principal_substitui_modelo_rn26`
  - `test_cu11_c2_fa1_item_deixou_de_ser_elegivel`
  - `test_cu11_c2_fa2_novo_modelo_inferior_mantem_vigente`
  - `test_cu11_c2_fe1_falha_mantem_vigente`
- C3:
  - `test_cu11_c3_fluxo_principal_registra_snapshot_rn13`
  - `test_cu11_c3_fa1_sem_predicao_do_dia`
  - `test_cu11_c3_fa2_valor_real_indisponivel`
  - `test_cu11_c3_fa3_degradacao_bloqueia_item_rn13`
  - `test_cu11_c3_fa4_degradacao_generalizada_antecipa_retreino`
  - `test_cu11_c3_fe1_falha_no_banco_reprocessa`
- Regras (portados de `estudos/lstm/tests`):
  - `test_rn24_ida_e_volta_recupera_o_preco`
  - `test_rn24_calculos_por_item`
  - `test_rn24_normalizacao_de_outra_versao_em_itens_fora_do_treino`
  - `test_rn25_sem_vazamento_do_futuro`
  - `test_rn25_janelas_respeitam_os_cortes`
  - `test_rn25_dias_ate_patch_respeita_antecedencia`
  - `test_rn03_descarta_pico_com_ema_dos_aceitos`
  - `test_rn03_confirma_novo_patamar_em_7_dias`
  - `test_rn03_salto_absurdo_exige_28_dias`
  - `test_rn10_libera_por_mdape_quem_supera_o_ingenuo`
  - `test_rn10_exige_minimo_de_dias_avaliados`
  - `test_rn27_historico_minimo_para_projecao`

### Limitações conhecidas

- **Itens novos:** só recebem projeção depois de uns 3 meses: 60 dias de histórico (RN27) e 30 dias avaliados (RN10), com a reavaliação semanal do C2.
- **Itens ilíquidos e equipamentos:** ficam sem projeção (RN02). Abaixo de umas 20 unidades ofertadas em média, o modelo empata com o ingênuo (etapa 2f).
- **Troca de expansão:** nos itens da expansão que sai, o modelo quase empata com o ingênuo (razão de 0,93 a 0,96 a 7 dias). Só há uma troca no período de treino, e as duas trocas observadas tiveram comportamentos opostos (etapa 2d).
- **RN03:** pode descartar movimentos reais no lançamento de expansões.
- **Dados:** a Undermine não tem dados de 28/06 a 01/07/2024, e o seu preço é o menor preço do dia, mais ruidoso que o valor de mercado.
