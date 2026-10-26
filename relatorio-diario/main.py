#!/usr/bin/env python3
"""main.py — relatorio diario de trafego das contas de cliente no WhatsApp.

Roda todo dia as 8h pelo cron. Descobre as contas sozinho, coleta ontem
e os 7 dias anteriores, renderiza as imagens e envia.

  python main.py                      envia para RELATORIO_RECIPIENTS
  python main.py --dry-run            so gera as imagens em saida/
  python main.py --conta 1234 --dry-run   uma conta so, para iterar design
  python main.py --destinatario 5551...   envia so para esse numero
"""
from __future__ import annotations

import argparse
import datetime
import sys
import time
import traceback


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="gera as imagens sem enviar")
    ap.add_argument("--conta", action="append", help="limita a essas contas (repetivel)")
    ap.add_argument(
        "--destinatario", action="append", help="envia so para esses numeros (repetivel)"
    )
    ap.add_argument("--data", help="finge que hoje e essa data (AAAA-MM-DD)")
    args = ap.parse_args()

    import config  # noqa: F401  (configuracao local)
    import meta
    import render
    import whatsapp

    if not config.check.TOKEN:
        print("META_SYSTEM_USER_TOKEN ausente (.env)", file=sys.stderr)
        return 2

    hoje = datetime.date.fromisoformat(args.data) if args.data else None
    inicio = time.time()

    dados = None
    tentativas = 3
    for tentativa in range(1, tentativas + 1):
        try:
            dados = meta.coleta(hoje=hoje, apenas=args.conta)
            break
        except Exception as e:
            if tentativa < tentativas:
                print(
                    f"[aviso] tentativa {tentativa}/{tentativas} da coleta falhou ({e}); aguardando {tentativa * 10}s...",
                    file=sys.stderr,
                )
                time.sleep(tentativa * 10)
            else:
                if not args.dry_run:
                    whatsapp.avisa_falha(f"coleta da Meta falhou: {e}")
                traceback.print_exc()
                return 1

    if not dados["contas"]:
        print("nenhuma conta com gasto na janela de 7 dias — nada a enviar")
        return 0

    try:
        paginas, ctx = render.renderiza(dados)
    except Exception as e:
        if not args.dry_run:
            whatsapp.avisa_falha(f"render das imagens falhou: {e}")
        traceback.print_exc()
        return 1

    print(
        f"{len(dados['contas'])} contas ativas de {dados['total_vistas']} vistas · "
        f"{len(paginas)} imagens · {time.time() - inicio:.1f}s"
    )
    for p in paginas:
        print("  ", p["png"])

    if args.dry_run:
        print("dry-run: nada enviado")
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
