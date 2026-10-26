"""render.py — dados prontos -> HTML (Jinja2) -> PNG (Chromium headless).

Os templates nao calculam nada: recebem a forma final e imprimem.
A imagem sai com 1080px de largura e altura livre, em 2x, que e o que
o WhatsApp mostra bem num celular.
"""
from __future__ import annotations

import datetime
import os
import re
import unicodedata

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

import config
import metricas

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]


def moeda(v):
    v = float(v or 0)
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def inteiro(v):
    return f"{int(round(float(v or 0))):,}".replace(",", ".")


def numero(v):
    return f"{float(v or 0):.1f}".replace(".", ",")


def custo(v):
    """Custo por resultado. Sem resultado o custo nao e zero, e inexistente."""
    return moeda(v) if float(v or 0) > 0 else "—"


def pct(v):
    return f"{float(v or 0):.2f}".replace(".", ",") + "%"


def seta(d):
    """Delta percentual como texto curto. Sem base, diz que nao ha base."""
    if d is None:
        return "sem base de comparação"
    simbolo = "▲" if d >= 0 else "▼"
    # base minuscula produz percentual absurdo (R$ 0,32 -> R$ 95 = 29597%)
    if abs(d) > 999:
        return f"{simbolo} >999%"
    return f"{simbolo} {abs(d):.0f}%"


def seta_curta(d):
    """Mesma seta, mas para coluna estreita: sem base vira travessao."""
    return seta(d) if d is not None else "—"


def classe_custo(d):
    """Em custo, subir e ruim. Usado so nas colunas de custo."""
    if d is None:
        return "neutro"
    return "cai" if d > 0 else "sobe"


def classe_volume(d):
    """Em gasto e resultado, subir e bom."""
    if d is None:
        return "neutro"
    return "sobe" if d >= 0 else "cai"


def slug(texto):
    txt = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    txt = re.sub(r"[^a-zA-Z0-9]+", "-", txt).strip("-").lower()
    return txt or "conta"


def extenso(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]}"


def curto(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day:02d}/{d.month:02d}"


