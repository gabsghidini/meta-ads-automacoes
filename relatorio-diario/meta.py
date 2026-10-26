"""meta.py — descobre as contas de cliente e coleta os insights do dia.

Nenhuma lista de clientes e mantida a mao: quem aparece no relatorio e
quem gastou nos ultimos 7 dias. Cliente novo entra sozinho, cliente que
parou sai sozinho.
"""
from __future__ import annotations

import datetime
import json
from concurrent.futures import ThreadPoolExecutor

import config
import metricas

check = config.check

CAMPOS = (
    "campaign_id,campaign_name,objective,spend,impressions,clicks,"
    "actions,cost_per_action_type"
)


def datas(hoje=None):
    """As datas do relatorio: ontem, anteontem e os 7 dias da media."""
    hoje = hoje or datetime.date.today()
    ontem = hoje - datetime.timedelta(days=1)
    anteontem = hoje - datetime.timedelta(days=2)
    media = [(anteontem - datetime.timedelta(days=i)).isoformat() for i in range(7)]
    return {
        "ontem": ontem.isoformat(),
        "anteontem": anteontem.isoformat(),
        "media": media,
        "since": (ontem - datetime.timedelta(days=7)).isoformat(),
        "until": ontem.isoformat(),
    }


def contas():
    """Todas as contas visiveis ao token, menos as ignoradas aqui."""
    todas, origem = check.discover_accounts()
    return [c for c in todas if str(c["id"]) not in config.IGNORE], origem


def insights(conta, since, until):
    """Uma chamada por conta cobrindo os 8 dias, quebrada por dia."""
    node = f"act_{conta['id']}/insights"
    try:
        return check.paginate(
            node,
            {
                "level": "campaign",
                "time_increment": "1",
                "fields": CAMPOS,
                "time_range": json.dumps({"since": since, "until": until}),
                "limit": "500",
            },
        )
    except Exception as e:  # conta sem acesso, desativada, sem historico
        conta["erro"] = str(e)
        return []


def metas_de_otimizacao(conta):
    """campaign_id -> (optimization_goal, custom_event_type, custom_conversion_id).

    O objetivo da campanha nao basta: OUTCOME_LEADS cobre formulario
    nativo, WhatsApp e pixel de site. Quem separa os tres e o conjunto —
    e, no caso de pixel, o evento que ele promove. Conjunto ativo tem
    preferencia, porque e ele que esta gastando hoje.
    """
    try:
        conjuntos = check.paginate(
            f"act_{conta['id']}/adsets",
            {
                "fields": (
                    "campaign_id,optimization_goal,promoted_object,effective_status"
                ),
                "limit": "500",
            },
        )
    except Exception:
        return {}

    votos = {}
    for c in conjuntos:
        cid = c.get("campaign_id")
        goal = c.get("optimization_goal")
        if not cid or not goal:
            continue
        promovido = c.get("promoted_object") or {}
        chave = (
            goal,
            promovido.get("custom_event_type"),
            promovido.get("custom_conversion_id"),
        )
        peso = 2 if c.get("effective_status") == "ACTIVE" else 1
        por_campanha = votos.setdefault(cid, {})
        por_campanha[chave] = por_campanha.get(chave, 0) + peso
    return {cid: max(v, key=v.get) for cid, v in votos.items()}


def coleta(hoje=None, apenas=None, workers=8):
    """Coleta e agrega tudo. Devolve so as contas com gasto na janela."""
    d = datas(hoje)
    todas, origem = contas()
    if apenas:
        alvo = {str(a) for a in apenas}
        todas = [c for c in todas if str(c["id"]) in alvo]

    def uma(conta):
        linhas = insights(conta, d["since"], d["until"])
        metas = metas_de_otimizacao(conta) if linhas else {}
        dados = metricas.agrega_conta(
            linhas, d["ontem"], d["anteontem"], d["media"], metas=metas
        )
        gasto_janela = sum(float(l.get("spend") or 0) for l in linhas)
        return {
            "id": conta["id"],
            "nome": conta.get("name") or conta["id"],
            "currency": conta.get("currency", "BRL"),
            "erro": conta.get("erro"),
            "gasto_janela": gasto_janela,
            **dados,
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        resultado = list(pool.map(uma, todas))

    ativas = [c for c in resultado if c["gasto_janela"] > config.MIN_SPEND_7D]
    ativas.sort(key=lambda c: c["ontem"]["spend"], reverse=True)
    return {"datas": d, "origem": origem, "contas": ativas, "total_vistas": len(todas)}
