# Relatório diário

Compara o dia anterior com anteontem e a média diária dos 7 dias anteriores ao dia analisado. Gera um resumo geral e um card por conta, em HTML e PNG. O envio das imagens usa a Evolution API.

Esta pasta é independente das outras automações.

## Instalação

**No Windows, siga o [guia de instalação e agendamento para Windows](../WINDOWS.md).** Os comandos abaixo são para Mac/Linux.

Dentro desta pasta, com Python 3.10+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

Em servidores Linux, o Chromium pode precisar de bibliotecas do sistema. Quando necessário, instale com `python -m playwright install --with-deps chromium`.

Edite `.env`: preencha `META_SYSTEM_USER_TOKEN`. Para enviar imagens, preencha também `EVOLUTION_API_BASE_URL`, `EVOLUTION_API_KEY`, `WHATSAPP_INSTANCE` e `RELATORIO_RECIPIENTS`. Para receber avisos de falha, configure `WHATSAPP_RECIPIENT`.

`BRAND_NAME` define o nome no cabeçalho. Não há uma marca fixa nos templates.

## Uso

```bash
python main.py --help
python main.py --dry-run                 # consulta Meta e gera arquivos, sem enviar
python main.py                           # gera e envia aos números configurados
python main.py --conta ID_DA_CONTA --dry-run
python main.py --data 2026-10-23 --dry-run # data-base da execução
```

`--conta` pode ser repetido para selecionar várias contas. `--destinatario NUMERO_COM_DDI` pode ser repetido para substituir os destinatários das imagens naquela execução.

Os arquivos ficam em `saida/`, ignorada pelo Git. `--dry-run` também impede avisos por WhatsApp se ocorrer uma falha.

Sem destinatário de imagens, o envio usa somente `WHATSAPP_RECIPIENT`, se configurado. Nenhum número é descoberto automaticamente pela instância.

## Métricas

O resultado de cada campanha considera a meta de otimização do conjunto, o evento do pixel e, quando disponível, a conversão personalizada. O relatório separa tipos como leads, compras, conversas e cliques.

`MIN_SPEND_7D` filtra contas com pouco ou nenhum investimento na janela analisada. `IGNORE_ACCOUNTS` remove contas pelo ID. Os valores dos relatórios são formatados em reais, para contas BRL.

O modo sem envio ainda exige o token e acesso à Meta. A versão da API pode ser alterada em `META_API_VERSION`.

Veja o [guia geral](../README.md) para agendamento e configuração das credenciais.

## Agendar para rodar sozinho

- **Windows:** [guia do Agendador de Tarefas](../WINDOWS.md). O arquivo `executar-windows.cmd` desta pasta executa a automação e grava a saída em `cron.log`; aceita os mesmos argumentos do script Python.
- **Mac/Linux:** [tutorial de cron para iniciantes](../CRON.md).