def _env():
    env = Environment(
        loader=FileSystemLoader(config.TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )
    env.filters.update(
        moeda=moeda,
        inteiro=inteiro,
        numero=numero,
        pct=pct,
        custo=custo,
        seta=seta,
        seta_curta=seta_curta,
        classe_custo=classe_custo,
        classe_volume=classe_volume,
    )
    return env


def prepara(dados):
    """Enriquece a coleta com rotulos, deltas e alertas — a forma que os
    templates comem. Aqui mora toda a regra de apresentacao."""
    d = dados["datas"]
    contas = []
    for c in dados["contas"]:
        rot_res, rot_custo = metricas.rotulos(c["tipo"])

        campanhas = []
        maior = max(
            [v["ontem"]["spend"] for v in c["campanhas"].values()] or [0]
        )
        for v in sorted(
            c["campanhas"].values(),
            key=lambda x: (x["tipo"] == c["tipo"], x["ontem"]["spend"]),
            reverse=True,
        ):
            if v["ontem"]["spend"] <= 0:
                continue
            r, cu = metricas.rotulos(v["tipo"])
            campanhas.append(
                {
                    "nome": v["nome"],
                    "rotulo_resultado": r,
                    "rotulo_custo": cu,
                    "ontem": metricas.derivadas(v["ontem"]),
                    "fatia": (v["ontem"]["spend"] / maior * 100) if maior else 0,
                }
            )

        contas.append(
            {
                **c,
                "rotulo_resultado": rot_res,
                "rotulo_custo": rot_custo,
                "campanhas_ontem": campanhas,
                "outros_tipos": [
                    {
                        "rotulo": metricas.rotulos(t)[0],
                        "spend": b["spend"],
                        "resultado": b["resultado"],
                    }
                    for t, b in sorted(
                        c["tipos"]["ontem"].items(),
                        key=lambda kv: kv[1]["spend"],
                        reverse=True,
                    )
                    if t != c["tipo"] and b["spend"] > 0
                ],
                "motivos": metricas.alertas(c),
                "parada": c["ontem"]["spend"] == 0,
                "delta_spend": metricas.delta(
                    c["ontem"]["spend"], c["anteontem"]["spend"]
                ),
                "delta_resultado": metricas.delta(
                    c["ontem"]["resultado"], c["anteontem"]["resultado"]
                ),
                "delta_custo": (
                    metricas.delta(
                        c["ontem"]["custo_resultado"], c["media"]["custo_resultado"]
                    )
                    if c["ontem"]["resultado"]
                    else None
                ),
                "slug": slug(c["nome"]),
            }
        )

    soma = lambda chave, janela: sum(x[janela][chave] for x in contas)
    spend = soma("spend", "ontem")
    res = soma("resultado", "ontem")
    spend_res = soma("spend_resultado", "ontem")
    spend_media = soma("spend_resultado_dia", "media")
    res_media = soma("resultado_dia", "media")

    # o total so faz sentido com a quebra do lado: 15 leads e 2 conversas
    # nao sao "17 resultados" para ninguem que lidera essas contas
    quebra = {}
    for c in contas:
        b = quebra.setdefault(c["tipo"], {"resultado": 0.0, "contas": 0})
        b["resultado"] += c["ontem"]["resultado"]
        b["contas"] += 1

    total = {
        "spend": spend,
        "resultado": res,
        "custo_resultado": (spend_res / res) if res else 0.0,
        "custo_media": (spend_media / res_media) if res_media else 0.0,
        "delta_spend": metricas.delta(spend, soma("spend", "anteontem")),
        "delta_resultado": metricas.delta(res, soma("resultado", "anteontem")),
        "quebra": [
            f"{int(round(b['resultado']))} {metricas.rotulos(t)[0].lower()}"
            for t, b in sorted(
                quebra.items(), key=lambda kv: kv[1]["resultado"], reverse=True
            )
        ],
    }

    return {
        "contas": contas,
        "total": total,
        "alertas": [
            {"nome": c["nome"], "motivos": c["motivos"]} for c in contas if c["motivos"]
        ],
        "dia_extenso": extenso(d["ontem"]),
        "anteontem_curto": curto(d["anteontem"]),
        "gerado_em": datetime.datetime.now().strftime("%d/%m/%Y às %H:%M"),
    }


def _html(env, template, contexto, destino):
    with open(os.path.join(config.TEMPLATES, "estilo.css"), encoding="utf-8") as f:
        css = f.read()
    # o CSS e codigo, nao texto do usuario: sem Markup o autoescape
    # transforma as aspas de font-family e de content:"" em entidades
    html = env.get_template(template).render(css=Markup(css), marca=config.BRAND_NAME, **contexto)
    with open(destino, "w", encoding="utf-8") as f:
        f.write(html)
    return destino


def renderiza(dados, pasta=None):
    """Gera resumo.png + uma imagem por cliente. Devolve a lista de envios
    ja na ordem certa: resumo primeiro."""
    pasta = pasta or os.path.join(config.SAIDA, dados["datas"]["ontem"])
    os.makedirs(pasta, exist_ok=True)
    env = _env()
    ctx = prepara(dados)

    paginas = [
        (
            "resumo",
            _html(env, "resumo.html", ctx, os.path.join(pasta, "resumo.html")),
            os.path.join(pasta, "resumo.png"),
            f"Resumo do dia — {ctx['dia_extenso']} · {len(ctx['contas'])} contas ativas",
        )
    ]
    for c in ctx["contas"]:
        base = os.path.join(pasta, f"cliente-{c['slug']}")
        paginas.append(
            (
                c["nome"],
                _html(
                    env,
                    "cliente.html",
                    {**ctx, "conta": c},
                    base + ".html",
                ),
                base + ".png",
                f"{c['nome']} — {ctx['dia_extenso']}",
            )
        )

    _screenshots([(p[1], p[2]) for p in paginas])
    return [
        {"titulo": t, "png": png, "legenda": leg} for t, _, png, leg in paginas
    ], ctx


def _screenshots(pares):
    """Uma instancia de Chromium para todas as paginas."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(
            viewport={"width": 1080, "height": 200}, device_scale_factor=2
        )
        for html, png in pares:
            pagina.goto("file://" + os.path.abspath(html))
            pagina.wait_for_load_state("networkidle")
            pagina.screenshot(path=png, full_page=True)
        navegador.close()
