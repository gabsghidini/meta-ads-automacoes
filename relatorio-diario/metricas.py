# -*- coding: utf-8 -*-
"""metricas.py — traduz insights crus da Meta em numeros de relatorio.

Duas regras seguram tudo aqui:

1. O "resultado" de uma campanha depende do objetivo dela. Lead form conta
   leads, campanha de mensagem conta conversas, campanha de trafego conta
   cliques no link.
2. Resultados de tipos diferentes NUNCA se somam. Uma conta que roda lead
   form e uma campanha de vaga de emprego tem leads de um lado e cliques do
   outro — somar os dois inventa um numero que nao existe em lugar nenhum.
"""
from __future__ import annotations

# acao reportada pela Meta -> tipo de resultado
TIPO_POR_ACAO = {
    "onsite_conversion.lead_grouped": "leads",
    "lead": "leads",
    "leadgen.other": "leads",
    "offsite_conversion.fb_pixel_lead": "leads",
    "purchase": "vendas",
    "omni_purchase": "vendas",
    "offsite_conversion.fb_pixel_purchase": "vendas",
    "offsite_conversion.fb_pixel_view_content": "page_views",
    "onsite_conversion.messaging_conversation_started_7d": "conversas",
    "onsite_conversion.total_messaging_connection": "conversas",
    "link_click": "cliques",
    "landing_page_view": "visitas",
    "omni_landing_page_view": "visitas",
    "onsite_conversion.profile_visit_view": "visitas_perfil",
    "offsite_conversion.fb_pixel_lead": "leads",
    "offsite_conversion.fb_pixel_complete_registration": "cadastros",
    "offsite_conversion.fb_pixel_start_trial": "testes",
    "start_trial_website": "testes",
    "offsite_conversion.fb_pixel_custom": "testes",
    "offsite_conversion.fb_pixel_add_to_cart": "carrinhos",
    "offsite_conversion.fb_pixel_initiate_checkout": "checkouts",
    "offsite_conversion.fb_pixel_contact": "contatos",
    "offsite_conversion.fb_pixel_submit_application": "inscricoes",
    "offsite_conversion.fb_pixel_schedule": "agendamentos",
    "mobile_app_install": "instalacoes",
    "app_install": "instalacoes",
    "video_view": "views",
    "post_engagement": "engajamentos",
}

ROTULOS = {
    "leads": ("Leads", "CPL"),
    "vendas": ("Vendas", "CPA"),
    "conversas": ("Conversas", "Custo por conversa"),
    "cliques": ("Cliques no link", "CPC link"),
    "instalacoes": ("Instalações", "CPI"),
    "views": ("Views", "Custo por view"),
    "engajamentos": ("Engajamentos", "Custo por engajamento"),
    "alcance": ("Impressões", "CPM"),
    "visitas": ("Visitas na página", "Custo por visita"),
    "page_views": ("Page Views", "Custo por Page View"),
    "visitas_perfil": ("Visitas no perfil", "Custo por visita"),
    # nomes do Gerenciador: CompleteRegistration e "Concluir inscrição",
    # SubmitApplication e "Enviar inscrição"
    "cadastros": ("Inscrições concluídas", "Custo por inscrição"),
    "testes": ("Testes iniciados", "Custo por teste"),
    "carrinhos": ("Adições ao carrinho", "Custo por adição"),
    "checkouts": ("Checkouts iniciados", "Custo por checkout"),
    "contatos": ("Contatos", "Custo por contato"),
    "inscricoes": ("Inscrições enviadas", "Custo por inscrição enviada"),
    "agendamentos": ("Agendamentos", "Custo por agendamento"),
    "conversoes": ("Conversões", "Custo por conversão"),
}

