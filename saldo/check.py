#!/usr/bin/env python3
import os
import sys
import re
import json
import urllib.request
import urllib.parse
import urllib.error
import datetime
from concurrent.futures import ThreadPoolExecutor

DIR = os.path.dirname(os.path.abspath(__file__))

def parse_env_file(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            out[key] = value
    return out

cfg = parse_env_file(os.path.join(DIR, ".env"))
# Variaveis do processo prevalecem sobre o arquivo local.
cfg.update(os.environ)
evolution_config = cfg

TOKEN = os.environ.get("META_SYSTEM_USER_TOKEN") or cfg.get("META_SYSTEM_USER_TOKEN", "")
VERSION = cfg.get("META_API_VERSION", "v25.0")
GRAPH = f"https://graph.facebook.com/{VERSION}"
BUSINESS_ID = cfg.get("META_BUSINESS_ID", "").strip()
PREPAID_URGENT = float(
    cfg.get("PREPAID_URGENT", cfg.get("PREPAID_LOW_WARN", "0") or "0")
)
PREPAID_LOW = float(cfg.get("PREPAID_LOW", "25"))
CARTAO_HIGH = float(cfg.get("CARTAO_HIGH", "1000"))
IGNORE = {str(x).strip() for x in cfg.get("IGNORE_ACCOUNTS", "").split(",") if x.strip()}
ALWAYS_NOTIFY = cfg.get("ALWAYS_NOTIFY", "0") == "1"
NO_WHATSAPP = "--no-wa" in sys.argv
AS_JSON = "--json" in sys.argv

STATUS_LABEL = {
    1: "ATIVA",
    2: "DESATIVADA",
    3: "PENDENTE_PGTO",
    7: "REVISAO_RISCO",
    8: "PENDENTE_LIQUIDACAO",
    9: "PERIODO_GRACA",
    100: "FECHAMENTO_PENDENTE",
    101: "FECHADA",
    201: "ATIVA",
    202: "FECHADA",
}
BLOCKED = {2, 3, 100, 101}


class TokenExpired(Exception):
    pass


def is_token_error(msg="", code=None):
    if code == 190:
        return True
    m = (msg or "").lower()
    return "oauth" in m and (
        "expired" in m
        or "session has expired" in m
        or "invalid access token" in m
        or "has not been authorized" in m
    )

NOW = datetime.datetime.now()
YMD = NOW.strftime("%Y-%m-%d")
STAMP = NOW.strftime("%Y-%m-%d %H:%M")


NO_MINOR = {"JPY", "VND", "KRW", "CLP", "ISK", "HUF", "TWD", "UGX", "RWF", "GNF", "PYG", "IDR", "XAF", "XOF"}


def to_major(value, currency):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if (currency or "").upper() in NO_MINOR:
        return n
    return n / 100.0


def fmt_money(value, currency, signed=False):
    n = to_major(value, currency)
    if n is None:
        return "-"
    sign = "+" if signed and n > 0 else ""
    text = f"{sign}{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {currency}"


def graph(node, params=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    url = f"{GRAPH}/{node}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode()).get("error") or {}
            msg = err.get("message") or f"HTTP {e.code}"
            code = err.get("code")
        except Exception:
            msg = f"HTTP {e.code}"
            code = None
        if is_token_error(msg, code):
            raise TokenExpired(msg) from e
        raise RuntimeError(f"Meta {node}: {msg}") from e
    except Exception as e:
        raise RuntimeError(f"Meta {node}: {e}") from e
    if body.get("error"):
        err = body["error"] or {}
        msg = err.get("message") or str(err)
        if is_token_error(msg, err.get("code")):
            raise TokenExpired(msg)
        raise RuntimeError(f"Meta {node}: {msg}")
    return body


def paginate(node, params=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    items = []
    next_url = None
    while True:
        try:
            if next_url:
                with urllib.request.urlopen(next_url, timeout=30) as r:
                    body = json.loads(r.read().decode())
            else:
                url = f"{GRAPH}/{node}?{urllib.parse.urlencode(params)}"
                with urllib.request.urlopen(url, timeout=30) as r:
                    body = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode()).get("error") or {}
                msg = err.get("message") or f"HTTP {e.code}"
                code = err.get("code")
            except Exception:
                msg = f"HTTP {e.code}"
                code = None
            if is_token_error(msg, code):
                raise TokenExpired(msg) from e
            raise RuntimeError(f"{node}: {msg}") from e
        if body.get("error"):
            err = body["error"] or {}
            msg = err.get("message") or str(err)
            if is_token_error(msg, err.get("code")):
                raise TokenExpired(msg)
            raise RuntimeError(f"{node}: {msg}")
        items.extend(body.get("data") or [])
        next_url = (body.get("paging") or {}).get("next")
        if not next_url:
            break
    return items


def classify_funding(fsd):
    if not fsd:
        return None
    t = str(fsd.get("type", "")).lower()
    display = str(fsd.get("display_string", "")).lower()
    if t in ("20", "funded") or "saldo dispon" in display:
        return "prepago"
    if t in ("1", "credit_card", "creditcard", "card") or any(
        word in display for word in ("mastercard", "visa", "elo", "amex", "cartao", "hipercard")
    ):
        return "cartao"
    return None


def parse_display_amount(display):
    m = re.search(r"\(([^()]*)\)", display or "")
    if not m:
        return None
    inner = m.group(1)
    num = re.search(r"[\d][\d.,]*", inner)
    if not num:
        return None
    s = num.group(0).replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s) * 100
    except ValueError:
        return None


def resolve_recipient(base, key, instance):
    raw = cfg.get("WHATSAPP_RECIPIENT", "").strip()
    if raw:
        return [r.strip() for r in raw.split(",") if r.strip()]
    return []


def send_text(lines):
    base = evolution_config.get("EVOLUTION_API_BASE_URL")
    key = evolution_config.get("EVOLUTION_API_KEY")
    instance = cfg.get("WHATSAPP_INSTANCE", "")
    if not base or not key or not instance:
        return "Configure EVOLUTION_API_BASE_URL, EVOLUTION_API_KEY e WHATSAPP_INSTANCE no .env"
    recipients = resolve_recipient(base, key, instance)
    if not recipients:
        return "destinatario nao configurado (WHATSAPP_RECIPIENT)"

    results = []
    for recipient in recipients:
        number = "".join(ch for ch in recipient if ch.isdigit())
        if len(number) in (10, 11):
            number = "55" + number
        if not number:
            continue
        payload = json.dumps({
            "number": number,
            "text": "\n".join(lines),
            "delay": 1000,
            "linkPreview": False,
        }).encode()
        req = urllib.request.Request(
            f"{base}/message/sendText/{urllib.parse.quote(instance)}",
            data=payload,
            headers={"apikey": key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
            results.append(f"({number}) OK")
        except urllib.error.HTTPError as e:
            results.append(f"({number}) erro {e.code}")
        except Exception as e:
            results.append(f"({number}) erro {e}")
    if results and all(r.endswith("OK") for r in results):
        return "sent"
    return "; ".join(results)


TIER_EMOJI = {"urgente": "🚨", "atencao": "⚠️", "ok": "✅"}
TIER_LABEL = {"urgente": "URGENTE", "atencao": "ATENCAO", "ok": "OK"}


def bal_value(r):
    if r["funding"] == "prepago" and r.get("avail") is not None:
        return r["avail"]
    return r.get("balance", 0.0)


def tier(r):
    if r["error"]:
        return "urgente"
    bal = to_major(bal_value(r), r.get("currency"))
    bal = bal if bal is not None else 0.0
    if r["funding"] == "prepago":
        if bal <= PREPAID_URGENT:
            return "urgente"
        if bal <= PREPAID_LOW:
            return "atencao"
        return "ok"
    if r["funding"] == "cartao":
        if bal >= CARTAO_HIGH:
            return "atencao"
        return "ok"
    if r["status"] != 1 or r["status"] in BLOCKED:
        return "atencao"
    return "ok"


def token_days_left():
    try:
        dt = graph("debug_token", {"input_token": TOKEN})
        exp = (dt.get("data") or {}).get("expires_at")
        if not exp:
            return None
        return (datetime.datetime.fromtimestamp(exp) - NOW).total_seconds() / 86400.0
    except Exception:
        return None


def send_whatsapp(enriched, need_action, to_recharge, token_days=None):
    groups = {"urgente": [], "atencao": [], "ok": 0}
    for r in enriched:
        t = tier(r)
        if t == "ok":
            groups["ok"] += 1
        else:
            flags = next((fl for rr, fl in need_action if rr is r), [])
            bal = fmt_money(bal_value(r), r.get("currency", "-"))
            detail = (r.get("situation") or "?")
            if r["error"]:
                detail = "ERRO/sem acesso"
            groups[t].append(f"{TIER_EMOJI[t]} {r.get('name') or r.get('id')}: {bal} - {detail}")

    lines = ["SALDOS META ADS", STAMP, ""]
    if token_days is not None and 0 < token_days <= 15:
        lines.append(f"🔑 Token expira em {token_days:.0f} dias - renove esta semana!")
        lines.append("")
    for t in ("urgente", "atencao"):
        if groups[t]:
            lines.append(f"{TIER_LABEL[t]} ({len(groups[t])}):")
            lines.extend(groups[t][:20])
            lines.append("")
    lines.append(f"✅ {groups['ok']} contas OK")
    lines.append("")
    lines.append(
        f"{len(enriched)} contas | {len(groups['urgente'])} urgentes | "
        f"{len(groups['atencao'])} atencao | {to_recharge} p/ reabastecer"
    )
    return send_text(lines)


def send_token_expired(e):
    lines = [
        "META SALDO - TOKEN EXPIRADO",
        STAMP,
        "",
        "🚨 O token do Facebook expirou - o cron esta cego.",
        "Atualize META_SYSTEM_USER_TOKEN no .env com um token valido.",
        "",
        f"Erro: {e}",
    ]
    return send_text(lines)


def discover_accounts():
    """Descobre todas as contas de anuncio visiveis ao token.

    Ordem: BM (owned + client) -> me/adaccounts -> debug_token.
    Retorna (contas, origem); contas e uma lista de
    {"id", "name", "currency"} sem duplicatas e sem as de IGNORE.
    """
    accounts = []
    source = ""
    business_id = BUSINESS_ID
    if not business_id:
        try:
            businesses = paginate("me/businesses", {"fields": "id,name", "limit": "10"})
            if businesses:
                business_id = businesses[0].get("id", "")
        except RuntimeError:
            business_id = ""
        if not business_id:
            try:
                me_biz = graph("me", {"fields": "business{id,name}"}).get("business") or {}
                business_id = str(me_biz.get("id", ""))
            except RuntimeError:
                business_id = ""

    if business_id:
        for edge in ("owned_ad_accounts", "client_ad_accounts"):
            try:
                accounts.extend(paginate(f"{business_id}/{edge}", {"fields": "id,name,currency"}))
                if not source:
                    source = f"BM {business_id} ({edge.replace('_', ' ')})"
            except RuntimeError:
                pass

    try:
        user_accounts = paginate("me/adaccounts", {"fields": "id,name,currency"})
        accounts.extend(user_accounts)
        if user_accounts:
            source = (f"{source}; " if source else "") + "me/adaccounts"
    except RuntimeError:
        pass

    if not accounts:
        try:
            dbg = graph("debug_token", {"input_token": TOKEN})
            uid = (dbg.get("data") or {}).get("user_id")
            if uid:
                accounts = paginate(f"{uid}/adaccounts", {"fields": "id,name,currency"})
                source = f"user/{uid}/adaccounts"
        except Exception:
            accounts = []

    if not source and business_id:
        source = f"BM {business_id}"

    seen = set()
    unique = []
    for a in accounts:
        raw_id = str(a.get("id"))
        acc_id = raw_id[4:] if raw_id.startswith("act_") else raw_id
        if acc_id in IGNORE or raw_id in IGNORE:
            continue
        if acc_id in seen:
            continue
        seen.add(acc_id)
        unique.append({"id": acc_id, "name": a.get("name"), "currency": a.get("currency", "-")})
    return unique, source


def main():
    if not TOKEN:
        print("Configure META_SYSTEM_USER_TOKEN no .env", file=sys.stderr)
        sys.exit(2)

    me = graph("me", {"fields": "id,name"})
    token_days = token_days_left()

    unique, source = discover_accounts()

    def enrich(base):
        try:
            raw_id = str(base["id"])
            act_node = raw_id if raw_id.startswith("act_") else f"act_{raw_id}"
            det = graph(
                act_node,
                {
                    "fields": (
                        "account_status,balance,amount_spent,spend_cap,"
                        "funding_source_details,currency"
                    )
                },
            )
            return {
                **base,
                "status": int(det.get("account_status", 0)),
                "balance": float(det.get("balance", 0) or 0),
                "amount_spent": float(det.get("amount_spent", 0) or 0),
                "spend_cap": float(det.get("spend_cap", 0) or 0),
                "funding": classify_funding(det.get("funding_source_details")),
                "funding_display": (det.get("funding_source_details") or {}).get(
                    "display_string", ""
                ),
                "avail": parse_display_amount(
                    (det.get("funding_source_details") or {}).get("display_string", "")
                ),
                "error": None,
            }
        except RuntimeError as e:
            return {
                **base,
                "status": 0,
                "balance": 0.0,
                "amount_spent": 0.0,
                "spend_cap": 0.0,
                "funding": None,
                "funding_display": "",
                "avail": None,
                "error": str(e),
            }

    with ThreadPoolExecutor(max_workers=5) as pool:
        enriched = list(pool.map(enrich, unique))

    def situation_and_flags(r):
        if r["error"]:
            return (f"ERRO: {r['error']}", [{"level": "agir", "label": "SEM ACESSO"}])
        flags = []
        if r["status"] in BLOCKED:
            flags.append(
                {"level": "agir", "label": STATUS_LABEL.get(r["status"], str(r["status"]))}
            )
        if r["status"] == 9:
            flags.append({"level": "agir", "label": "PERIODO_GRACA"})
        if r["funding"] == "prepago":
            if (to_major(bal_value(r), r.get("currency")) or 0) <= PREPAID_URGENT:
                label = "SEM SALDO" if bal_value(r) <= 0 else "Saldo baixo"
                flags.append(
                    {
                        "level": "cobrar",
                        "label": f"{label} - reabastecer",
                    }
                )
                return (f"{label} - reabastecer", flags)
            return ("Saldo restante", flags)
        if r["funding"] == "cartao":
            return ("Fatura (cartao)", flags)
        return ("Saldo/desconhecido", flags)

    need_action = []
    for r in enriched:
        sit, flags = situation_and_flags(r)
        r["situation"] = sit
        if flags:
            need_action.append((r, flags))

    to_recharge = sum(
        1
        for r, fl in need_action
        if any(f["level"] == "cobrar" for f in fl) and r["funding"] == "prepago"
    )
    to_charge = len(need_action)

    F_TYPE = {"prepago": "Pre-pago", "cartao": "Cartao", None: "?"}

    header = [
        f"# Saldo contas de anuncio - {STAMP}",
        "",
        f"Fonte: {source or 'desconhecida'} | Token: {me.get('name')} ({me.get('id')})",
        "",
        f"- **🚨 URGENTE**: pre-paga com saldo ate {PREPAID_URGENT:g} na moeda da conta, ou erro de acesso.",
        "- **⚠️ ATENCAO**: pre-paga quase zerando, fatura de cartao alta ou conta desativada.",
        "- **✅ OK**: conta rodando normal.",
        "- Valores na moeda de cada conta, convertidos das unidades da API.",
        "",
        "| Conta | Tipo | Situacao | Saldo | Gasto total |",
        "|---|---|---|---|---|",
    ]

    def situation(r):
        return r.get("situation", "?")

    counts = {"urgente": 0, "atencao": 0, "ok": 0}
    for r in enriched:
        counts[tier(r)] += 1

    for r in enriched:
        t = tier(r)
        header.append(
            " | ".join(
                [
                    f"{TIER_EMOJI[t]} **{r.get('name') or 'sin nome'}** ({r.get('id')})",
                    F_TYPE.get(r["funding"], "?"),
                    situation(r),
                    fmt_money(bal_value(r), r.get("currency", "-")),
                    fmt_money(r.get("amount_spent", 0), r.get("currency", "-")),
                ]
            )
        )

    header.append("")
    if token_days is not None and 0 < token_days <= 15:
        header.append(f"**🔑 Token expira em {token_days:.0f} dias - renove esta semana!**")
        header.append("")
    header.append(
        f"**Resumo:** {len(enriched)} contas | {counts['urgente']} urgentes | "
        f"{counts['atencao']} atencao | {counts['ok']} ok | {to_recharge} para reabastecer"
    )
    md = "\n".join(header) + "\n"

    history_dir = os.path.join(DIR, "reports", "history")
    os.makedirs(history_dir, exist_ok=True)
    with open(os.path.join(history_dir, f"{YMD}.md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(DIR, "reports", "report.md"), "w", encoding="utf-8") as f:
        f.write(md)

    should_notify = (not NO_WHATSAPP) and (need_action or ALWAYS_NOTIFY)
    wa_result = None
    if should_notify:
        wa_result = send_whatsapp(enriched, need_action, to_recharge, token_days)

    if AS_JSON:
        flags_by_id = {r.get("id"): [f["label"] for f in fl] for r, fl in need_action}
        print(json.dumps({
            "date": YMD,
            "source": source,
            "accounts": [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "currency": r.get("currency"),
                    "status": r.get("status"),
                    "balance": to_major(bal_value(r), r.get("currency")),
                    "avail_balance": to_major(r.get("avail"), r.get("currency")) if r.get("avail") is not None else None,
                    "amount_spent": to_major(r.get("amount_spent", 0), r.get("currency")),
                    "situation": situation(r),
                    "tier": tier(r),
                    "flags": flags_by_id.get(r.get("id"), []),
                }
                for r in enriched
            ],
            "summary": {"total": len(enriched), "urgent": counts["urgente"], "attention": counts["atencao"], "ok": counts["ok"], "to_recharge": to_recharge},
            "whatsapp": wa_result if wa_result else "skipped",
        }, ensure_ascii=False, indent=2))
        return

    print(f"Saldo Meta Ads - {STAMP}")
    print(f"Fonte: {source} | Contas: {len(enriched)}")
    print("")
    for r in enriched:
        t = tier(r)
        ftype = F_TYPE.get(r["funding"], "?")
        flags = next((fl for rr, fl in need_action if rr is r), [])
        mark = f" [{'; '.join(f['label'] for f in flags)}]" if flags else ""
        print(
            f"  {TIER_EMOJI[t]} {situation(r):<22} {ftype:<8} {fmt_money(bal_value(r), r.get('currency', '-')):<18} "
            f"{r.get('name') or r.get('id')} ({r.get('id')}){mark}"
        )
    print("")
    if token_days is not None and 0 < token_days <= 15:
        print(f"  🔑 Token expira em {token_days:.0f} dias - renove esta semana!")
    print(
        f"Total: {len(enriched)} contas | {counts['urgente']} urgentes | "
        f"{counts['atencao']} atencao | {counts['ok']} ok | {to_recharge} para reabastecer"
    )
    print(f"Relatorio: reports/report.md")
    if wa_result:
        print("WhatsApp: notificacao enviada" if wa_result == "sent" else f"WhatsApp: {wa_result}")


if __name__ == "__main__":
    try:
        main()
    except TokenExpired as e:
        msg = ["META SALDO - TOKEN EXPIRADO", STAMP, "", repr(e)]
        if not NO_WHATSAPP:
            res = send_token_expired(e)
            print(f"TOKEN EXPIRADO - WhatsApp: {'enviado' if res == 'sent' else res}")
        if not os.path.exists(os.path.join(DIR, "reports")):
            os.makedirs(os.path.join(DIR, "reports"), exist_ok=True)
        with open(os.path.join(DIR, "reports", "report.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(msg) + "\n")
        sys.stderr.write(f"TOKEN EXPIRADO: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"Falha na checagem: {e}", file=sys.stderr)
        sys.exit(1)