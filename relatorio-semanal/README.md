# Relatório semanal

Compara os últimos 7 dias completos com os 7 dias imediatamente anteriores. Executado na sexta, fecha sexta a quinta; executado em outro dia, usa os 7 dias anteriores a esse dia. Gera um resumo geral e um card por conta, em HTML e PNG. O envio das imagens usa a Evolution API.

Esta pasta é independente das outras automações.

## Instalação

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
python semanal.py --help
python semanal.py --dry-run                 # consulta Meta e gera arquivos, sem enviar
python semanal.py                           # gera e envia aos números configurados
python semanal.py --conta ID_DA_CONTA --dry-run
python semanal.py --data 2026-10-23 --dry-run # data-base da execução
```

`--conta` pode ser repetido para selecionar várias contas. `--destinatario NUMERO_COM_DDI` pode ser repetido para substituir os destinatários das imagens naquela execução.

Os arquivos ficam em `saida/`, ignorada pelo Git. `--dry-run` também impede avisos por WhatsApp se ocorrer uma falha.

Sem destinatário de imagens, o envio usa somente `WHATSAPP_RECIPIENT`, se configurado. Nenhum número é descoberto automaticamente pela instância.

## Métricas

O resultado de cada campanha considera a meta de otimização do conjunto, o evento do pixel e, quando disponível, a conversão personalizada. O relatório separa tipos como leads, compras, conversas e cliques.

`MIN_SPEND_7D` filtra contas com pouco ou nenhum investimento na janela analisada. `IGNORE_ACCOUNTS` remove contas pelo ID. Os valores dos relatórios são formatados em reais, para contas BRL.

O modo sem envio ainda exige o token e acesso à Meta. A versão da API pode ser alterada em `META_API_VERSION`.

Veja o [guia geral](../README.md) para agendamento e configuração das credenciais.

## Período personalizado

```bash
python semanal.py --inicio 2026-10-01 --fim 2026-10-07 --dry-run
python semanal.py --sem-resumo
```

O período é inclusivo e comparado com o mesmo número de dias imediatamente anteriores. `--inicio` e `--fim` devem ser usados juntos. `--sem-resumo` mantém apenas os cards individuais.

## Agendar para rodar sozinho

Veja o [tutorial de cron para iniciantes](../CRON.md), com os comandos de agendamento, como salvar, testar, consultar os logs e pausar esta automação.
