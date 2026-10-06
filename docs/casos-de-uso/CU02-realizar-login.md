# CU02 – Realizar Login

> Fonte: documento do TC *TCII-N2-IND-Itzac Albertin-Guiliano Rangel Alves* (Google Drive), exportado em 06/10/2026, já com as atualizações pós-implementação. O documento do TC é a fonte da verdade: se houver divergência, atualize este arquivo a partir dele.

**Situação no código (06/10/2026):** Implementado (C1 a C4), commits `98670a6` e `64245e7`. Testes em `backend/tests/integration/test_cu02_realizar_login.py`.

## Descrição

Este caso de uso tem como principal função permitir que o usuário se autentique na plataforma por meio de e-mail e senha, recupere o acesso à conta em caso de esquecimento da senha e encerre a sua sessão, controlando o acesso às funcionalidades restritas, como a lista de itens favoritos e os alertas de preço.

- **Requisitos associados:** RF01 – Autenticação de Usuário
- **Cenários:**
  - Cenário 01 – Autenticar usuário
  - Cenário 02 – Solicitar recuperação de senha
  - Cenário 03 – Redefinir senha
  - Cenário 04 – Encerrar sessão

## Regras de negócio dos requisitos associados

(Conforme o campo "Regras de Negócio" dos quadros dos RFs; texto completo em `docs/regras-de-negocio.md`.)

- **RN11 – Validação de Domínio Geográfico:** O sistema só aceita o cadastro de contas e a ingestão de dados de mercado das regiões Ocidentais: US e EU.
- **RN18 – Unicidade de Conta por E-mail:** Cada endereço de e-mail só pode estar vinculado a uma única conta na plataforma. Por atuar como identificador de acesso do usuário e como destino das notificações de alertas, o e-mail não pode ser alterado após o cadastro.
- **RN19 – Confirmação de Identidade para Operações Sensíveis:** Operações que alteram credenciais ou removem dados da conta, como a troca de senha e a exclusão da conta, só podem ser executadas mediante a confirmação da senha atual do usuário, mesmo que ele já esteja autenticado.
- **RN20 – Exclusão Integral dos Dados do Usuário:** Ao excluir a conta, o sistema deve remover de forma definitiva e atômica todos os dados pessoais vinculados ao usuário, sem manter registros residuais, em conformidade com o direito à eliminação dos dados pessoais previsto no art. 18, inciso VI, da Lei Geral de Proteção de Dados (BRASIL, 2018). Caso qualquer etapa da remoção falhe, todas as remoções devem ser desfeitas.
- **RN21 – Limite de Tentativas de Autenticação:** Após cinco tentativas consecutivas de login malsucedidas para um mesmo e-mail, o acesso à conta deve ser bloqueado temporariamente por quinze minutos, mitigando ataques de força bruta. O contador de tentativas é reiniciado após um login bem-sucedido ou ao término do bloqueio. O bloqueio também se aplica a e-mails não cadastrados, para não revelar se o e-mail possui conta.
- **RN22 – Validade do Link de Recuperação de Senha:** O link de redefinição de senha é de uso único e expira em dez minutos após a sua emissão. A emissão de um novo link invalida automaticamente os links anteriores ainda não utilizados.

## CU02 - C1 – Realizar Login - Cenário Autenticar Usuário

- **Objetivo:** Autenticar o usuário na plataforma a partir do e-mail e da senha cadastrados, liberando o acesso às funcionalidades restritas.
- **Pré-condição:** O usuário não deve estar autenticado na plataforma.
- **Pós-condição:** Uma sessão autenticada é iniciada e o usuário é direcionado à página inicial.
- **Atores:** Usuário
- **Ativação:** O usuário seleciona a opção "Entrar" na interface.

### Fluxo principal

1. O usuário seleciona a opção "Entrar".
2. O sistema exibe o formulário de login contendo os campos e-mail e senha.
3. O usuário informa o e-mail e a senha e confirma o acesso.
4. O sistema valida o preenchimento dos campos e o formato do e-mail.
5. O sistema localiza a conta vinculada ao e-mail informado.
6. O sistema confere a senha informada com o hash armazenado no banco de dados.
7. O sistema inicia a sessão autenticada do usuário.
8. O sistema direciona o usuário à página inicial com acesso às funcionalidades restritas.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Dados inválidos

