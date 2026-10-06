# CU11 – Treinar Modelo

> **PROVISÓRIO.** Este caso de uso ainda **não está no documento do TC**. O autor decidiu implementá-lo e testá-lo antes de escrevê-lo. O conteúdo vem do arquivo `docs/Alterações do TC - modelo global (para colar) v2.docx`. Enquanto o TC não for atualizado, as regras de negócio deste arquivo prevalecem sobre as versões antigas em `docs/regras-de-negocio.md`. Qualquer divergência encontrada na implementação deve ser avisada ao autor, para que o texto do TC saia corrigido.

**Situação no código (06/10/2026):** Não implementado. A implementação de referência do pipeline de dados, da normalização, da separação dos períodos, do treino e da avaliação está em `estudos/lstm/`, com testes (`README.md` de lá). Antes de implementar, conferir os pré-requisitos de `estudos/lstm/pedido-preparacao-treino.md`.

## Descrição

Este caso de uso tem como principal função preparar o histórico consolidado dos itens selecionados, treinar o modelo preditivo global de preços e avaliá-lo individualmente para cada item, liberando a projeção somente para os itens em que o modelo atinge o limiar mínimo de acurácia, além de mantê-lo atualizado por meio de retreinamentos periódicos e de registrar diariamente as predições e o seu desempenho para fins de auditoria.

- **Requisitos associados:** RF08 – Retreinamento do Modelo; RF12 – Treinamento Inicial
- **Cenários:**
  - Cenário 01 – Executar treinamento inicial
  - Cenário 02 – Retreinar o modelo periodicamente
  - Cenário 03 – Consolidar predições diárias

## Regras de negócio

Regras **alteradas** em relação a `docs/regras-de-negocio.md`:

- **RN02 – Filtro de Liquidez para Modelagem Preditiva:** Os algoritmos de *Machine Learning* só devem processar e gerar projeções preditivas para itens que possuam quantidade média ofertada superior a 50 unidades nos últimos 7 dias. A quantidade ofertada é utilizada como indicador de liquidez, pois a API oficial não informa as vendas realizadas. Itens com baixa liquidez não possuem dados estatísticos suficientes para inferências estocásticas confiáveis, devendo exibir apenas o histórico gráfico (sem a linha de tendência).
- **RN03 – Mitigação de *Outliers* e *Market Spoofing*:** Para evitar que o treinamento do modelo preditivo seja corrompido por manipulações de mercado (jogadores que postam itens a preços absurdamente altos para inflacionar médias), o *pipeline* de dados (Python) deve descartar registros cujo preço diário seja 300% superior ou 90% inferior à Média Móvel Exponencial (EMA) de 14 dias do referido item. A média móvel é calculada somente com registros anteriores ao dia avaliado.
- **RN07 – Relevância de Equipamento (iLvl):** O modelo de *Machine Learning* deve somente processar equipamentos (armas e armaduras) se forem relevantes para o *endgame*, ou seja, se o seu nível de item (iLvl) for igual ou superior ao mínimo definido para a temporada vigente. Equipamentos obsoletos têm a predição bloqueada para economizar processamento.
- **RN10 – Limiar de Precisão Preditiva:** O sistema deve omitir projeções de ML que não atinjam um padrão mínimo de acurácia matemática. A projeção de um item só é exibida se o erro percentual absoluto médio (MAPE) do modelo, medido no período de teste do item (RN25), for igual ou inferior a 15% e menor que o erro do modelo ingênuo, que repete o último preço observado.
- **RN13 – Snapshot de Estado (Auditoria ML):** O sistema deve consolidar diariamente suas predições contra a realidade para fins de auditoria acadêmica, registrando, para cada item com projeção liberada, a data, a versão do modelo, o valor predito, o valor real observado e o erro. Se o erro médio dos últimos 7 dias ultrapassar o limiar da RN10, a projeção do item é bloqueada até o próximo retreinamento.
- **RN16 – Harmonização de Dados de Terceiros:** Dados históricos retroativos obtidos via extração externa (Undermine Exchange, *web scraping*) devem obrigatoriamente ser convertidos, tipados e higienizados para o exato padrão relacional do SGBD do sistema e da padronização de moeda, garantindo a integridade do *dataset* antes do treinamento inicial. Cada registro identifica a sua origem e a sua granularidade (diária ou horária). As séries de origens diferentes não são misturadas no treinamento: o modelo utiliza a série diária da Undermine Exchange, única com histórico contínuo, e a série horária do ciclo da Blizzard (RN06) não é incorporada a ela.

