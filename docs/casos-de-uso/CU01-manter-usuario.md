# CU01 – Manter Usuário

> Fonte: documento do TC *TCII-N2-IND-Itzac Albertin-Guiliano Rangel Alves* (Google Drive), exportado em 06/10/2026, já com as atualizações pós-implementação. O documento do TC é a fonte da verdade: se houver divergência, atualize este arquivo a partir dele.

**Situação no código (06/10/2026):** Implementado (C1 a C3), commits `98670a6` e `64245e7`. Testes em `backend/tests/integration/test_cu01_manter_usuario.py`.

## Descrição

Este caso de uso tem como principal função permitir que o usuário crie, altere e exclua a sua conta na plataforma, mantendo os dados de acesso (e-mail, senha e região) necessários para a autenticação e para o uso das funcionalidades restritas, como a lista de itens favoritos e os alertas de preço.

- **Requisitos associados:** RF01 – Autenticação de Usuário
- **Cenários:**
  - Cenário 01 – Cadastrar usuário
  - Cenário 02 – Alterar dados do usuário
  - Cenário 03 – Excluir conta do usuário

## Regras de negócio dos requisitos associados

(Conforme o campo "Regras de Negócio" dos quadros dos RFs; texto completo em `docs/regras-de-negocio.md`.)

- **RN11 – Validação de Domínio Geográfico:** O sistema só aceita o cadastro de contas e a ingestão de dados de mercado das regiões Ocidentais: US e EU.
- **RN18 – Unicidade de Conta por E-mail:** Cada endereço de e-mail só pode estar vinculado a uma única conta na plataforma. Por atuar como identificador de acesso do usuário e como destino das notificações de alertas, o e-mail não pode ser alterado após o cadastro.
- **RN19 – Confirmação de Identidade para Operações Sensíveis:** Operações que alteram credenciais ou removem dados da conta, como a troca de senha e a exclusão da conta, só podem ser executadas mediante a confirmação da senha atual do usuário, mesmo que ele já esteja autenticado.
- **RN20 – Exclusão Integral dos Dados do Usuário:** Ao excluir a conta, o sistema deve remover de forma definitiva e atômica todos os dados pessoais vinculados ao usuário, sem manter registros residuais, em conformidade com o direito à eliminação dos dados pessoais previsto no art. 18, inciso VI, da Lei Geral de Proteção de Dados (BRASIL, 2018). Caso qualquer etapa da remoção falhe, todas as remoções devem ser desfeitas.
- **RN21 – Limite de Tentativas de Autenticação:** Após cinco tentativas consecutivas de login malsucedidas para um mesmo e-mail, o acesso à conta deve ser bloqueado temporariamente por quinze minutos, mitigando ataques de força bruta. O contador de tentativas é reiniciado após um login bem-sucedido ou ao término do bloqueio. O bloqueio também se aplica a e-mails não cadastrados, para não revelar se o e-mail possui conta.
- **RN22 – Validade do Link de Recuperação de Senha:** O link de redefinição de senha é de uso único e expira em dez minutos após a sua emissão. A emissão de um novo link invalida automaticamente os links anteriores ainda não utilizados.

## CU01 - C1 – Manter Usuário - Cenário Cadastrar Usuário

- **Objetivo:** Registrar uma nova conta de usuário na plataforma a partir do e-mail, da senha e da região de jogo informados.
- **Pré-condição:** O usuário não deve estar autenticado na plataforma.
- **Pós-condição:** A conta do usuário é registrada no banco de dados e o usuário é direcionado à tela de login.
- **Atores:** Usuário
- **Ativação:** O usuário seleciona a opção "Criar conta" na interface.

### Fluxo principal

1. O usuário seleciona a opção "Criar conta".
2. O sistema exibe o formulário de cadastro contendo os campos e-mail, senha, confirmação de senha e região (US/EU).
3. O usuário preenche os campos e confirma o cadastro.
4. O sistema valida o preenchimento dos campos obrigatórios, o formato do e-mail e a correspondência entre a senha e a confirmação de senha.
5. O sistema verifica se já existe conta cadastrada com o e-mail informado.
6. O sistema criptografa a senha informada por meio de algoritmo de hash.
7. O sistema registra a conta do usuário no banco de dados.
8. O sistema exibe a mensagem "Conta criada com sucesso" e direciona o usuário à tela de login.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Dados inválidos

- **1.1** No passo 4, o sistema identifica campo obrigatório não preenchido, e-mail em formato inválido ou divergência entre a senha e a confirmação de senha.
- **1.2** O sistema destaca os campos inválidos e exibe a mensagem: "Verifique os campos destacados".
- **1.3** Retorna ao passo 3 do fluxo principal.

#### Fluxo Alternativo 2 - E-mail já cadastrado

- **2.1** No passo 5, o sistema identifica uma conta já cadastrada com o e-mail informado.
- **2.2** O sistema exibe a mensagem: "Já existe uma conta cadastrada com este e-mail".
- **2.3** Retorna ao passo 3 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** No passo 7, o sistema não consegue registrar a conta devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível concluir o cadastro no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU01 - C2 – Manter Usuário - Cenário Alterar Dados do Usuário

