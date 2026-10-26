"""Configuracao independente desta automacao; sem arquivos externos."""
import os
import check

DIR = os.path.dirname(os.path.abspath(__file__))
cfg = check.cfg
IGNORE = check.IGNORE
MIN_SPEND_7D = float(cfg.get("MIN_SPEND_7D", "1") or 1)
INSTANCE = cfg.get("WHATSAPP_INSTANCE", "")
RECIPIENTS = [r.strip() for r in cfg.get("RELATORIO_RECIPIENTS", "").replace(";", ",").split(",") if r.strip()]
SAIDA = os.path.join(DIR, "saida")
TEMPLATES = os.path.join(DIR, "templates")
BRAND_NAME = cfg.get("BRAND_NAME", "META ADS")