Regras **novas**:

- **RN24 – Normalização das Variáveis do Modelo:** Para o treinamento e a predição, os preços e as quantidades recebem transformação logarítmica e são padronizados pela média e pelo desvio-padrão dos últimos 90 dias do próprio item; as variações de preço e os indicadores derivados são divididos por constantes globais. Em todos os casos, os valores resultantes são limitados ao intervalo entre −1 e 1. O dia da semana é representado por seno e cosseno, as contagens de dias são limitadas a 60 e divididas por 60 (exceto a distância até o próximo patch, limitada à antecedência da RN25), e as categorias do item são representadas por vetores aprendidos (*embeddings*). Dias sem registro são preenchidos com o último valor observado por até 3 dias e marcados como não observados. A saída do modelo é padronizada pela média e pelo desvio-padrão de cada dia do horizonte, calculados no período de treinamento.
- **RN25 – Integridade Temporal do Treinamento:** Toda variável de entrada do modelo deve ser calculada apenas com informações disponíveis no dia da previsão. Como a data de anúncio dos eventos não é registrada, um patch só é considerado conhecido a partir de 14 dias antes da sua data. O histórico é dividido em ordem cronológica, com as mesmas datas de corte para todos os itens, em 70% para treinamento, 20% para validação e 10% para teste (HYNDMAN; ATHANASOPOULOS, 2018). A validação é usada para interromper o treinamento e escolher a configuração do modelo; o teste é usado uma única vez, para medir o erro final e decidir a liberação da projeção de cada item (RN10). Amostras cujos dias previstos atravessem uma data de corte são descartadas. As constantes de normalização (RN24) são calculadas exclusivamente com os dados do período de treinamento e armazenadas junto com a versão do modelo.
- **RN26 – Política de Retreinamento:** O modelo preditivo é retreinado semanalmente, após o reinício semanal do jogo, e só substitui o modelo vigente se apresentar erro menor que o dele no mesmo período de teste (RN25); caso contrário, o modelo vigente é mantido.

Regras **sem alteração**, usadas pelo caso de uso:

- **RN15 – Volume Mínimo para Treinamento Inicial:** O modelo preditivo de um item só pode ser processado e ativado (RF12) se a base de dados contiver um período histórico contínuo predeterminado de mínimo 6 meses de registros consolidados para o respectivo ativo. Itens sem histórico mínimo terão a predição bloqueada. O período mínimo corresponde a 180 dias contínuos, e lacunas de até 3 dias sem registros não interrompem a continuidade do período.
- **RN17 – Marcação Estocástica de Eventos:** Datas de grandes atualizações sistêmicas do jogo (patches/expansões) mapeadas no banco histórico devem ser injetadas como variáveis categóricas para o algoritmo. Isso impede que o modelo interprete quedas abruptas de preço causadas por obsolescência de itens como flutuações naturais de mercado. Além de patches e expansões, são registrados como eventos as temporadas, os eventos sazonais e os eventos recorrentes do jogo.

Mapeamento de rastreabilidade (seção 3.6.2):

- **RF04 (Projeção Preditiva com ML):** Estritamente governado por RN02, RN03, RN07, RN10, RN17.
- **RF08 (Retreinamento do Modelo):** Validado por RN02, RN03, RN07, RN10, RN13, RN24, RN25, RN26.
- **RF12 (Treinamento Inicial do Modelo):** Estritamente governado por RN02, RN03, RN07, RN10, RN15, RN16, RN17, RN24, RN25.

## Requisito Funcional 08 – [RF 08]: Retreinamento do Modelo

