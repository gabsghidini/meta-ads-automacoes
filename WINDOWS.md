# Windows: instalar e agendar as três automações

No Windows, usamos o **Agendador de Tarefas**, que já vem com o sistema. Este guia mostra a instalação e o agendamento pela interface, sem precisar de Linux ou cron.

Use o **Prompt de Comando (`cmd`)** nos exemplos abaixo. Não precisa abrir como administrador. Execute um comando de cada vez e, se aparecer erro, resolva antes de continuar.

## 1. Instale o Python e baixe o projeto

1. Instale o Python 3.10 ou superior pelo [site oficial do Python para Windows](https://www.python.org/downloads/windows/). Escolha uma versão estável, compatível com seu Windows. Se o instalador mostrar **Add Python to PATH**, marque essa opção.
2. Feche e abra novamente o Prompt de Comando depois da instalação.
3. No GitHub do projeto, clique em **Code → Download ZIP**.
4. Clique com o botão direito no ZIP e escolha **Extrair Tudo**. Não execute os arquivos de dentro do ZIP.
5. Renomeie a pasta extraída para `meta-ads-automacoes` e guarde em um local fixo. Dentro dela devem aparecer `relatorio-diario`, `relatorio-semanal` e `saldo`.

Para abrir o Prompt de Comando nessa pasta, abra a pasta no Explorador de Arquivos, clique na barra de endereço, digite `cmd` e aperte Enter.

Confira o Python:

```bat
py --version
```

Deve aparecer `Python 3.x.x`, na versão 3.10 ou superior. Se `py` não for reconhecido, tente `python --version`. Se esse funcionar, substitua `py` por `python` nos comandos de criação da `.venv` deste guia. Se nenhum funcionar, confira a instalação do Python e abra um novo Prompt.

## 2. Instale as dependências

Com o Prompt aberto na pasta principal `meta-ads-automacoes`, copie estes comandos, um de cada vez. Você pode instalar somente as automações que pretende usar.

### Relatório diário

```bat
py -m venv relatorio-diario\.venv
relatorio-diario\.venv\Scripts\python.exe -m pip install -r relatorio-diario\requirements.txt
relatorio-diario\.venv\Scripts\python.exe -m playwright install chromium
copy relatorio-diario\.env.example relatorio-diario\.env
```

### Relatório semanal

```bat
py -m venv relatorio-semanal\.venv
relatorio-semanal\.venv\Scripts\python.exe -m pip install -r relatorio-semanal\requirements.txt
relatorio-semanal\.venv\Scripts\python.exe -m playwright install chromium
copy relatorio-semanal\.env.example relatorio-semanal\.env
```

### Monitor de saldo

```bat
py -m venv saldo\.venv
copy saldo\.env.example saldo\.env
```

O monitor de saldo não precisa instalar pacotes adicionais. Os relatórios baixam o Chromium para gerar as imagens; aguarde o download terminar.

Se o comando `copy` perguntar se quer substituir um `.env` existente, responda **N** para manter suas configurações. Você só precisa copiar o arquivo de exemplo na primeira instalação.

## 3. Preencha suas credenciais

Abra os arquivos de configuração no Bloco de Notas:

```bat
notepad relatorio-diario\.env
notepad relatorio-semanal\.env
notepad saldo\.env
```

Preencha apenas os arquivos das automações instaladas. Em cada um, coloque seus próprios dados depois do sinal `=`:

| Campo | O que preencher |
| --- | --- |
| `META_SYSTEM_USER_TOKEN` | Seu token Meta com acesso às contas de anúncios |
| `EVOLUTION_API_BASE_URL` | Endereço da sua Evolution API |
| `EVOLUTION_API_KEY` | Chave da sua Evolution API |
| `WHATSAPP_INSTANCE` | Nome exato da instância WhatsApp conectada |
| `RELATORIO_RECIPIENTS` | Nos relatórios: números que recebem as imagens, com DDI e separados por vírgula |
| `WHATSAPP_RECIPIENT` | No saldo: números que recebem o resumo; nos relatórios: números que recebem avisos de falha |

No arquivo do saldo, use `ALWAYS_NOTIFY=1` se quiser receber o resumo todos os dias, mesmo sem pendências. Nos relatórios, `BRAND_NAME` define o nome no cabeçalho.

Salve com **Ctrl + S**. O arquivo deve se chamar exatamente `.env`, sem `.txt` no final. Se precisar conferir, ative a exibição de extensões de nomes de arquivos no Explorador.

A Evolution API deve estar instalada e funcionando, e a instância deve estar conectada ao WhatsApp. Este projeto não instala o servidor Evolution; ele usa o endereço e a chave que você informar. Se não tiver essas credenciais ou o token Meta, será necessário configurar esses serviços antes dos envios.

## 4. Teste antes de agendar

Cada automação inclui um arquivo `executar-windows.cmd`. Ele encontra a pasta automaticamente, usa o Python da `.venv` e grava as mensagens em `cron.log`. O nome do log é o mesmo nas duas plataformas.

Na pasta principal do projeto, execute:

```bat
relatorio-diario\executar-windows.cmd --dry-run
relatorio-semanal\executar-windows.cmd --dry-run
saldo\executar-windows.cmd --no-wa
```

Esses testes consultam a Meta, mas não enviam mensagens pelo WhatsApp. Como a saída vai para o log, o Prompt pode ficar sem mostrar mensagens enquanto o programa trabalha. Espere o comando terminar e a linha do Prompt reaparecer.

Leia o resultado abrindo os logs:

```bat
notepad relatorio-diario\cron.log
notepad relatorio-semanal\cron.log
notepad saldo\cron.log
```

As imagens ficam na pasta `saida` de cada relatório. O saldo fica em `saldo\reports\report.md`. Se aparecer erro, confira a seção de problemas comuns no final.

Para testar o envio real, execute **somente a automação desejada**, sem o argumento de teste:

```bat
relatorio-diario\executar-windows.cmd
relatorio-semanal\executar-windows.cmd
saldo\executar-windows.cmd
```

Esses comandos enviam aos números configurados. Não precisa deixar o Prompt aberto depois de terminar os testes.

## 5. Abra o Agendador de Tarefas

1. Aperte a tecla **Windows**.
2. Pesquise **Agendador de Tarefas** e abra o aplicativo.
3. No painel da direita, clique em **Criar Tarefa…**.

Vamos criar uma tarefa por automação. Comece pelo relatório diário.

### Aba Geral

- **Nome:** `Meta Ads - Relatorio diario`.
- Selecione seu próprio usuário, o mesmo que fez a instalação.
- Para começar, marque **Executar somente quando o usuário estiver conectado**. Assim, não precisa informar uma senha para salvar; você precisa permanecer conectado à sua conta no horário. Pode bloquear a tela, mas não sair da conta.
- Não é necessário marcar **Executar com privilégios mais altos**.

Para executar mesmo depois de sair da conta, existe a opção **Executar estando o usuário conectado ou não**. Ela pode pedir a senha da conta Windows ao salvar; o PIN do Windows Hello não é essa senha. A configuração mais simples para este tutorial é permanecer conectado com a primeira opção.

### Aba Disparadores

1. Clique em **Novo…**.
2. Em **Iniciar a tarefa**, escolha **Em um agendamento**.
3. Escolha **Diariamente**, repetindo a cada **1 dia**.
4. Defina a hora **08:00:00** e confira a data de início.
5. Mantenha **Habilitado** marcado e clique em **OK**.

Os horários seguem a hora e o fuso do Windows. Confira o relógio do computador.

### Aba Ações

1. Clique em **Novo…** e escolha **Iniciar um programa**.
2. Preencha os campos conforme o exemplo abaixo.

Vamos usar `C:\Automacoes\meta-ads-automacoes` apenas como exemplo. **Troque esse começo pelo caminho onde você guardou o projeto.** Para descobrir o caminho, abra a pasta no Explorador e copie a barra de endereço.

**Programa/script:**

```text
C:\Windows\System32\cmd.exe
```

Se seu Windows estiver instalado em outro local, use o `cmd.exe` da pasta `System32` dessa instalação.

**Adicionar argumentos:**

```text
/d /c ""C:\Automacoes\meta-ads-automacoes\relatorio-diario\executar-windows.cmd""
```

Mantenha as **duas aspas** antes e depois do caminho nessa linha: elas permitem executar o arquivo mesmo se houver espaços no nome das pastas. Não acrescente `--dry-run` se quiser que a tarefa envie os relatórios.

**Iniciar em:**

```text
C:\Automacoes\meta-ads-automacoes\relatorio-diario
```

Nesse último campo, use somente o caminho da pasta, **sem aspas**. Clique em **OK**.

### Abas Condições e Configurações

- Em **Condições**, se quiser permitir a execução na bateria, desmarque a opção de iniciar somente com o computador ligado à energia e confira também a opção de parar ao mudar para bateria. Para uso diário, prefira deixá-lo na tomada.
- Se quiser tentar acordar o computador suspenso, marque **Ativar o computador para executar esta tarefa**. Isso depende das configurações de energia e do equipamento; não liga um computador desligado. Teste no seu computador antes de depender dessa opção.
- Em **Configurações**, mantenha **Permitir que a tarefa seja executada por demanda** marcado.
- Marque **Executar a tarefa assim que possível após um início agendado ser perdido** se quiser permitir o envio atrasado ao voltar a usar o computador.
- Em **Se a tarefa já estiver em execução**, escolha **Não iniciar uma nova instância**, para evitar duas execuções da mesma automação ao mesmo tempo.

Clique em **OK** para salvar a tarefa.

## 6. Cadastre o semanal e o saldo

Repita o passo 5 para cada automação. O programa continua sendo o `cmd.exe`; altere nome, horário, argumentos e a pasta de início:

| Campo | Relatório semanal | Saldo |
| --- | --- | --- |
| Nome | `Meta Ads - Relatorio semanal` | `Meta Ads - Saldo` |
| Disparador | Semanalmente, a cada 1 semana, sexta-feira às 08h30 | Diariamente, a cada 1 dia, às 09h |
| Final do caminho do arquivo | `relatorio-semanal\executar-windows.cmd` | `saldo\executar-windows.cmd` |
| Final da pasta em “Iniciar em” | `relatorio-semanal` | `saldo` |

Exemplo de **Adicionar argumentos** para o semanal:

```text
/d /c ""C:\Automacoes\meta-ads-automacoes\relatorio-semanal\executar-windows.cmd""
```

Exemplo para o saldo:

```text
/d /c ""C:\Automacoes\meta-ads-automacoes\saldo\executar-windows.cmd""
```

## 7. Teste sem esperar pelo horário

1. No painel esquerdo, clique em **Biblioteca do Agendador de Tarefas**.
2. Localize a tarefa que criou, clique com o botão direito e escolha **Executar**.
3. Aguarde a execução terminar e atualize a lista, se necessário.
4. Confira o `cron.log` da automação e o recebimento no WhatsApp. Essa execução faz o envio real.

Para testar pelo agendador sem enviar, acrescente temporariamente ` --dry-run` ao final dos argumentos do relatório, depois das aspas. Para o saldo, use ` --no-wa`. Retire esse argumento depois do teste para permitir os envios nos horários cadastrados.

Confira as colunas **Horário da Próxima Execução** e **Resultado da Última Execução**. Em geral, `0x0` significa que o processo terminou sem informar erro. Isso, sozinho, não garante entrega no WhatsApp: leia o log e confira a mensagem, especialmente no saldo, que pode terminar sem enviar se não houver pendências.

## Mudar horário ou pausar

- **Mudar horário:** botão direito na tarefa → **Propriedades** → **Disparadores** → selecione o disparador → **Editar**.
- **Pausar:** botão direito na tarefa → **Desabilitar**.
- **Voltar a rodar:** botão direito → **Habilitar**.
- **Remover:** botão direito → **Excluir**. Isso remove o agendamento, sem apagar os arquivos do projeto.

## Problemas comuns

| Problema | O que conferir |
| --- | --- |
| “Python local nao encontrado” | Crie a `.venv` daquela automação, conforme o passo 2. No Windows, o executável fica em `Scripts\python.exe`. |
| O arquivo abre no Bloco de Notas | Execute o `.cmd`, não o `.py`. No Agendador, confira o programa `cmd.exe` e os argumentos. |
| Não encontra o arquivo ou resultado `0x1` | Confira o caminho, as aspas dos argumentos e a pasta “Iniciar em”. Depois leia o log; `0x1` também pode ser erro da automação. |
| Não encontra um pacote Python | Refaça o comando `pip install -r` do passo 2 para a pasta correspondente. |
| Não encontra o Chromium | Refaça o comando `playwright install chromium` do passo 2, usando o mesmo usuário do agendamento. |
| Token ausente ou expirado | Confira o `.env` daquela pasta e renove seu token Meta se necessário. |
| Nada acontece no horário | Confira se a tarefa está habilitada, a data de início, o horário do Windows, a opção de bateria e se o usuário estava conectado. |
| O notebook estava fechado ou desligado | Ele precisa estar disponível para executar. A opção de acordar pode ajudar com suspensão, dependendo do equipamento, mas não com o computador desligado. |
| Os arquivos foram gerados, mas não chegou WhatsApp | Confira endereço/chave do Evolution, instância conectada, destinatários e se deixou `--dry-run` ou `--no-wa` nos argumentos. No saldo, confira `ALWAYS_NOTIFY`. |
| Moveu a pasta depois de instalar | Atualize os caminhos no Agendador e recrie a `.venv` no novo local, reinstalando as dependências. |
| A janela preta abre e fecha rapidamente | Abra o Prompt na pasta e execute o `.cmd` por ali; depois consulte `cron.log`. Não precisa acrescentar `pause` no arquivo agendado. |

Tokens, telefones, logs e relatórios são seus dados locais. Não publique seu `.env` nem envie logs completos sem revisar o conteúdo.

Referências: [Python no Windows](https://www.python.org/downloads/windows/), [ambientes virtuais](https://docs.python.org/3/library/venv.html), [Agendador de Tarefas da Microsoft](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page) e [opções das tarefas](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings).

[Voltar ao guia principal](README.md)
