"""Render a UPI payment QR as bytes for embedding in Discord."""
from __future__ import annotations
import io


def generate_upi_qr(payee: str, amount: float, note: str = "Enforcer party debt") -> bytes | None:
    try:
        import qrcode
    except ImportError:
        return None
    upi_uri = f"upi://pay?pa={payee}&am={amount}&tn={note}"
    img = qrcode.make(upi_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