# evento de pixel promovido pelo conjunto -> acao que a Meta conta.
# Um so evento, sem alternativa: se o conjunto otimiza para LEAD e o
# pixel nao disparou lead, o resultado do dia e zero. Aceitar outro
# evento no lugar (um COMPLETE_REGISTRATION, por exemplo) inventa um
# resultado que nao aparece no Gerenciador.
EVENTOS = {
    "LEAD": ["offsite_conversion.fb_pixel_lead"],
    "PURCHASE": ["offsite_conversion.fb_pixel_purchase"],
    "CONTENT_VIEW": ["offsite_conversion.fb_pixel_view_content"],
    "COMPLETE_REGISTRATION": ["offsite_conversion.fb_pixel_complete_registration"],
    "START_TRIAL": [
        "offsite_conversion.fb_pixel_custom",
        "offsite_conversion.fb_pixel_start_trial",
        "start_trial_website",
    ],
    "ADD_TO_CART": ["offsite_conversion.fb_pixel_add_to_cart"],
    "INITIATED_CHECKOUT": ["offsite_conversion.fb_pixel_initiate_checkout"],
    "CONTACT": ["offsite_conversion.fb_pixel_contact"],
    "SUBMIT_APPLICATION": ["offsite_conversion.fb_pixel_submit_application"],
    "SCHEDULE": ["offsite_conversion.fb_pixel_schedule"],
}

# meta de otimizacao do conjunto -> acoes aceitas. Esta e a fonte de
# verdade: o objetivo da campanha e generico demais (OUTCOME_LEADS cobre
# formulario nativo, WhatsApp e pixel de site ao mesmo tempo), enquanto o
# optimization_goal diz exatamente pelo que a Meta esta otimizando.
METAS = {
    # formulario nativo: os tres nomes sao sinonimos do mesmo resultado
    "LEAD_GENERATION": ["onsite_conversion.lead_grouped", "leadgen.other", "lead"],
    "QUALITY_LEAD": ["onsite_conversion.lead_grouped", "leadgen.other", "lead"],
    "QUALITY_CALL": ["onsite_conversion.lead_grouped", "leadgen.other", "lead"],
    "CONVERSATIONS": ["onsite_conversion.messaging_conversation_started_7d"],
    "LINK_CLICKS": ["link_click"],
    "LANDING_PAGE_VIEWS": ["omni_landing_page_view", "landing_page_view"],
    "PROFILE_VISIT": ["onsite_conversion.profile_visit_view"],
    "THRUPLAY": ["video_view"],
    "VIDEO_VIEWS": ["video_view"],
    "POST_ENGAGEMENT": ["post_engagement"],
    "APP_INSTALLS": ["mobile_app_install", "app_install"],
    "IMPRESSIONS": [],
    "REACH": [],
    "AD_RECALL_LIFT": [],
}

SEM_CONVERSAO = ("OUTCOME_AWARENESS", "REACH", "BRAND_AWARENESS")

# Fallback para campanhas sem meta de otimizacao disponivel nos conjuntos.
# A meta do conjunto, quando presente, continua tendo prioridade.
OBJETIVOS = {
    "OUTCOME_TRAFFIC": METAS["LINK_CLICKS"],
    "LINK_CLICKS": METAS["LINK_CLICKS"],
    "OUTCOME_LEADS": METAS["LEAD_GENERATION"],
    "LEAD_GENERATION": METAS["LEAD_GENERATION"],
    "MESSAGES": METAS["CONVERSATIONS"],
    "OUTCOME_SALES": ["purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"],
    "CONVERSIONS": ["offsite_conversion.fb_pixel_lead", "purchase"],
    "PRODUCT_CATALOG_SALES": ["purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"],
    "OUTCOME_ENGAGEMENT": METAS["POST_ENGAGEMENT"],
    "POST_ENGAGEMENT": METAS["POST_ENGAGEMENT"],
    "VIDEO_VIEWS": METAS["VIDEO_VIEWS"],
    "OUTCOME_APP_PROMOTION": METAS["APP_INSTALLS"],
    "APP_INSTALLS": METAS["APP_INSTALLS"],
    **{objetivo: [] for objetivo in SEM_CONVERSAO},
}

# abaixo disso, o gasto de ontem nao define o tipo principal da conta
GASTO_MINIMO_ONTEM = 1.0
PADRAO = ["link_click"]

# pseudo-acoes para objetivos que nao reportam conversao
IMPRESSOES = "__impressions__"
CLIQUES = "__clicks__"


def rotulos(tipo):
    """(rotulo do resultado, rotulo do custo) de um tipo de resultado."""
    return ROTULOS.get(tipo, ROTULOS["cliques"])


def _acoes(linha):
    return {
        a.get("action_type"): float(a.get("value") or 0)
        for a in (linha.get("actions") or [])
    }


