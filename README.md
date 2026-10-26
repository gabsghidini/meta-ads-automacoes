# Automações de Meta Ads

Três automações Python para acompanhar campanhas e saldos e enviar relatórios pelo WhatsApp usando a Evolution API.

| Pasta | O que faz | Horário sugerido |
| --- | --- | --- |
| [relatorio-diario](relatorio-diario/) | Resumo em imagem e um card por conta: ontem, anteontem e média dos 7 dias anteriores | Todos os dias, 08h |
| [relatorio-semanal](relatorio-semanal/) | Imagens com os últimos 7 dias completos comparados aos 7 anteriores | Sexta-feira, 08h30 |
| [saldo](saldo/) | Consulta saldos, faturas e situação das contas; salva Markdown e envia alertas em texto | Todos os dias, 09h |

Cada pasta funciona sozinha. Você pode baixar apenas a automação que quiser; nenhuma depende das outras pastas ou de outro projeto local.

## O que você precisa

- Python 3.10 ou superior.
- Seu próprio token Meta com acesso de leitura às contas de anúncios que deseja acompanhar. O acesso aos campos depende das permissões do token e dos ativos atribuídos a ele.
- Para enviar no WhatsApp: sua Evolution API em execução, uma instância conectada e a respectiva chave de API. O repositório contém o cliente de envio; a instalação do servidor Evolution é separada.
- Para gerar as imagens: Jinja2, Playwright e o Chromium instalado pelo Playwright.

O monitor de saldo usa somente a biblioteca padrão do Python.

## Comece por aqui

**Usa Windows? Siga o [guia completo para Windows](WINDOWS.md), da instalação ao agendamento automático.**

1. Abra a pasta da automação desejada e siga seu `README.md`.
2. Copie `.env.example` para `.env` e preencha suas credenciais.
3. Nos relatórios, use `--dry-run` para gerar as imagens sem enviar mensagens. No saldo, use `--no-wa`.
4. Confira os arquivos gerados e depois execute o envio.
5. Se quiser, configure o agendamento no seu computador ou servidor.

Os modos sem envio consultam dados reais da sua conta Meta e precisam do token. Para validar o código sem credenciais, veja os testes abaixo.

## Configuração

Cada pasta lê apenas seu próprio `.env`. Variáveis de ambiente do processo têm prioridade sobre o arquivo. Não há destinatário, instância, conta de anúncios ou token embutido no código.

| Variável | Uso |
| --- | --- |
| `META_SYSTEM_USER_TOKEN` | Seu token da Meta |
| `META_API_VERSION` | Versão da Graph API; ajuste conforme o seu aplicativo |
| `META_BUSINESS_ID` | Opcional: portfólio empresarial usado na descoberta de contas |
| `IGNORE_ACCOUNTS` | IDs de contas que devem ser ignoradas, separados por vírgula |
| `EVOLUTION_API_BASE_URL` | Endereço da sua Evolution API |
| `EVOLUTION_API_KEY` | Sua chave da Evolution API |
| `WHATSAPP_INSTANCE` | Nome exato da instância conectada |
| `WHATSAPP_RECIPIENT` | Números com DDI para o saldo e os avisos de falha |
| `RELATORIO_RECIPIENTS` | Números com DDI para as imagens; aceita vários separados por vírgula |
| `BRAND_NAME` | Nome exibido no cabeçalho dos relatórios |

As contas são descobertas a partir do acesso do token. Use um token restrito aos ativos que você pretende incluir. Os relatórios selecionam contas com gasto na janela analisada, conforme `MIN_SPEND_7D`.

As imagens usam formatação em reais (`R$`); utilize os relatórios com contas BRL. O saldo mostra a moeda de cada conta, e seus limites são aplicados nessa moeda.

## Agendar para rodar sozinho

- **Windows:** [instalação e Agendador de Tarefas, passo a passo](WINDOWS.md).
- **Mac e Linux:** [tutorial de cron para iniciantes](CRON.md).

Os dois guias explicam como testar, definir horários, consultar os logs e pausar os envios.

O computador precisa estar ligado e acordado no horário, com acesso à internet. Para os envios, o Evolution também precisa estar disponível e conectado ao WhatsApp.

## Arquivos locais e privacidade

Este repositório é uma cópia limpa do código. Não inclui configurações de produção, listas de clientes, telefones, relatórios reais, logs, sessões do WhatsApp ou histórico Git dos projetos de origem.

O `.gitignore` exclui `.env`, ambientes virtuais, logs e saídas geradas. Os relatórios que você gerar na sua máquina conterão os dados das contas acessíveis pelo seu próprio token. Compartilhe apenas com os destinatários que você configurar.

## Testes sem credenciais

Instale as dependências dos relatórios em um ambiente Python e execute, na raiz:

```bash
python -m pip install -r relatorio-diario/requirements.txt
python tests/verificar.py
```

Os testes usam contas e campanhas fictícias e bloqueiam chamadas de rede. Para também verificar a geração de PNG com Chromium:

```bash
python -m playwright install chromium
python tests/verificar.py --render
```

Licença [MIT](LICENSE).