O sistema deve possuir um trabalho automatizado para retreinar periodicamente os algoritmos preditivos com os dados mais recentes ingeridos.

**Intenção do sistema:** "Atualizar os pesos matemáticos do modelo de *Machine Learning* baseando-se nas últimas flutuações do mercado, para evitar que a linha de tendência fique defasada."

Antes do retreinamento, o sistema deve garantir que o conjunto de dados esteja higienizado: descartando valores absurdos (*outliers* gerados por *spoofing*/*market manipulation*), ignorando itens sem quantidade ofertada suficiente e focando em equipamentos que ainda tenham relevância no jogo (iLvl). O retreinamento atualiza o modelo global com os dados mais recentes e só substitui o modelo vigente quando o novo apresenta desempenho superior (RN26).

- **Regras de negócio:** RN02; RN03; RN07; RN10; RN13; RN24; RN25; RN26

| Variável | Tipo de dado | Tamanho | Obrigatório | Domínio |
| --- | --- | --- | --- | --- |
| ID do Item | Inteiro | - | Sim | Numérico |
| Versão do Modelo | Inteiro | - | Sim | Numérico sequencial |
| Data/Hora do Treinamento | Data/Hora | - | Sim | Timestamp |
| Erro do Modelo por Item (MAPE) | Decimal | - | Sim | Percentual |
| Situação da Projeção do Item | Texto | 9 | Sim | 'Liberada' ou 'Bloqueada' |

## Requisito Funcional 12 – [RF 12]: Treinamento Inicial

O sistema deve possuir uma rotina dedicada para processar o histórico consolidado de dados (proveniente do RF11) e realizar o treinamento primário dos algoritmos de *Machine Learning*, estabelecendo um modelo preditivo global, treinado com o histórico de todos os itens selecionados e avaliado individualmente para cada item, antes de sua disponibilização no ambiente de produção.

**Intenção do sistema:** "Preciso analisar todo o histórico de preços já higienizado para gerar o primeiro modelo matemático preditivo, garantindo que o sistema já nasça com inteligência ao entrar em produção."

O treinamento utiliza a base harmonizada e aplica a marcação estocástica de eventos para refinar a precisão. As variáveis de entrada do modelo e a sua normalização estão descritas na seção 5.12.2.

- **Regras de negócio:** RN02; RN03; RN07; RN10; RN15; RN16; RN17; RN24; RN25

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
| 6 | Variação do índice da subclasse | Mercado (passado) | −1 a 1 | Média dos log-retornos dos demais itens da subclasse no dia, ponderada pela quantidade ofertada, dividida por uma constante global e limitada ao intervalo. |
| 7 | Distância ao preço de venda ao vendedor | Mercado (passado) | −1 a 1 | ln(preço ÷ preço pago pelo vendedor do jogo), dividido por uma constante global e limitado; vale 0 para itens sem esse preço. |
| 8 | Dado observado | Mercado (passado) | 0 ou 1 | Indica se o registro do dia foi observado ou preenchido com o último valor (RN24). |
| 9 | Dia da semana | Calendário (futuro conhecido) | −1 a 1 | Seno e cosseno de 2π × dia ÷ 7. |
| 10 | Dias desde o último patch | Evento (futuro conhecido) | 0 a 1 | Limitado a 60 e dividido por 60. |
| 11 | Dias até o próximo patch | Evento (futuro conhecido) | 0 a 1 | Dias até o patch divididos por 14 quando ele está a até 14 dias; vale 1 quando o patch ainda não é considerado conhecido (RN25). |
| 12 | Expansão ou pré-patch nos próximos 14 dias | Evento (futuro conhecido) | 0 ou 1 | Indicador. |
| 13 | Temporada ativa e dias desde o seu início | Evento (futuro conhecido) | 0 a 1 | Indicador de temporada ativa e contagem de dias limitada a 60 e dividida por 60. |
| 14 | Evento sazonal ativo | Evento (futuro conhecido) | 0 ou 1 | Indicador. |
| 15 | Classe e subclasse do item | Item (fixa) | — | Vetor aprendido pelo modelo (*embedding*). |
| 16 | Qualidade e nível de item | Item (fixa) | 0 a 1 | Qualidade dividida por 5; nível de item normalizado pelo mínimo e pelo máximo do treinamento. |
| 17 | Possui preço de venda ao vendedor | Item (fixa) | 0 ou 1 | Indicador. |
| 18 | Item do tipo commodity | Item (fixa) | 0 ou 1 | Indicador. |

Fundamentação (seção 3.1.2.3, a entrar no TC): modelo global, treinado com as séries de todos os itens (MONTERO-MANSO; HYNDMAN, 2021; SALINAS et al., 2020), com camada LSTM (HOCHREITER; SCHMIDHUBER, 1997); divisão dos períodos conforme HYNDMAN; ATHANASOPOULOS (2018).

## CU11 - C1 – Treinar Modelo - Cenário Executar Treinamento Inicial

- **Objetivo:** Gerar o primeiro modelo preditivo global a partir do histórico consolidado dos itens selecionados, liberando a projeção somente para os itens em que o modelo atinge o limiar mínimo de acurácia.
- **Pré-condição:** O Admin deve possuir acesso às funções administrativas da plataforma e a cobertura histórica dos itens deve ter sido validada (CU10 - Cenário 03).
- **Pós-condição:** O modelo global é registrado com as suas métricas, e cada item processado tem a sua projeção classificada como "Liberada" ou "Bloqueada".
- **Atores:** Admin
- **Ativação:** O Admin solicita a execução do treinamento inicial.

### Fluxo principal

1. O Admin solicita a execução do treinamento inicial, informando a região.
2. O sistema seleciona os itens classificados como "Apto ao treinamento" (RN15) que atendem ao filtro de liquidez (RN02) e ao critério de relevância de equipamentos (RN07).
3. O sistema recupera a série histórica diária harmonizada de cada item selecionado (RN16).
4. O sistema descarta os registros cujo preço seja 300% superior ou 90% inferior à média móvel exponencial de 14 dias do item (RN03).
5. O sistema calcula as variáveis de entrada de cada item, incluindo as variáveis de calendário e as variáveis categóricas dos eventos do jogo registrados no período (RN17).
6. O sistema normaliza as variáveis de entrada (RN24).
7. O sistema separa o histórico em períodos de treinamento, validação e teste, com as mesmas datas de corte para todos os itens e preservando a ordem cronológica dos registros (RN25).
8. O sistema treina o modelo preditivo global com os dados do período de treinamento de todos os itens selecionados, interrompendo o treinamento quando o erro no período de validação deixa de diminuir.
9. O sistema avalia o modelo no período de teste de cada item, calculando o erro das predições do item e o erro do modelo ingênuo.
10. O sistema verifica, para cada item, se o modelo atinge o limiar mínimo de acurácia (RN10).
11. O sistema registra a versão do modelo, com a data e a hora do treinamento e as métricas obtidas, e libera a projeção dos itens aprovados (CU05).
12. O sistema apresenta ao Admin o resumo do treinamento, com a quantidade de itens com projeção liberada, de itens com projeção bloqueada e de itens ignorados.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Nenhum item apto ao treinamento

- **1.1** No passo 2, o sistema não encontra itens que atendam aos critérios de seleção.
- **1.2** O sistema exibe a mensagem: "Nenhum item apto ao treinamento. Verifique a validação da cobertura histórica".
- **1.3** Fim.

#### Fluxo Alternativo 2 - Treinamento em andamento

- **2.1** No passo 1, o sistema identifica que já existe um treinamento em andamento.
- **2.2** O sistema exibe a mensagem: "Já existe um treinamento em andamento".
- **2.3** Fim.

#### Fluxo Alternativo 3 - Série insuficiente após a higienização

- **3.1** No passo 4, o sistema identifica que os registros restantes do item não são suficientes para compor os períodos de treinamento, validação e teste.
- **3.2** O sistema classifica o item como "Ignorado", registrando o motivo, e o exclui do treinamento.
- **3.3** Retorna ao passo 3 do fluxo principal para os demais itens.

#### Fluxo Alternativo 4 - Projeção do item reprovada na avaliação

- **4.1** No passo 10, o sistema identifica que o modelo não atinge o limiar mínimo de acurácia (RN10) para o item.
- **4.2** O sistema registra as métricas do item e mantém a sua projeção bloqueada.
- **4.3** Retorna ao passo 10 do fluxo principal para os demais itens.

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
- **Atores:** Sistema
- **Ativação:** O agendador de tarefas dispara a rotina de retreinamento após o reinício semanal do jogo (RN26).

### Fluxo principal

1. O agendador de tarefas dispara a rotina de retreinamento.
2. O sistema seleciona os itens que atendem ao filtro de liquidez (RN02), ao critério de relevância de equipamentos (RN07) e à cobertura histórica mínima (RN15).
3. O sistema recupera a série histórica de cada item, incluindo os dados ingeridos desde o último treinamento.
4. O sistema higieniza, calcula, normaliza e separa as variáveis conforme os passos 4 a 7 do Cenário 01.
5. O sistema treina um novo modelo global.
6. O sistema avalia o novo modelo e o modelo vigente no mesmo período de teste (RN25).
7. O sistema verifica se o novo modelo apresenta erro menor que o do modelo vigente (RN26).
8. O sistema substitui o modelo vigente pelo novo, registrando a versão, a data e a hora do treinamento e as métricas obtidas.
9. O sistema atualiza a situação da projeção de cada item, liberando os itens que atingem o limiar mínimo de acurácia (RN10) e bloqueando os demais.
10. O sistema registra em log o resumo do retreinamento.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Item deixou de atender aos critérios

- **1.1** No passo 2, o sistema identifica que um item com projeção liberada não atende mais aos critérios de seleção.
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
- **Atores:** Sistema
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

- **3.1** No passo 5, o sistema identifica que o erro médio do item nos últimos 7 dias ultrapassa o limiar mínimo de acurácia (RN13).
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

Este caso de uso ainda não tem decisões implementadas. Abaixo estão as sugestões de implementação e o que precisa ser confirmado com o autor (CLAUDE.md, regra 3). Onde houver conflito com o texto acima, vale o que está aqui, e o autor deve ser avisado para corrigir o texto do TC.

### Arquitetura

- **Código do pipeline.** Porte o código de `estudos/lstm/` para o backend, por exemplo em `backend/src/ml/`, e leve junto os testes do estudo. Correspondência:

  | Arquivo do estudo | Parte do pipeline |
  | --- | --- |
  | `preparar_dados.py` | variáveis, normalização e janelas |
  | `dataset.py` | tensores |
  | `avaliar.py` | desnormalização e métricas |
  | `treinar.py` | rede e treino |

  Se o estudo e as regras acima divergirem, vale o texto das regras, e o autor deve ser avisado.
- **Decisão pendente: onde o TensorFlow roda.** O worker usa a imagem `python:3.11-alpine`, e o TensorFlow não tem pacote para Alpine.
  - Sugestão: criar um serviço novo, `modelo`, no `docker-compose.yml`, com imagem `python:3.11-slim` e `tensorflow-cpu`. Ele acessa o mesmo banco e um volume `modelos/`, tem o seu próprio agendador e roda o treino (C1 e C2) e a consolidação diária (C3).
  - Alternativa: trocar a imagem do worker. Fica mais pesado, e o treino disputa processador com a ingestão.
- **Artefatos.** Cada versão do modelo fica em `modelos/v{versão}/`, com três arquivos: `modelo.keras`, `normalizacao.json` (constantes e datas de corte, RN25) e `treino.json`. Para prever com uma versão, use sempre as constantes dela.
- **Tabelas novas, via Alembic** (sugestão, a confirmar no plano):

  | Tabela | Conteúdo |
  | --- | --- |
  | `modelo_preditivo` | versão, região, data e hora do treinamento, datas de corte, MAPE médio do modelo e do ingênuo no teste, caminho dos artefatos, se é a versão vigente |
  | `execucao_treinamento` | tipo (inicial ou retreinamento), origem (Admin ou agendado), status (`EXECUTANDO`, `SUCESSO`, `FALHA`), início, fim, resumo (liberados, bloqueados, ignorados), erro |
  | `projecao_item` | item, série/região, versão, MAPE, MAPE do ingênuo, situação (`LIBERADA`, `BLOQUEADA`, `IGNORADO`), motivo, data da atualização |
  | `predicao_diaria` (RN13) | data da previsão, item, série, versão, h (1 a 7), data prevista, preço previsto em Cobre, preço real, erro |

  - `execucao_treinamento` atende o C1-FA2. Como no CU10-C1-FA4, uma execução "em andamento" há mais de N horas deixa de bloquear.
  - Em `predicao_diaria`, preço real e erro nulos correspondem a "N/D". Chave única: (item, série, versão, data da previsão, h).
- **Mensagens ao usuário:** exatamente as dos cenários.

### C1 – Treinamento inicial

- **Disparo pelo Admin,** no mesmo padrão de `/admin/history-import`:
  - `POST /admin/model-training`, que responde 202 e roda de forma assíncrona;
  - `GET /admin/model-training/{id}` e `GET /admin/model-training`, para o resumo;
  - tela em `frontend/src/app/admin/treinamento`.
- **Passo 2 (seleção dos itens):**
  - RN15: pela tabela `aptidao_treinamento`;
  - RN02: pela quantidade média dos últimos 7 dias;
  - RN07: usa a classe e o nível do item em `items.metadata_info` (`item_class_id`, `level`), gravados pela Parte 1 de `estudos/lstm/pedido-preparacao-treino.md`.

  **Decisão pendente:** o nível mínimo da temporada vigente. Deixe configurável (`MODELO_ILVL_MINIMO`), desligado por padrão, e avise no resumo.
- **Passo 3 (RN16):** só entram registros com `origem = 'UNDERMINE'`, `granularidade = 'DIARIA'` e sem `anomalia`. O preço da Undermine é o menor preço do dia. A série horária da Blizzard (1º quartil, RN06) não entra.
- **Passo 4 (RN03):** a EMA de 14 dias usa só os dias anteriores ao avaliado. O registro é descartado se o preço for maior que 4 × EMA ou menor que 0,1 × EMA.
- **Passos 5 a 7:** como em `estudos/lstm/preparar_dados.py`:
  - variáveis 1 a 18, sempre calculadas item a item;
  - preenchimento de até 3 dias;
  - divisão 70/20/10 por data de calendário;
  - constantes calculadas só com o treino;
  - descarte das amostras cujos dias previstos atravessam uma data de corte.
- **Passo 8 (rede e treino):**
  - arquitetura: LSTM(64) → Dropout(0,2) → junção com os atributos fixos e os embeddings de classe (4) e subclasse (8) → Dense(32, ReLU) → Dense(7);
  - otimizador Adam, taxa 0,001;
  - lotes de 512 montados sob demanda, com as amostras sorteadas a cada época;
  - EarlyStopping na validação, com paciência 10 e volta para a melhor época.

  **Decisão pendente:** a função de perda. A sugestão é Huber; o estudo do orientador usa MSE.
- **Passos 9 e 10 (RN10):** o erro é calculado por item, no período de teste, só sobre os dias observados (dias preenchidos e descartados pela RN03 não contam). A projeção é liberada se o MAPE for menor ou igual ao limiar e menor que o MAPE do ingênuo.
- **FA3:** o item sem amostras suficientes em algum dos três períodos vira `IGNORADO`, com o motivo. Exemplo: item com menos de cerca de 60 dias de histórico antes do corte da validação.
- **FE1:** cobre treino que produz NaN (TerminateOnNaN) e falta de memória.

### C2 – Retreinamento

- **Agendamento:** depois do reinício semanal, que nos EUA é na terça-feira. Configurável em `MODELO_RETREINO_CRON`; sugestão: terça, 18:00 UTC.
- **Novos períodos:** a divisão 70/20/10 é recalculada até a data mais recente.
- **Comparação (RN26):** o modelo vigente é avaliado no novo período de teste com as suas próprias constantes; o modelo novo, com as dele.
- **Resultado:**
  - modelo novo melhor: vira o vigente, e a situação de cada item é recalculada (RN10);
  - modelo novo pior: é descartado, mas os artefatos e as métricas ficam registrados.

### C3 – Consolidação diária

- **Decisão pendente:** o passo 2 depende de uma importação incremental **diária** da Undermine (CU10-C1). Hoje o backfill só roda pela regra de 48 horas. Sugestão: agendar, antes da consolidação, a importação incremental dos itens com projeção liberada, respeitando a RN23.
- **Passo 7:** a previsão dos próximos 7 dias de cada item liberado é gravada em `predicao_diaria`, em Cobre (RN01): preço previsto = preço de hoje × exp(log-retorno previsto).
- **FA3 (RN13):** se o erro médio do item nos últimos 7 dias passar do limiar, o item fica `BLOQUEADA` até o próximo retreinamento.
- **FA4:** se mais de 20% dos itens liberados forem bloqueados no dia, o C2 é antecipado.
- **CU05 (consulta da previsão) não está especificado.** O CU11 só grava as previsões e a situação dos itens; não há tela de projeção.

### Valores configuráveis

Todos são sugestões, exceto a divisão 70/20/10, que já foi decidida. O autor precisa confirmar os demais.

| Variável de ambiente | Valor | Regra |
| --- | --- | --- |
| `MODELO_JANELA_DIAS` | 30 | RF12 |
| `MODELO_HORIZONTE_DIAS` | 7 | RF04 |
| `MODELO_ZSCORE_DIAS` | 90 | RN24 |
| `MODELO_PROPORCAO_TREINO` / `MODELO_PROPORCAO_VALIDACAO` | 0,70 / 0,20 (decidido) | RN25 |
| `MODELO_ANTECEDENCIA_PATCH_DIAS` | 14 | RN25 |
| `MODELO_LIMIAR_MAPE` | 0,15 | RN10 |
| `MODELO_DEGRADACAO_DIAS` | 7 | RN13 |
| `MODELO_DEGRADACAO_GERAL` | 0,20 | C3-FA4 |
| `MODELO_ILVL_MINIMO` | vazio (desligado) | RN07 |
| `MODELO_EPOCAS_MAX` / `MODELO_PACIENCIA` / `MODELO_LOTE` | 100 / 10 / 512 | treino |
| `MODELO_AMOSTRAS_POR_EPOCA` | 400000 | treino |
| `MODELO_PERDA` | huber | treino |

### Testes (um por fluxo)

Use dados sintéticos (`estudos/lstm/gerar_sinteticos.py`) e um modelo mínimo nos testes, por exemplo LSTM de 4 unidades e 1 época, para a suíte continuar rápida.

- C1:
  - `test_cu11_c1_fluxo_principal_treina_e_libera_itens`
  - `test_cu11_c1_fa1_nenhum_item_apto`
  - `test_cu11_c1_fa2_treinamento_em_andamento`
  - `test_cu11_c1_fa3_serie_insuficiente_item_ignorado`
  - `test_cu11_c1_fa4_projecao_reprovada_rn10`
  - `test_cu11_c1_fe1_falha_no_treinamento`
  - `test_cu11_c1_fe2_falha_no_banco`
- C2:
  - `test_cu11_c2_fluxo_principal_substitui_modelo_rn26`
  - `test_cu11_c2_fa1_item_deixou_de_atender`
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
  - `test_rn25_sem_vazamento_do_futuro`
  - `test_rn25_janelas_respeitam_os_cortes`
  - `test_rn25_dias_ate_patch_respeita_antecedencia`
  - `test_rn03_descarta_pico_com_ema_anterior`

### Limitações conhecidas

- Itens novos só recebem previsão depois de cerca de 60 dias de histórico: 30 para a padronização e 30 para a janela.
- A RN03 pode descartar movimentos reais no lançamento de expansões. O pedido de preparação mede isso.
- A Undermine não tem dados de 28/06 a 01/07/2024.
- O preço da Undermine é o menor preço do dia, mais ruidoso que o valor de mercado.
