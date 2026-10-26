# Como deixar as automações rodando sozinhas

Este tutorial é para quem nunca usou cron. Ele serve para **Mac e Linux**. Os comandos abaixo são para colar no Terminal, um bloco de cada vez.

O cron é o agendador do sistema: você informa o horário e o comando, e ele executa automaticamente. Não precisa deixar o Terminal aberto depois de configurar.

O computador ou servidor precisa estar **ligado e acordado no horário**. Se estiver desligado ou dormindo, não conte com o envio ao ligar depois. Para rodar todos os dias sem depender do seu notebook, use um servidor Linux que permaneça ligado.

No Windows, estes comandos não funcionam diretamente no PowerShell. Este guia cobre Mac e servidores Linux; o Windows tem seu próprio Agendador de Tarefas.

## 1. Prepare as automações antes de agendar

Baixe o repositório pelo botão **Code → Download ZIP** no GitHub e descompacte. Você pode renomear a pasta para `meta-ads-automacoes` e guardá-la na sua pasta pessoal. Depois de agendar, mantenha a pasta no mesmo lugar.

Siga a instalação das automações que você quer usar:

- [Instalar o relatório diário](relatorio-diario/README.md#instalação).
- [Instalar o relatório semanal](relatorio-semanal/README.md#instalação).
- [Instalar o monitor de saldo](saldo/README.md#instalação).

Cada uma precisa do seu próprio arquivo `.env` preenchido. Para envio ao WhatsApp, sua Evolution API precisa estar funcionando e a instância precisa estar conectada.

Para receber o resumo de saldo todos os dias, mesmo sem pendências, coloque `ALWAYS_NOTIFY=1` no `.env` da pasta `saldo`.

## 2. Abra o Terminal na pasta do projeto

**No Mac:** abra o aplicativo Terminal. Digite `cd `, com um espaço depois, arraste a pasta do projeto do Finder para a janela do Terminal e aperte Enter.

**No Linux:** abra o Terminal ou entre no seu servidor por SSH. Use `cd` com o caminho onde você salvou o projeto. Por exemplo, se ele estiver na sua pasta pessoal:

```bash
cd "$HOME/meta-ads-automacoes"
```

Confira onde você está:

```bash
pwd
ls
```

O `pwd` mostra o caminho completo. O `ls` deve mostrar as pastas `relatorio-diario`, `relatorio-semanal` e `saldo`. **Guarde o caminho mostrado pelo `pwd`: vamos usá-lo no passo 5.** Se você baixou apenas uma automação, use como base a pasta que contém essa automação e ajuste os caminhos dos exemplos.

## 3. Teste manualmente

Na pasta principal do projeto, execute apenas os comandos das automações que você instalou:

```bash
./relatorio-diario/.venv/bin/python ./relatorio-diario/main.py --dry-run
./relatorio-semanal/.venv/bin/python ./relatorio-semanal/semanal.py --dry-run
./saldo/.venv/bin/python ./saldo/check.py --no-wa
```

Os dois primeiros geram imagens em `saida/` dentro da respectiva automação. O terceiro salva o saldo em `saldo/reports/report.md`. Esses comandos consultam a Meta, mas não enviam mensagens pelo WhatsApp.

Se aparecer erro, resolva antes de agendar. O cron executará o mesmo programa e encontrará o mesmo problema.

Para conferir também o envio real, rode o comando desejado sem `--dry-run` ou sem `--no-wa`. Isso enviará mensagens aos números que você colocou no `.env`.

## 4. Confira o horário e o serviço do cron

Veja a data, a hora e o fuso do computador ou servidor:

```bash
date
```

Os agendamentos deste guia seguem **o fuso do sistema**. Por exemplo, 08h em um servidor configurado em UTC não é 08h de Brasília. Confira isso antes de cadastrar os horários.

**No Mac:** o cron já faz parte do sistema. Continue para o próximo passo. Se o macOS perguntar se o Terminal pode administrar o computador para criar o agendamento, permita essa operação.

**No Ubuntu ou Debian com systemd:** se o cron ainda não estiver instalado ou ativo, execute:

```bash
sudo apt update
sudo apt install cron nano
sudo systemctl enable --now cron
systemctl is-active cron
```

O último comando deve responder `active`. O `sudo` pode pedir a senha do usuário do servidor; enquanto você digita, os caracteres não aparecem. Isso é normal.

Outras distribuições Linux podem usar outro gerenciador de pacotes e outro nome para o serviço, como `crond`. Os comandos acima são específicos para Ubuntu/Debian com systemd.

## 5. Abra a lista de agendamentos e cole a configuração

Execute como **o mesmo usuário que instalou as automações**, sem `sudo`:

```bash
EDITOR=nano crontab -e
```

Isso abre um editor de texto dentro do Terminal. Se aparecer uma mensagem dizendo que ainda não existe crontab para esse usuário, é normal no primeiro uso. Se aparecer uma escolha de editor, escolha `nano`.

Se já houver texto no arquivo, mantenha os agendamentos existentes e acrescente o bloco abaixo no final. Cada comando de agendamento precisa ficar em uma única linha; a quebra visual na tela do editor é normal.

**Antes de salvar, substitua `/caminho/completo/meta-ads-automacoes` pelo caminho exato que o `pwd` mostrou no passo 2.** Mantenha as aspas. Não coloque `~` ou `$HOME` nessa configuração: cole o caminho completo.

```cron
# Pasta onde voce salvou o projeto: substitua este caminho
AUTOMACOES_DIR="/caminho/completo/meta-ads-automacoes"

# Relatorio diario: todos os dias, as 08h
0 8 * * * "$AUTOMACOES_DIR/relatorio-diario/.venv/bin/python" -u "$AUTOMACOES_DIR/relatorio-diario/main.py" >> "$AUTOMACOES_DIR/relatorio-diario/cron.log" 2>&1

# Relatorio semanal: sexta-feira, as 08h30
30 8 * * 5 "$AUTOMACOES_DIR/relatorio-semanal/.venv/bin/python" -u "$AUTOMACOES_DIR/relatorio-semanal/semanal.py" >> "$AUTOMACOES_DIR/relatorio-semanal/cron.log" 2>&1

# Saldo: todos os dias, as 09h
0 9 * * * "$AUTOMACOES_DIR/saldo/.venv/bin/python" -u "$AUTOMACOES_DIR/saldo/check.py" >> "$AUTOMACOES_DIR/saldo/cron.log" 2>&1
```

Pode apagar as linhas das automações que não quiser agendar. Não precisa escrever suas senhas ou tokens aqui: cada programa lê o `.env` da sua própria pasta.

O caminho termina em `.venv/bin/python` para usar o Python com as dependências instaladas. Por isso não precisa ativar o ambiente virtual dentro do cron. O `-u` faz as mensagens aparecerem no arquivo de log durante a execução; `>>` acrescenta as mensagens sem apagar as anteriores, e `2>&1` registra também os erros.

### Como salvar e sair do editor

1. Aperte **Control + O** para salvar. No Mac, é a tecla Control, não Command.
2. Aperte **Enter** para confirmar o nome do arquivo.
3. Aperte **Control + X** para sair.

Confira o resultado:

```bash
crontab -l
```

Você deve ver o bloco que acabou de salvar, com seu caminho preenchido. Se o editor informar erro de sintaxe ao sair, volte e confira as linhas; o agendamento só estará cadastrado depois de salvar sem erro. Com o serviço ativo, não é necessário reiniciá-lo a cada edição.

## 6. Teste o cron sem esperar até amanhã

Vamos criar um teste que apenas grava a hora em um arquivo. Ele não consulta a Meta nem envia WhatsApp.

Abra novamente:

```bash
EDITOR=nano crontab -e
```

Acrescente esta linha **abaixo da configuração `AUTOMACOES_DIR`** e salve como no passo anterior:

```cron
* * * * * /bin/date >> "$AUTOMACOES_DIR/cron-teste.log" 2>&1
```

Espere a virada do próximo minuto; se ainda não aparecer, aguarde mais um minuto. Na pasta principal do projeto, confira:

```bash
tail -n 5 cron-teste.log
```

Se aparecer uma data e hora, o cron conseguiu executar o comando e gravar na pasta. O teste confirma o agendador; o teste manual do passo 3 confirma o Python e a configuração das automações.

**Depois do teste, abra `EDITOR=nano crontab -e`, apague somente a linha de teste e salve.** Mantenha a configuração da pasta e os horários das automações.

## 7. Veja se o relatório rodou

Depois do horário agendado, na pasta principal do projeto, leia o registro da automação desejada:

```bash
tail -n 50 relatorio-diario/cron.log
tail -n 50 relatorio-semanal/cron.log
tail -n 50 saldo/cron.log
```

O arquivo `cron.log` é um registro de execução: ele mostra o que o programa fez e os erros encontrados. Ele é criado quando o cron tenta executar o comando. Antes da primeira execução, é normal ele ainda não existir.

## Como mudar o horário ou pausar

Cada linha tem cinco campos de horário antes do comando:

```text
minuto  hora  dia-do-mes  mes  dia-da-semana  comando
```

| Começo da linha | Quando executa |
| --- | --- |
| `0 8 * * *` | Todo dia às 08h |
| `30 8 * * 5` | Sexta-feira às 08h30 |
| `0 9 * * *` | Todo dia às 09h |
| `0 10 * * 1-5` | De segunda a sexta às 10h |

O `*` significa qualquer valor naquele campo. A hora usa o formato de 24 horas. Para trocar 08h por 14h, por exemplo, mude `0 8 * * *` para `0 14 * * *` e mantenha o restante da linha.

Para pausar uma automação, abra `EDITOR=nano crontab -e` e coloque `#` no início da linha dela. Para reativar, retire o `#`. Para remover definitivamente, apague somente a linha desejada e salve. Evite `crontab -r`: ele remove todos os agendamentos do usuário, inclusive os de outros projetos.

## Se não funcionar

| O que aconteceu | O que conferir |
| --- | --- |
| `No such file or directory` | Confira o caminho do projeto, o nome da pasta e se criou a `.venv`. Se moveu ou renomeou a pasta, atualize o cron. |
| `ModuleNotFoundError` | Instale as dependências na `.venv` daquela automação, conforme seu README. |
| Chromium ou navegador não encontrado | Dentro da pasta do relatório, execute `.venv/bin/python -m playwright install chromium` como o mesmo usuário do cron. |
| Token ausente ou expirado | Preencha ou atualize `META_SYSTEM_USER_TOKEN` no `.env` da automação. O cron não carrega automaticamente as variáveis que você configurou no Terminal. |
| Gerou arquivos, mas não enviou WhatsApp | Confira os destinatários, a chave e o endereço do Evolution, e se a instância está conectada. No saldo, confira também `ALWAYS_NOTIFY`. |
| Enviou em outro horário | Confira `date` no computador ou servidor que executa o cron. |
| O teste de data não criou arquivo | Confira `crontab -l`, o caminho da pasta, suas permissões e, no Linux, se o serviço está ativo. |
| Funciona manualmente, mas no Mac aparece `Operation not permitted` | Evite guardar o projeto em pastas protegidas como Mesa, Documentos ou Downloads; prefira uma pasta na sua pasta pessoal. Se a restrição persistir, confira as permissões de privacidade do macOS para o processo que está sendo bloqueado. |
| Não rodou com o notebook fechado | Confira se o computador estava acordado no horário. Para disponibilidade contínua, use um servidor. |

Os logs e relatórios podem conter dados das suas contas. Ao pedir ajuda, envie apenas o trecho necessário e oculte informações privadas.

Referências técnicas: [formato do crontab](https://man7.org/linux/man-pages/man5/crontab.5.html) e [funcionamento do serviço cron](https://man7.org/linux/man-pages/man8/cron.8.html).

[Voltar ao guia principal](README.md)