TIPO_POR_EVENTO = {"START_TRIAL": "testes", "COMPLETE_REGISTRATION": "cadastros"}


def _tipo(acao, evento):
    return TIPO_POR_EVENTO.get(evento) or TIPO_POR_ACAO.get(acao, "conversoes")


def acao_da_campanha(linhas, otimizacao=None):
    """Escolhe UMA acao para a campanha, valida na janela inteira.

    Escolher dia a dia faria a campanha trocar de metrica quando um dia
    vem sem lead — o numero de ontem deixaria de ser comparavel com o de
    anteontem. Por isso a decisao olha os 8 dias de uma vez.

    `otimizacao` e (optimization_goal, custom_event_type,
    custom_conversion_id) do conjunto. Ele manda no objetivo da campanha:
    OUTCOME_LEADS cobre formulario nativo, WhatsApp e pixel de site ao
    mesmo tempo, e so o conjunto diz qual dos tres e.
    """
    objetivo = next((l.get("objective") for l in linhas if l.get("objective")), "")
    goal, evento, conversao = (otimizacao or (None, None, None))

    sem_conversao = False
    if goal == "OFFSITE_CONVERSIONS":
        if conversao:
            # conversao personalizada manda no evento: o conjunto promove
            # COMPLETE_REGISTRATION, mas quem conta e a regra da conversao
            # (a Meta reporta como offsite_conversion.custom.<id>), nao o
            # evento padrao do pixel, que pode valer zero.
            candidatos = ["offsite_conversion.custom.%s" % conversao]
        elif evento in EVENTOS:
            ev = EVENTOS[evento]
            candidatos = ev if isinstance(ev, list) else [ev]
        else:
            candidatos = ["offsite_conversion.fb_pixel_lead", "purchase"]
    elif goal in METAS:
        candidatos = METAS[goal]
        sem_conversao = not candidatos
    else:
        candidatos = OBJETIVOS.get(objetivo, PADRAO)
        sem_conversao = objetivo in SEM_CONVERSAO

    somas = {}
    for linha in linhas:
        for acao, valor in _acoes(linha).items():
            somas[acao] = somas.get(acao, 0) + valor

    for acao in candidatos:
        if somas.get(acao):
            return acao, _tipo(acao, evento)

    if sem_conversao:
        return IMPRESSOES, "alcance"
    if candidatos:
        # a campanha nao converteu na janela inteira. Ela continua sendo
        # do tipo que e: zero e a noticia, e trocar a metrica esconderia
        # exatamente isso.
        acao = candidatos[0]
        return acao, _tipo(acao, evento)
    return CLIQUES, "cliques"


def resultado(linha, acao):
    """Quantos resultados a linha entregou, pela acao fixada da campanha."""
    if acao == IMPRESSOES:
        return float(linha.get("impressions") or 0)
    if acao == CLIQUES:
        return float(linha.get("clicks") or 0)
    return _acoes(linha).get(acao, 0.0)


def _vazio():
    return {"spend": 0.0, "impressions": 0, "clicks": 0, "resultado": 0.0}


def _soma(alvo, linha, acao=None):
    alvo["spend"] += float(linha.get("spend") or 0)
    alvo["impressions"] += int(linha.get("impressions") or 0)
    alvo["clicks"] += int(linha.get("clicks") or 0)
    if acao is not None:
        alvo["resultado"] += resultado(linha, acao)


def derivadas(bloco, dias=1, spend_resultado=None):
    """CTR, CPC, custo por resultado e medias diarias.

    `spend_resultado` e o investimento das campanhas que produzem o tipo
    de resultado principal — e ele que divide o custo por resultado, nao
    o investimento total da conta.
    """
    spend = bloco["spend"]
    imp = bloco["impressions"]
    res = bloco["resultado"]
    base = spend if spend_resultado is None else spend_resultado
    return {
        "spend": spend,
        "spend_resultado": base,
        "impressions": imp,
        "clicks": bloco["clicks"],
        "resultado": res,
        "ctr": (bloco["clicks"] / imp * 100) if imp else 0.0,
        "cpc": (spend / bloco["clicks"]) if bloco["clicks"] else 0.0,
        "cpm": (spend / imp * 1000) if imp else 0.0,
        "custo_resultado": (base / res) if res else 0.0,
        "spend_dia": spend / dias if dias else 0.0,
        "spend_resultado_dia": base / dias if dias else 0.0,
        "resultado_dia": res / dias if dias else 0.0,
    }


