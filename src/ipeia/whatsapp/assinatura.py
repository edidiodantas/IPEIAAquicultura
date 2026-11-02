"""Verificação da assinatura X-Hub-Signature-256 enviada pela Meta."""

import hashlib
import hmac


def assinatura_valida(corpo: bytes, cabecalho: str | None, app_secret: str) -> bool:
    if not app_secret:
        return True  # desenvolvimento local sem segredo configurado
    if not cabecalho or not cabecalho.startswith("sha256="):
        return False
    esperado = hmac.new(app_secret.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho.removeprefix("sha256="))