- **1.1** No passo 4, o sistema identifica campo não preenchido ou e-mail em formato inválido.
- **1.2** O sistema destaca os campos inválidos e exibe a mensagem: "Verifique os campos destacados".
- **1.3** Retorna ao passo 3 do fluxo principal.

#### Fluxo Alternativo 2 - Credenciais inválidas

- **2.1** Nos passos 5 ou 6, o sistema não localiza conta vinculada ao e-mail informado ou identifica que a senha não corresponde à cadastrada.
- **2.2** O sistema registra a tentativa de acesso malsucedida.
- **2.3** O sistema exibe a mensagem genérica: "Credenciais inválidas", sem indicar qual dado está incorreto.
- **2.4** Retorna ao passo 3 do fluxo principal.

#### Fluxo Alternativo 3 - Conta temporariamente bloqueada

- **3.1** No passo 5, o sistema identifica que a conta está com bloqueio temporário ativo por excesso de tentativas malsucedidas.
- **3.2** O sistema exibe a mensagem: "Acesso temporariamente bloqueado por excesso de tentativas. Tente novamente mais tarde".
- **3.3** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** Nos passos 5 ou 6, o sistema não consegue consultar os dados de acesso devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema exibe a mensagem: "Não foi possível realizar o login no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU02 - C2 – Realizar Login - Cenário Solicitar Recuperação de Senha

- **Objetivo:** Enviar ao e-mail cadastrado do usuário um link para a redefinição da senha de acesso.
- **Pré-condição:** O usuário não deve estar autenticado na plataforma.
- **Pós-condição:** Um link de recuperação de uso único e com prazo de validade é enviado ao e-mail cadastrado.
- **Atores:** Usuário
- **Ativação:** O usuário seleciona a opção "Esqueci minha senha" na tela de login.

### Fluxo principal

1. O usuário seleciona a opção "Esqueci minha senha".
2. O sistema exibe o formulário solicitando o e-mail cadastrado.
3. O usuário informa o e-mail e confirma a solicitação.
4. O sistema valida o formato do e-mail informado.
5. O sistema localiza a conta vinculada ao e-mail informado.
6. O sistema gera um token de recuperação de uso único e com prazo de validade.
7. O sistema envia ao e-mail informado uma mensagem contendo o link de redefinição de senha.
8. O sistema exibe a mensagem: "Se o e-mail estiver cadastrado, você receberá as instruções de recuperação".

### Fluxos alternativos

#### Fluxo Alternativo 1 - E-mail em formato inválido

- **1.1** No passo 4, o sistema identifica que o e-mail informado não possui formato válido.
- **1.2** O sistema exibe a mensagem: "Informe um e-mail válido".
- **1.3** Retorna ao passo 3 do fluxo principal.

#### Fluxo Alternativo 2 - E-mail não cadastrado

- **2.1** No passo 5, o sistema não localiza conta vinculada ao e-mail informado.
- **2.2** O sistema não gera o token nem envia a mensagem de recuperação.
- **2.3** O sistema exibe a mesma mensagem do passo 8, sem revelar se o e-mail possui conta cadastrada.
- **2.4** Fim.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha no serviço de envio de e-mail

- **1.1** No passo 7, o sistema não consegue enviar a mensagem devido à indisponibilidade do serviço de e-mail.
- **1.2** O sistema invalida o token gerado.
- **1.3** O sistema exibe a mensagem: "Não foi possível processar a solicitação no momento. Tente novamente mais tarde".
- **1.4** Fim.

## CU02 - C3 – Realizar Login - Cenário Redefinir Senha

- **Objetivo:** Permitir que o usuário cadastre uma nova senha de acesso a partir do link de recuperação recebido por e-mail.
- **Pré-condição:** O usuário deve ter solicitado a recuperação de senha e recebido o link de redefinição.
- **Pós-condição:** A senha do usuário é atualizada, o token de recuperação é invalidado e o usuário é direcionado à tela de login.
- **Atores:** Usuário
- **Ativação:** O usuário acessa o link de redefinição de senha recebido por e-mail.

