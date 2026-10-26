#!/usr/bin/env python3
"""semanal.py — relatorio semanal de trafego das contas de cliente no WhatsApp.

Roda toda sexta-feira pelo cron (ou sob demanda). Consolida os ultimos 7 dias
fechados (sexta a quinta) e compara diretamente com a semana imediatamente anterior
(os 7 dias anteriores, tambem de sexta a quinta).

  python semanal.py                      envia para RELATORIO_RECIPIENTS
  python semanal.py --dry-run            so gera as imagens em saida/semanal-AAAA-MM-DD
  python semanal.py --conta 1234         filtra por conta(s)
  python semanal.py --destinatario 55... envia so para esse(s) numero(s)
  python semanal.py --data 2026-09-25    finge que hoje e essa data
  python semanal.py --inicio 2026-09-20 --fim 2026-09-27
                                         periodo exato (inclusivo), comparado com
                                         os mesmos N dias imediatamente anteriores
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from markupsafe import Markup

import config
import meta
import metricas
import render
import whatsapp

check = config.check

DIAS_SEMANA_SIGLA = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


LEGENDA = "Olá, tudo bem? Segue o relatório semanal 🚀"


def datas_semana(hoje=None, inicio=None, fim=None):
    """Calcula as duas janelas: periodo atual e periodo anterior de mesmo tamanho.

    Padrao: semana atual fechada (D-7 a D-1) e semana anterior (D-14 a D-8).
    Com inicio/fim: periodo exato pedido (inclusivo) comparado com os N dias
    imediatamente antes dele.
    """
    if inicio or fim:
        if not (inicio and fim):
            raise ValueError("--inicio e --fim precisam vir juntos")
        if fim < inicio:
            raise ValueError("--fim antes de --inicio")
        ini_atual, fim_atual = inicio, fim
        hoje = fim + datetime.timedelta(days=1)
    else:
        hoje = hoje or datetime.date.today()
        fim_atual = hoje - datetime.timedelta(days=1)
        ini_atual = hoje - datetime.timedelta(days=7)
    n = (fim_atual - ini_atual).days + 1
    fim_ant = ini_atual - datetime.timedelta(days=1)
    ini_ant = ini_atual - datetime.timedelta(days=n)

    dias_atual = [(ini_atual + datetime.timedelta(days=i)).isoformat() for i in range(n)]
    dias_ant = [(ini_ant + datetime.timedelta(days=i)).isoformat() for i in range(n)]

    sigla_ini_atual = DIAS_SEMANA_SIGLA[ini_atual.weekday()]
    sigla_fim_atual = DIAS_SEMANA_SIGLA[fim_atual.weekday()]
    sigla_ini_ant = DIAS_SEMANA_SIGLA[ini_ant.weekday()]
    sigla_fim_ant = DIAS_SEMANA_SIGLA[fim_ant.weekday()]

    semana_extenso = (
        f"{ini_atual.day:02d}/{ini_atual.month:02d} a {fim_atual.day:02d}/{fim_atual.month:02d} "
        f"({sigla_ini_atual} a {sigla_fim_atual})"
    )
    semana_anterior_extenso = (
        f"{ini_ant.day:02d}/{ini_ant.month:02d} a {fim_ant.day:02d}/{fim_ant.month:02d} "
        f"({sigla_ini_ant} a {sigla_fim_ant})"
    )

    return {
        "hoje": hoje.isoformat(),
        "dias": n,
        "fim_atual": fim_atual.isoformat(),
        "ini_atual": ini_atual.isoformat(),
        "fim_ant": fim_ant.isoformat(),
        "ini_ant": ini_ant.isoformat(),
        "dias_atual": set(dias_atual),
        "dias_ant": set(dias_ant),
        "since": ini_ant.isoformat(),
        "until": fim_atual.isoformat(),
        "semana_extenso": semana_extenso,
        "semana_anterior_extenso": semana_anterior_extenso,
    }


def coleta_semanal(hoje=None, apenas=None, workers=8, inicio=None, fim=None):
    """Coleta e agrega o comparativo semanal das contas."""
    d = datas_semana(hoje, inicio, fim)
    todas, origem = meta.contas()
    if apenas:
        alvo = {str(a) for a in apenas}
        todas = [c for c in todas if str(c["id"]) in alvo]

    def processa_uma(conta):
        linhas = meta.insights(conta, d["since"], d["until"])
        if not linhas:
            return None
        metas = meta.metas_de_otimizacao(conta) if linhas else {}

        por_campanha = {}
        for l in linhas:
            por_campanha.setdefault(l.get("campaign_id"), []).append(l)

        campanhas = {}
        janelas = {"atual": metricas._vazio(), "anterior": metricas._vazio()}
        tipos = {"atual": {}, "anterior": {}}

        for cid, rows in por_campanha.items():
            acao, tipo = metricas.acao_da_campanha(rows, metas.get(cid))
            camp = {
                "nome": rows[0].get("campaign_name") or "Sem nome",
                "tipo": tipo,
                "acao": acao,
                "atual": metricas._vazio(),
                "anterior": metricas._vazio(),
            }
            for l in rows:
                dt = l.get("date_start")
                pertence = (
                    "atual"
                    if dt in d["dias_atual"]
                    else ("anterior" if dt in d["dias_ant"] else None)
                )
                if not pertence:
                    continue
                metricas._soma(camp[pertence], l, acao)
                metricas._soma(janelas[pertence], l)
                bucket = tipos[pertence].setdefault(
                    tipo, {"spend": 0.0, "resultado": 0.0}
                )
                bucket["spend"] += float(l.get("spend") or 0)
                bucket["resultado"] += metricas.resultado(l, acao)
            campanhas[cid] = camp

        # Determina o tipo principal da conta com base na semana atual (ou anterior se a atual estiver zerada)
        gasto_por_tipo = {}
        for camp in campanhas.values():
            gasto_por_tipo[camp["tipo"]] = (
                gasto_por_tipo.get(camp["tipo"], 0.0) + camp["atual"]["spend"]
            )
        if not gasto_por_tipo or max(gasto_por_tipo.values()) == 0:
            for camp in campanhas.values():
                gasto_por_tipo[camp["tipo"]] = (
                    gasto_por_tipo.get(camp["tipo"], 0.0) + camp["anterior"]["spend"]
                )

        principal = (
            max(gasto_por_tipo, key=gasto_por_tipo.get)
            if gasto_por_tipo
            else "cliques"
        )

        saida = {}
        for j in ("atual", "anterior"):
            b = tipos[j].get(principal, {"spend": 0.0, "resultado": 0.0})
            bloco = dict(janelas[j])
            bloco["resultado"] = b["resultado"]
            saida[j] = metricas.derivadas(bloco, dias=d["dias"], spend_resultado=b["spend"])

        spend_total = saida["atual"]["spend"] + saida["anterior"]["spend"]
        if spend_total < config.MIN_SPEND_7D:
            return None

        rot_res, rot_custo = metricas.rotulos(principal)

        delta_custo_val = (
            metricas.delta(
                saida["atual"]["custo_resultado"],
                saida["anterior"]["custo_resultado"],
            )
            if saida["atual"]["resultado"] and saida["anterior"]["resultado"]
            else None
        )
        delta_ctr_val = metricas.delta(
            saida["atual"]["ctr"], saida["anterior"]["ctr"]
        )
        delta_cpm_val = metricas.delta(
            saida["atual"]["cpm"], saida["anterior"]["cpm"]
        )
        delta_spend_val = metricas.delta(
            saida["atual"]["spend"], saida["anterior"]["spend"]
        )

        # Alertas semanais com diagnostico de causa provavel
        motivos = []
        if saida["atual"]["spend"] == 0 and saida["anterior"]["spend"] > 0:
            motivos.append("campanha pausada / parou de gastar")
        elif saida["atual"]["spend"] > 0 and saida["atual"]["resultado"] == 0:
            motivos.append(
                f"gastou {render.moeda(saida['atual']['spend'])} sem gerar nenhum {rot_res.lower()} (revisar criativo/público)"
            )

        if delta_custo_val and delta_custo_val > 30:
            sigla_custo = rot_custo if rot_custo in ("CPL", "CPA", "CPI", "CPM") else "Custo"
            if delta_ctr_val is not None and delta_ctr_val <= -12 and delta_cpm_val is not None and delta_cpm_val > 35:
                diag = f"{sigla_custo} subiu {delta_custo_val:.0f}% · provável fadiga de criativo (CTR {delta_ctr_val:.0f}%) + leilão mais caro (CPM +{delta_cpm_val:.0f}%)"
            elif delta_ctr_val is not None and delta_ctr_val <= -15:
                diag = f"{sigla_custo} subiu {delta_custo_val:.0f}% · provável fadiga de criativo (CTR caiu {abs(delta_ctr_val):.0f}%)"
            elif delta_cpm_val is not None and delta_cpm_val >= 35:
                diag = f"{sigla_custo} subiu {delta_custo_val:.0f}% · leilão mais concorrido (CPM subiu +{delta_cpm_val:.0f}%)"
            elif delta_spend_val is not None and delta_spend_val > 40:
                diag = f"{sigla_custo} subiu {delta_custo_val:.0f}% · impacto de escala de verba (+{delta_spend_val:.0f}% gasto)"
            else:
                diag = f"{sigla_custo} subiu {delta_custo_val:.0f}% · investigar taxa de conversão / criativos"
            motivos.append(diag)

        # Campanhas que gastaram na semana atual
        maior_spend_camp = max(
            [v["atual"]["spend"] for v in campanhas.values()] or [0]
        )
        campanhas_semana = []
        for v in sorted(
            campanhas.values(),
            key=lambda x: (x["tipo"] == principal, x["atual"]["spend"]),
            reverse=True,
        ):
            if v["atual"]["spend"] <= 0:
                continue
            r, cu = metricas.rotulos(v["tipo"])
            campanhas_semana.append(
                {
                    "nome": v["nome"],
                    "rotulo_resultado": r,
                    "rotulo_custo": cu,
                    "atual": metricas.derivadas(v["atual"], dias=d["dias"]),
                    "fatia": (
                        (v["atual"]["spend"] / maior_spend_camp * 100)
                        if maior_spend_camp
                        else 0
                    ),
                }
            )

        outros_tipos = [
            {
                "rotulo": metricas.rotulos(t)[0],
                "spend": b["spend"],
                "resultado": b["resultado"],
            }
            for t, b in sorted(
                tipos["atual"].items(),
                key=lambda kv: kv[1]["spend"],
                reverse=True,
            )
            if t != principal and b["spend"] > 0
        ]

        return {
            "id": conta["id"],
            "nome": conta.get("name") or conta["id"],
            "tipo": principal,
            "rotulo_resultado": rot_res,
            "rotulo_custo": rot_custo,
            "atual": saida["atual"],
            "anterior": saida["anterior"],
            "delta_spend": metricas.delta(
                saida["atual"]["spend"], saida["anterior"]["spend"]
            ),
            "delta_resultado": metricas.delta(
                saida["atual"]["resultado"], saida["anterior"]["resultado"]
            ),
            "delta_custo": (
                metricas.delta(
                    saida["atual"]["custo_resultado"],
                    saida["anterior"]["custo_resultado"],
                )
                if saida["atual"]["resultado"] and saida["anterior"]["resultado"]
                else None
            ),
            "delta_ctr": metricas.delta(
                saida["atual"]["ctr"], saida["anterior"]["ctr"]
            ),
            "delta_clicks": metricas.delta(
                saida["atual"]["clicks"], saida["anterior"]["clicks"]
            ),
            "motivos": motivos,
            "parada": saida["atual"]["spend"] == 0,
            "campanhas_semana": campanhas_semana,
            "outros_tipos": outros_tipos,
            "slug": render.slug(conta.get("name") or conta["id"]),
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        contas_processadas = [
            r for r in pool.map(processa_uma, todas) if r is not None
        ]

    # Ordena por gasto na semana atual
    contas_processadas.sort(key=lambda c: c["atual"]["spend"], reverse=True)

    # Totais consolidados
    soma = lambda chave, janela: sum(x[janela][chave] for x in contas_processadas)
    spend_atual = soma("spend", "atual")
    res_atual = soma("resultado", "atual")
    spend_res_atual = soma("spend_resultado", "atual")

    spend_ant = soma("spend", "anterior")
    res_ant = soma("resultado", "anterior")
    spend_res_ant = soma("spend_resultado", "anterior")

    custo_atual = (spend_res_atual / res_atual) if res_atual else 0.0
    custo_ant = (spend_res_ant / res_ant) if res_ant else 0.0

    quebra = {}
    for c in contas_processadas:
        b = quebra.setdefault(c["tipo"], {"resultado": 0.0, "contas": 0})
        b["resultado"] += c["atual"]["resultado"]
        b["contas"] += 1

    total = {
        "spend": spend_atual,
        "spend_anterior": spend_ant,
        "resultado": res_atual,
        "resultado_anterior": res_ant,
        "custo_resultado": custo_atual,
        "custo_anterior": custo_ant,
        "delta_spend": metricas.delta(spend_atual, spend_ant),
        "delta_resultado": metricas.delta(res_atual, res_ant),
        "delta_custo": metricas.delta(custo_atual, custo_ant) if res_atual and res_ant else None,
        "quebra": [
            f"{int(round(b['resultado']))} {metricas.rotulos(t)[0].lower()}"
            for t, b in sorted(
                quebra.items(), key=lambda kv: kv[1]["resultado"], reverse=True
            )
        ],
    }

    return {
        "datas": d,
        "origem": origem,
        "contas": contas_processadas,
        "total": total,
        "total_vistas": len(todas),
    }


def seta_kpi(d):
    if d is None:
        return "sem base anterior"
    simbolo = "▲" if d >= 0 else "▼"
    if abs(d) > 999:
        return f"{simbolo} >999% vs sem. anterior"
    return f"{simbolo} {abs(d):.0f}% vs sem. anterior"


def renderiza_semanal(dados, pasta=None):
    """Renderiza resumo_semanal.png e cliente_semanal.png para cada conta."""
    d = dados["datas"]
    pasta = pasta or os.path.join(config.SAIDA, f"semanal-{d['fim_atual']}")
    os.makedirs(pasta, exist_ok=True)
    env = render._env()
    env.filters["seta_kpi"] = seta_kpi

    ctx = {
        "contas": dados["contas"],
        "total": dados["total"],
        "alertas": [
            {"nome": c["nome"], "motivos": c["motivos"]}
            for c in dados["contas"]
            if c["motivos"]
        ],
        "semana_extenso": d["semana_extenso"],
        "semana_anterior_extenso": d["semana_anterior_extenso"],
        "dias": d["dias"],
        "gerado_em": datetime.datetime.now().strftime("%d/%m/%Y às %H:%M"),
    }

    paginas = [
        (
            "resumo",
            render._html(
                env,
                "resumo_semanal.html",
                ctx,
                os.path.join(pasta, "resumo_semanal.html"),
            ),
            os.path.join(pasta, "resumo_semanal.png"),
            LEGENDA,
        )
    ]

    for c in ctx["contas"]:
        base = os.path.join(pasta, f"cliente-{c['slug']}")
        paginas.append(
            (
                c["nome"],
                render._html(
                    env,
                    "cliente_semanal.html",
                    {**ctx, "conta": c},
                    base + ".html",
                ),
                base + ".png",
                LEGENDA,
            )
        )

    render._screenshots([(p[1], p[2]) for p in paginas])
    return [
        {"titulo": t, "png": png, "legenda": leg} for t, _, png, leg in paginas
    ], ctx


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="gera as imagens sem enviar")
    ap.add_argument("--conta", action="append", help="limita a essas contas (repetivel)")
    ap.add_argument(
        "--sem-resumo", action="store_true", help="envia apenas os cards de clientes, sem o resumo geral"
    )
    ap.add_argument(
        "--destinatario", action="append", help="envia so para esses numeros (repetivel)"
    )
    ap.add_argument("--data", help="finge que hoje e essa data (AAAA-MM-DD)")
    ap.add_argument("--inicio", help="inicio de periodo especifico (AAAA-MM-DD), junto com --fim")
    ap.add_argument("--fim", help="fim de periodo especifico, inclusivo (AAAA-MM-DD)")
    args = ap.parse_args()

    if not config.check.TOKEN:
        print("META_SYSTEM_USER_TOKEN ausente (.env)", file=sys.stderr)
        return 2

    hoje = datetime.date.fromisoformat(args.data) if args.data else None
    inicio_p = datetime.date.fromisoformat(args.inicio) if args.inicio else None
    fim_p = datetime.date.fromisoformat(args.fim) if args.fim else None
    if bool(inicio_p) != bool(fim_p):
        ap.error("--inicio e --fim precisam vir juntos")
    if inicio_p and fim_p < inicio_p:
        ap.error("--fim antes de --inicio")
    inicio = time.time()

    dados = None
    tentativas = 3
    for tentativa in range(1, tentativas + 1):
        try:
            dados = coleta_semanal(hoje=hoje, apenas=args.conta, inicio=inicio_p, fim=fim_p)
            break
        except Exception as e:
            if tentativa < tentativas:
                print(
                    f"[aviso] tentativa {tentativa}/{tentativas} da coleta semanal falhou ({e}); aguardando {tentativa * 10}s...",
                    file=sys.stderr,
                )
                time.sleep(tentativa * 10)
            else:
                if not args.dry_run:
                    whatsapp.avisa_falha(f"coleta semanal da Meta falhou: {e}")
                traceback.print_exc()
                return 1

    if not dados["contas"]:
        print("nenhuma conta com gasto na janela semanal — nada a enviar")
        return 0

    try:
        paginas, ctx = renderiza_semanal(dados)
    except Exception as e:
        if not args.dry_run:
            whatsapp.avisa_falha(f"render das imagens semanais falhou: {e}")
        traceback.print_exc()
        return 1

    if args.sem_resumo:
        paginas = [p for p in paginas if p["titulo"] != "resumo"]

    print(
        f"{len(dados['contas'])} contas ativas de {dados['total_vistas']} vistas · "
        f"{len(paginas)} imagens semanais · {time.time() - inicio:.1f}s"
    )
    for p in paginas:
        print("  ", p["png"])

    if args.dry_run:
        print("dry-run: nada enviado via WhatsApp")
        return 0

    try:
        resultados = whatsapp.envia_relatorio(paginas, override=args.destinatario)
    except Exception as e:
        print(f"Falha no envio: {e}", file=sys.stderr)
        return 1
    for linha in resultados:
        print("  ", linha)
    return 1 if any(": erro" in linha for linha in resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
