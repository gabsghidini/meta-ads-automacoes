# Monitor de saldo Meta Ads

Descobre as contas acessíveis ao seu token, consulta saldo, fatura e situação e salva um relatório Markdown. Pode enviar um resumo em texto pelo WhatsApp usando sua Evolution API.

Esta pasta funciona sozinha e usa somente a biblioteca padrão do Python 3.10+.

## Instalação

**No Windows, siga o [guia de instalação e agendamento para Windows](../WINDOWS.md).** Os comandos abaixo são para Mac/Linux.

```bash
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
```

Edite `.env` com seu `META_SYSTEM_USER_TOKEN`. Para os envios, configure também `EVOLUTION_API_BASE_URL`, `EVOLUTION_API_KEY`, `WHATSAPP_INSTANCE` e `WHATSAPP_RECIPIENT`.

## Uso

```bash
python check.py --no-wa         # consulta e salva, sem enviar ao WhatsApp
python check.py --no-wa --json  # também imprime os dados em JSON
python check.py                 # consulta, salva e envia quando há pendências
```

Os arquivos ficam em `reports/report.md` e `reports/history/AAAA-MM-DD.md`, ignorados pelo Git. O comando sem envio ainda consulta a Meta e precisa de um token válido.

## Limites

| Variável | Padrão | Significado |
| --- | --- | --- |
| `PREPAID_URGENT` | `0` | Saldo pré-pago até esse valor entra como urgente e precisa de recarga |
| `PREPAID_LOW` | `25` | Saldo pré-pago até esse valor entra como atenção |
| `CARTAO_HIGH` | `1000` | Fatura de cartão a partir desse valor entra como atenção |
| `ALWAYS_NOTIFY` | `0` | `1` envia resumo em toda execução; `0` envia quando há pendências de ação |

Os limites são aplicados na moeda de cada conta. Não há conversão cambial. `IGNORE_ACCOUNTS` permite excluir IDs.

Com `ALWAYS_NOTIFY=0`, o aviso por saldo baixo acima do limite urgente não dispara sozinho: o resumo é enviado se houver alguma pendência de ação e inclui então as contas em atenção. Use `ALWAYS_NOTIFY=1` para receber o resumo diariamente.

O campo `balance` de uma conta com cartão representa fatura, não crédito disponível. Quando a API não informa o tipo de financiamento ou saldo pré-pago de forma reconhecível, o relatório marca a situação como desconhecida; confira a conta no Gerenciador de Anúncios.

Veja o [guia geral](../README.md) para agendamento e configuração.

## Agendar para rodar sozinho

- **Windows:** [guia do Agendador de Tarefas](../WINDOWS.md). O arquivo `executar-windows.cmd` desta pasta executa a automação e grava a saída em `cron.log`; aceita os mesmos argumentos do script Python.
- **Mac/Linux:** [tutorial de cron para iniciantes](../CRON.md).
