"""whatsapp.py — envia as imagens pela Evolution API.

Usa as credenciais do arquivo .env desta pasta;
aqui entra so o que ele nao faz: enviar midia.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import config

check = config.check

INTERVALO = 2.5  # segundos entre mensagens, para nao parecer disparo em massa


def credenciais():
    base = check.evolution_config.get("EVOLUTION_API_BASE_URL")
    key = check.evolution_config.get("EVOLUTION_API_KEY")
    return (base or "").rstrip("/"), key


def numero_limpo(bruto):
    n = "".join(ch for ch in str(bruto) if ch.isdigit())
    if len(n) in (10, 11):
        n = "55" + n
    return n


def destinatarios(override=None):
    if override:
        brutos = override
    elif config.RECIPIENTS:
        brutos = config.RECIPIENTS
    else:
        base, key = credenciais()
        brutos = check.resolve_recipient(base, key, config.INSTANCE)
    return [n for n in (numero_limpo(b) for b in brutos) if n]


def _post(url, payload, key, timeout=60):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"apikey": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def envia_imagem(numero, caminho, legenda, base, key):
    """Evolution v2 aceita os campos de midia na raiz; v1 espera um
    bloco `mediaMessage`. Tentamos v2 e caimos para v1 no 400/404."""
    with open(caminho, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    nome = os.path.basename(caminho)
    url = f"{base}/message/sendMedia/{urllib.parse.quote(config.INSTANCE)}"

    v2 = {
        "number": numero,
        "mediatype": "image",
        "mimetype": "image/png",
        "media": b64,
        "fileName": nome,
        "caption": legenda,
        "delay": 800,
    }
    try:
        _post(url, v2, key)
        return "ok"
    except urllib.error.HTTPError as e:
        if e.code not in (400, 404, 500):
            return f"erro {e.code}"
    except Exception as e:
        return f"erro {e}"

    v1 = {
        "number": numero,
        "options": {"delay": 800, "presence": "composing"},
        "mediaMessage": {
            "mediatype": "image",
            "fileName": nome,
            "caption": legenda,
            "media": b64,
        },
    }
    try:
        _post(url, v1, key)
        return "ok"
    except urllib.error.HTTPError as e:
        return f"erro {e.code}: {e.read().decode()[:160]}"
    except Exception as e:
        return f"erro {e}"


def envia_relatorio(paginas, override=None):
    """Resumo primeiro, depois um envio por cliente, para cada numero."""
    base, key = credenciais()
    if not base or not key or not config.INSTANCE:
        raise RuntimeError("Configure EVOLUTION_API_BASE_URL, EVOLUTION_API_KEY e WHATSAPP_INSTANCE no .env")

    numeros = destinatarios(override)
    if not numeros:
        raise RuntimeError("Configure RELATORIO_RECIPIENTS no .env")

    log = []
    for numero in numeros:
        for i, pag in enumerate(paginas):
            status = envia_imagem(numero, pag["png"], pag["legenda"], base, key)
            log.append(f"{numero} · {pag['titulo']}: {status}")
            if i < len(paginas) - 1:
                time.sleep(INTERVALO)
    return log


def avisa_falha(mensagem):
    """Quando o relatorio nao sai, o silencio e o pior resultado."""
    try:
        return check.send_text(["*Relatorio diario falhou*", "", mensagem])
    except Exception as e:
        return f"falha ao avisar: {e}"
