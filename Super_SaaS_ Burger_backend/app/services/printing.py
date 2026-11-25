import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# =====================================================
# Settings (por tenant) - sem .env (via arquivo JSON)
# =====================================================

def _safe_parse_json(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None
    return None

def _settings_dir() -> str:
    os.makedirs("data", exist_ok=True)
    return "data"


def _settings_path(tenant_id: int) -> str:
    return os.path.join(_settings_dir(), f"print_settings_tenant_{tenant_id}.json")


def get_print_settings(tenant_id: int) -> Dict[str, Any]:
    """
    Retorna as configurações de impressão do tenant.
    Estrutura padrão:
      - auto_print: bool
      - mode: "pdf" | "print"
      - printer_name: str (opcional)
    """
    path = _settings_path(tenant_id)
    if not os.path.exists(path):
        return {
            "auto_print": False,
            "mode": "pdf",
            "printer_name": "",
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        data = {}

    auto_print = data.get("auto_print", data.get("auto_print_enabled", False))
    mode = data.get("mode", data.get("print_mode", "pdf"))
    printer_name = data.get("printer_name", data.get("preferred_printer", ""))

    return {
        "auto_print": bool(auto_print),
        "mode": (mode or "pdf").lower(),
        "printer_name": (printer_name or "").strip(),
    }


def save_print_settings(tenant_id: int, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Salva as configurações de impressão do tenant e retorna o que foi salvo (normalizado).
    """
    auto_print = settings.get("auto_print", settings.get("auto_print_enabled", False))
    mode = settings.get("mode", settings.get("print_mode", "pdf"))
    printer_name = settings.get("printer_name", settings.get("preferred_printer", ""))

    normalized = {
        "auto_print": bool(auto_print),
        "mode": (mode or "pdf").lower(),
        "printer_name": (printer_name or "").strip(),
    }

    path = _settings_path(tenant_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    return normalized


def list_printers_windows() -> List[str]:
    """
    Lista impressoras no Windows.
    Se pywin32 não estiver instalado, retorna uma lista mínima.
    """
    printers: List[str] = []
    try:
        import win32print  # type: ignore
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        for p in win32print.EnumPrinters(flags):
            # p[2] costuma ser o nome
            name = p[2]
            if name and name not in printers:
                printers.append(name)
    except Exception:
        # fallback: pelo menos uma opção padrão
        printers = ["Microsoft Print to PDF"]

    return printers


# =========================
# PDF Ticket (Completo)
# =========================

def _resolve_tenant_id(order, tenant_id: int | None) -> int:
    if tenant_id is not None:
        return tenant_id
    return int(getattr(order, "tenant_id", 0) or 0)


def generate_ticket_pdf(order, tenant_id: int | None = None) -> str:
    """
    Gera um PDF estilo ticket de cozinha/entrega com as informações completas do pedido.
    Retorna o caminho do arquivo PDF gerado.
    """
    if not hasattr(order, "id"):
        raise AttributeError("order precisa ser um objeto Order com atributo id")

    tenant_id = _resolve_tenant_id(order, tenant_id)
    base_dir = os.path.join("tickets", f"tenant_{tenant_id}")
    os.makedirs(base_dir, exist_ok=True)

    file_path = os.path.join(base_dir, f"pedido_{order.id}_tenant_{tenant_id}.pdf")

    with open(file_path, "wb") as output:
        render_ticket_pdf(order, output)
    return file_path


def render_ticket_pdf(order, output) -> None:
    """Render a receipt on 80 mm roll paper with 72 mm of printable width."""
    width = 80 * mm
    margin = 4 * mm
    lines: list[tuple[str, str, int, int, int, str]] = []

    def write_line(
        text: str, gap: int = 12, bold: bool = False, font_size: int = 9,
        indent: int = 0, style: str = "left",
    ):
        font = "Helvetica-Bold" if bold else "Helvetica"
        max_width = width - 2 * margin - indent
        for paragraph in text.splitlines() or [""]:
            for line in simpleSplit(paragraph, font, font_size, max_width) or [""]:
                while stringWidth(line, font, font_size) > max_width:
                    split = 1
                    while stringWidth(line[:split + 1], font, font_size) <= max_width:
                        split += 1
                    lines.append((line[:split], font, font_size, gap, indent, style))
                    line = line[split:]
                lines.append((line, font, font_size, gap, indent, style))

    def divider():
        lines.append(("", "Helvetica", 9, 14, 0, "rule"))

    # helpers para tratar None
    cliente_nome = getattr(order, "cliente_nome", "") or ""
    cliente_tel = getattr(order, "cliente_telefone", "") or ""
    itens = getattr(order, "itens", "") or ""
    items_json = getattr(order, "items_json", "") or ""
    order_items = getattr(order, "order_items", None)
    endereco = getattr(order, "endereco", "") or ""
    obs = getattr(order, "observacao", "") or ""
    tipo = getattr(order, "tipo_entrega", "") or ""
    pagamento = getattr(order, "forma_pagamento", "") or ""
    status = getattr(order, "status", "") or ""
    total_cents = getattr(order, "total_cents", None)
    valor_total = getattr(order, "valor_total", None)

    def format_price_cents(value: int | None) -> str:
        if value is None:
            return ""
        price = value / 100
        return f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    created_at = getattr(order, "created_at", None)
    if created_at:
        try:
            data_str = created_at.strftime("%d/%m/%Y %H:%M")
        except Exception:
            data_str = str(created_at)
    else:
        data_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    order_number = getattr(order, "daily_order_number", None) or order.id
    write_line("PEDIDO", gap=13, bold=True, style="center")
    write_line(f"#{order_number}", gap=31, bold=True, font_size=27, style="center")
    if tipo:
        write_line(tipo.upper(), gap=15, bold=True, font_size=11, style="center")
    write_line(data_str, gap=14, style="center")
    if order_number != order.id:
        write_line(f"ID: {order.id}", style="center")
    divider()

    write_line("ITENS", gap=16, bold=True, font_size=10)
    parsed_items: list[dict] = []
    if isinstance(order_items, list) and order_items:
        for item in order_items:
            parsed_items.append(
                {
                    "name": getattr(item, "name", "") or "",
                    "quantity": getattr(item, "quantity", 0) or 0,
                    "note": getattr(item, "note", "") or "",
                    "subtotal_cents": getattr(item, "subtotal_cents", 0) or 0,
                    "modifiers": _safe_parse_json(getattr(item, "modifiers_json", None)),
                }
            )
    elif items_json:
        try:
            parsed_items = json.loads(items_json) or []
        except Exception:
            parsed_items = []

    if parsed_items:
        for entry in parsed_items:
            name = str(entry.get("name", "") or "")
            qty = entry.get("quantity", 0)
            subtotal = entry.get("subtotal_cents", 0)
            if name and qty:
                write_line(f"{qty}x {name} ({format_price_cents(int(subtotal))})", gap=15, bold=True, font_size=10)
                modifiers = entry.get("modifiers") or []
                if isinstance(modifiers, list):
                    for modifier in modifiers:
                        mod_name = str(modifier.get("name", "") or "").strip()
                        if mod_name:
                            write_line(f"+ {mod_name}", indent=8)
                note = str(entry.get("note") or "").strip()
                if note:
                    write_line(f"Obs. do item: {note}", bold=True, indent=10, style="note")
    else:
        items_list = [i.strip() for i in itens.split(",") if i.strip()] if itens else []
        if not items_list:
            write_line("(nenhum item informado)")
        else:
            for it in items_list:
                write_line(f"• {it}")

    if obs.strip():
        divider()
        write_line("OBSERVAÇÃO DO PEDIDO", bold=True)
        write_line(obs.strip())

    divider()
    write_line("CLIENTE", gap=16, bold=True, font_size=10)
    write_line(f"Nome: {cliente_nome or '(não informado)'}")
    write_line(f"Tel: {cliente_tel or '(não informado)'}")


    if endereco.strip():
        write_line("ENDEREÇO", gap=15, bold=True, font_size=10)
        write_line(endereco.strip())
    reference = str(getattr(order, "reference", "") or "").strip()
    order_type = str(getattr(order, "order_type", "") or tipo).strip().lower()
    if reference and order_type in {"delivery", "entrega"}:
        write_line(f"Instruções de entrega: {reference}", bold=True, indent=10, style="note")

    divider()
    write_line("PAGAMENTO", gap=16, bold=True, font_size=10)
    write_line(pagamento.upper() if pagamento else "(não informado)")
    if total_cents is None and valor_total is not None:
        total_cents = valor_total
    if total_cents is not None and str(total_cents) != "":
        write_line(f"Total  {format_price_cents(int(total_cents))}", gap=21, bold=True, font_size=14)
    write_line(f"Status: {status.upper() if status else '(não informado)'}")

    height = 2 * margin + sum(gap for _, _, _, gap, _, _ in lines)
    c = canvas.Canvas(output, pagesize=(width, height))
    y = height - margin
    c.setLineWidth(.45)
    for line, font, font_size, gap, indent, style in lines:
        if style == "rule":
            c.line(margin, y - gap / 2, width - margin, y - gap / 2)
        else:
            c.setFont(font, font_size)
            if style == "center":
                c.drawCentredString(width / 2, y - font_size, line)
            else:
                if style == "note":
                    c.rect(margin, y - gap, 1.2, gap, stroke=0, fill=1)
                c.drawString(margin + indent, y - font_size, line)
        y -= gap
    c.showPage()
    c.save()


# =========================
# Auto-print (por Config)
# =========================

def _try_print_pdf(pdf_path: str, printer_name: str | None = None) -> bool:
    if os.name != "nt":
        return False
    try:
        import win32api  # type: ignore
        import win32print  # type: ignore
    except Exception:
        return False

    current = None
    try:
        current = win32print.GetDefaultPrinter()
        if printer_name:
            win32print.SetDefaultPrinter(printer_name)
        win32api.ShellExecute(0, "print", pdf_path, None, ".", 0)
        return True
    except Exception:
        return False
    finally:
        try:
            if current and printer_name:
                win32print.SetDefaultPrinter(current)
        except Exception:
            pass


def auto_print_if_possible(
    order,
    tenant_id: int | None = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Decide o que fazer quando um pedido chega/muda status:
    - Se imprimir automático estiver ON:
        - modo 'pdf' => gera PDF
        - modo 'print' => (por enquanto) gera PDF também (fallback)
    Retorna o caminho do PDF gerado (sempre).
    """
    tenant_id = _resolve_tenant_id(order, tenant_id)
    config = config or get_print_settings(tenant_id)

    enabled = bool(config.get("auto_print", config.get("auto_print_enabled", False)))
    mode = (config.get("mode", config.get("print_mode", "pdf")) or "pdf").lower()  # pdf | print
    preferred = (config.get("printer_name", config.get("preferred_printer", "")) or "").strip()

    pdf_path = generate_ticket_pdf(order, tenant_id)

    if not enabled or mode == "pdf":
        return pdf_path

    if mode == "print":
        printed = _try_print_pdf(pdf_path, preferred or None)
        if not printed:
            logger.error(
                "Falha ao imprimir ticket %s (tenant_id=%s, printer_name=%s).",
                pdf_path,
                tenant_id,
                preferred or "default",
            )
        return pdf_path

    return pdf_path