### Fluxo principal

1. O usuário acessa o link de redefinição recebido por e-mail.
2. O sistema verifica se o token do link é válido, se está dentro do prazo de validade e se ainda não foi utilizado.
3. O sistema exibe o formulário contendo os campos nova senha e confirmação da nova senha.
4. O usuário informa a nova senha e a confirmação e confirma a redefinição.
5. O sistema valida a correspondência entre a nova senha e a sua confirmação.
6. O sistema criptografa a nova senha por meio de algoritmo de hash.
7. O sistema atualiza a senha do usuário no banco de dados e invalida o token utilizado.
8. O sistema exibe a mensagem "Senha redefinida com sucesso" e direciona o usuário à tela de login.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Link inválido ou expirado

- **1.1** No passo 2, o sistema identifica que o token é inválido, está expirado ou já foi utilizado.
- **1.2** O sistema exibe a mensagem: "Link de recuperação inválido ou expirado. Solicite uma nova recuperação de senha".
- **1.3** Fim.

#### Fluxo Alternativo 2 - Confirmação de senha divergente

- **2.1** No passo 5, o sistema identifica que a nova senha e a sua confirmação não coincidem.
- **2.2** O sistema exibe a mensagem: "A nova senha e a confirmação não coincidem".
- **2.3** Retorna ao passo 4 do fluxo principal.

### Fluxos de exceção

#### Fluxo Exceção 1 - Falha na comunicação com o Banco de Dados

- **1.1** No passo 7, o sistema não consegue atualizar a senha devido a uma falha interna de I/O ou queda de conexão.
- **1.2** O sistema mantém a senha anterior e o token válido e exibe a mensagem: "Não foi possível redefinir a senha no momento. Tente novamente mais tarde".
- **1.3** Fim.

## CU02 - C4 – Realizar Login - Cenário Encerrar Sessão

- **Objetivo:** Finalizar a sessão autenticada do usuário na plataforma.
- **Pré-condição:** O usuário deve estar autenticado na plataforma.
- **Pós-condição:** A sessão do usuário é encerrada e as funcionalidades restritas ficam indisponíveis até um novo login.
- **Atores:** Usuário
- **Ativação:** O usuário seleciona a opção "Sair" na interface.

### Fluxo principal

1. O usuário seleciona a opção "Sair".
2. O sistema invalida a sessão autenticada do usuário.
3. O sistema remove os dados de sessão armazenados no navegador.
4. O sistema direciona o usuário à página inicial sem acesso às funcionalidades restritas.

### Fluxos alternativos

#### Fluxo Alternativo 1 - Sessão expirada

- **1.1** O sistema identifica que a sessão do usuário atingiu o tempo máximo de validade de 24 horas, contadas a partir do login.
- **1.2** O sistema encerra a sessão automaticamente.
- **1.3** O sistema exibe a mensagem: "Sua sessão expirou. Faça login novamente" e direciona o usuário à tela de login.
- **1.4** Fim.

## Observações para a implementação

Decisões já implementadas (com a variável de ambiente que as controla) e o que continua pendente. Detalhes em `docs/decisoes-e-pendencias.md`. Onde houver conflito com o texto acima, vale o que está aqui e o documento do TC deve ser corrigido.

- Sessão: JWT válido por 24 horas a partir do login, não renovável. A sessão fica na tabela `sessao`, e o logout a revoga. Não há prazo de inatividade separado (C4-FA1).
- `JWT_SECRET` deve estar preenchido no `.env`. Sem ele, a API usa um segredo temporário (com aviso no log) e as sessões se perdem a cada reinício.
- RN21: o bloqueio vale também para e-mails sem conta, para não revelar se o e-mail existe.
- RN22: o link é de uso único e vale 10 minutos; um novo link invalida os anteriores. A resposta é a mesma para e-mail cadastrado ou não.
- Envio de e-mail: SMTP configurado por variáveis de ambiente (`SMTP_*`, `FRONTEND_URL`). Em desenvolvimento, o Mailpit do `docker-compose.yml` fica em `http://localhost:8025`.