def agrega_conta(linhas, ontem, anteontem, dias_media, metas=None):
    """Monta as janelas da conta sem misturar tipos de resultado.

    `dias_media` sao os 7 dias anteriores a ontem, para o comparativo nao
    competir consigo mesmo.
    """
    por_campanha = {}
    for linha in linhas:
        por_campanha.setdefault(linha.get("campaign_id"), []).append(linha)

    campanhas = {}
    janelas = {j: _vazio() for j in ("ontem", "anteontem", "media")}
    # investimento e resultado separados por tipo, em cada janela
    tipos = {j: {} for j in ("ontem", "anteontem", "media")}
    set_media = set(dias_media)

    for cid, rows in por_campanha.items():
        acao, tipo = acao_da_campanha(rows, (metas or {}).get(cid))
        camp = {
            "nome": rows[0].get("campaign_name") or "Sem nome",
            "objetivo": rows[0].get("objective") or "",
            "acao": acao,
            "tipo": tipo,
            "ontem": _vazio(),
            "janela": _vazio(),
        }
        for linha in rows:
            data = linha.get("date_start")
            _soma(camp["janela"], linha, acao)
            if data == ontem:
                _soma(camp["ontem"], linha, acao)

            for nome_janela, pertence in (
                ("ontem", data == ontem),
                ("anteontem", data == anteontem),
                ("media", data in set_media),
            ):
                if not pertence:
                    continue
                _soma(janelas[nome_janela], linha)
                bucket = tipos[nome_janela].setdefault(
                    tipo, {"spend": 0.0, "resultado": 0.0}
                )
                bucket["spend"] += float(linha.get("spend") or 0)
                bucket["resultado"] += resultado(linha, acao)

        campanhas[cid] = camp

    # o tipo principal da conta e o que concentrou investimento ONTEM. A
    # janela de 8 dias so decide se ontem nao gastou de verdade: senao uma
    # conta que trocou de campanha (lead -> inscricao) continua reportada
    # pela campanha pausada, com zero, por uma semana. O piso existe porque
    # centavos de entrega residual de uma campanha parada nao sao troca.
    gasto_por_tipo = {}
    for janela in ("ontem", "janela"):
        gasto_por_tipo = {}
        for camp in campanhas.values():
            gasto_por_tipo[camp["tipo"]] = (
                gasto_por_tipo.get(camp["tipo"], 0.0) + camp[janela]["spend"]
            )
        if sum(gasto_por_tipo.values()) >= GASTO_MINIMO_ONTEM:
            break
    principal = (
        max(gasto_por_tipo, key=gasto_por_tipo.get) if gasto_por_tipo else "cliques"
    )

    saida = {}
    for nome_janela, dias in (("ontem", 1), ("anteontem", 1), ("media", max(len(dias_media), 1))):
        bucket = tipos[nome_janela].get(principal, {"spend": 0.0, "resultado": 0.0})
        bloco = dict(janelas[nome_janela])
        bloco["resultado"] = bucket["resultado"]
        saida[nome_janela] = derivadas(
            bloco, dias=dias, spend_resultado=bucket["spend"]
        )

    saida["campanhas"] = campanhas
    saida["tipo"] = principal
    saida["tipos"] = tipos
    return saida


def delta(agora, antes):
    """Variacao percentual. Sem base, nao inventa numero (None)."""
    if antes in (0, 0.0) or antes is None:
        return None
    return (agora / antes - 1) * 100


def alertas(conta):
    """Alertas de desempenho que merecem revisao."""
    fora = []
    ontem = conta["ontem"]
    media = conta["media"]
    if ontem["spend"] == 0 and media["spend"] > 0:
        fora.append("não gastou ontem")
    elif ontem["spend"] > 0 and ontem["resultado"] == 0:
        fora.append("gastou sem resultado")
    if (
        ontem["custo_resultado"]
        and media["custo_resultado"]
        and ontem["custo_resultado"] > media["custo_resultado"] * 1.5
    ):
        fora.append("custo por resultado disparou")
    return fora
