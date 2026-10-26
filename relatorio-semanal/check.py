"""Cliente Meta Graph e envio de texto com configuracao local."""
import os
import json
import urllib.request
import urllib.parse
import urllib.error

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
TOKEN = cfg.get("META_SYSTEM_USER_TOKEN", "")
VERSION = cfg.get("META_API_VERSION", "v25.0")
GRAPH = f"https://graph.facebook.com/{VERSION}"
BUSINESS_ID = cfg.get("META_BUSINESS_ID", "").strip()
IGNORE = {x.strip().removeprefix("act_") for x in cfg.get("IGNORE_ACCOUNTS", "").split(",") if x.strip()}

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