- **Objetivo:** Permitir que o usuário atualize a sua região de jogo e a sua senha de acesso.
- **Pré-condição:** O usuário deve estar autenticado na plataforma.
- **Pós-condição:** Os dados do usuário são atualizados no banco de dados.
- **Atores:** Usuário
- **Ativação:** O usuário acessa a opção "Meu perfil" na interface.

### Fluxo principal

1. O usuário acessa a opção "Meu perfil".
2. O sistema recupera e exibe os dados cadastrados do usuário, mantendo o e-mail apenas para leitura.
3. O usuário altera a região e informa a senha atual, a nova senha e a confirmação da nova senha.
4. O usuário confirma a alteração.
5. O sistema valida os campos informados e a correspondência entre a nova senha e a sua confirmação.
6. O sistema confere a senha atual informada com o hash armazenado no banco de dados.
7. O sistema criptografa a nova senha por meio de algoritmo de hash.
8. O sistema atualiza os dados do usuário no banco de dados.
9. O sistema exibe a mensagem "Dados atualizados com sucesso".

### Fluxos alternativos

#### Fluxo Alternativo 1 - Alteração somente da região

- **1.1** No passo 3, o usuário altera apenas a região, sem preencher os campos de senha.
- **1.2** O sistema dispensa a conferência da senha atual e a criptografia de nova senha.
- **1.3** Prossegue para o passo 8 do fluxo principal.

#### Fluxo Alternativo 2 - Confirmação de senha divergente

- **2.1** No passo 5, o sistema identifica que a nova senha e a sua confirmação não coincidem.
- **2.2** O sistema exibe a mensagem: "A nova senha e a confirmação não coincidem".
- **2.3** Retorna ao passo 3 do fluxo principal.

#### Fluxo Alternativo 3 - Senha atual incorreta

- **3.1** No passo 6, o sistema identifica que a senha atual informada não corresponde à senha cadastrada.
- **3.2** O sistema exibe a mensagem: "Senha atual incorreta".
- **3.3** Retorna ao passo 3 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** No passo 8, o sistema não consegue atualizar os dados devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema mantém os dados anteriores do usuário e exibe a mensagem: "Não foi possível atualizar os dados no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU01 - C3 – Manter Usuário - Cenário Excluir Conta do Usuário

- **Objetivo:** Remover definitivamente a conta do usuário e os dados vinculados a ela.
- **Pré-condição:** O usuário deve estar autenticado na plataforma, na página de perfil.
- **Pós-condição:** A conta, os itens favoritos e os alertas do usuário são removidos do banco de dados e a sessão é encerrada.
- **Atores:** Usuário
- **Ativação:** O usuário seleciona a opção "Excluir conta" na tela "Meu perfil".

### Fluxo principal

1. O usuário seleciona a opção "Excluir conta".
2. O sistema exibe um aviso informando que a exclusão é definitiva e que removerá os itens favoritos e os alertas cadastrados, solicitando a senha para confirmação.
3. O usuário informa a senha e confirma a exclusão.
4. O sistema confere a senha informada com o hash armazenado no banco de dados.
5. O sistema remove os itens favoritos e os alertas vinculados ao usuário.
6. O sistema remove a conta do usuário do banco de dados.
7. O sistema encerra a sessão do usuário e o direciona à página inicial.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Exclusão cancelada

- **1.1** No passo 3, o usuário cancela a exclusão.
- **1.2** O sistema fecha o aviso e mantém a conta inalterada.
- **1.3** Fim.

#### Fluxo Alternativo 2 - Senha incorreta

- **2.1** No passo 4, o sistema identifica que a senha informada não corresponde à senha cadastrada.
- **2.2** O sistema exibe a mensagem: "Senha incorreta. A conta não foi excluída".
- **2.3** Retorna ao passo 3 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 5 ou 6, o sistema não consegue concluir a remoção devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema desfaz as remoções já realizadas, mantendo a conta e os dados vinculados inalterados.
- **1.3** O sistema exibe a mensagem: "Não foi possível excluir a conta no momento. Tente novamente mais tarde".
- **1.4** Fim.

## Observações para a implementação

Decisões já implementadas (com a variável de ambiente que as controla) e o que continua pendente. Detalhes em `docs/decisoes-e-pendencias.md`. Onde houver conflito com o texto acima, vale o que está aqui e o documento do TC deve ser corrigido.

- Papel do Admin: coluna `role` com os valores `usuario` e `admin`. A promoção é feita direto no banco, sem tela de gestão de papéis (seção 6.3 do TC).
- Senha: mínimo de 8 caracteres (`PASSWORD_MIN_LENGTH`) e máximo de 255; hash bcrypt com custo 12 (`BCRYPT_ROUNDS`). O documento não define regras de complexidade.
- RN20: a exclusão é atômica, com chaves estrangeiras `ON DELETE CASCADE`. As tabelas de favoritos (CU06) e alertas (CU07) ainda não existem; quando forem criadas, devem seguir o mesmo padrão.
- Divergência com o MR: a tabela `usuario` tem `regiao`, não tem `nome_usuario` e o e-mail tem 150 caracteres. O MR do TC ainda precisa ser atualizado.
- **Pendente (teste):** o CU01-C3 FA1 (exclusão cancelada) não tem teste próprio. Criar `test_cu01_c3_fa1_exclusao_cancelada`; o botão "Cancelar" está em `frontend/app/perfil/page.tsx`.
