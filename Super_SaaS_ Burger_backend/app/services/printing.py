import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


# =====================================================
# Settings (por tenant) - sem .env (via arquivo JSON)
# =====================================================

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

def generate_ticket_pdf(order, tenant_id: int) -> str:
    """
    Gera um PDF estilo ticket de cozinha/entrega com as informações completas do pedido.
    Retorna o caminho do arquivo PDF gerado.
    """

    base_dir = os.path.join("tickets", f"tenant_{tenant_id}")
    os.makedirs(base_dir, exist_ok=True)

    file_path = os.path.join(base_dir, f"pedido_{order.id}_tenant_{tenant_id}.pdf")

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    y = height - 40

    def write_line(text: str = "", gap: int = 18, bold: bool = False, font_size: int = 10):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", font_size)
        c.drawString(40, y, text)
        y -= gap

    # helpers para tratar None
    cliente_nome = getattr(order, "cliente_nome", "") or ""
    cliente_tel = getattr(order, "cliente_telefone", "") or ""
    itens = getattr(order, "itens", "") or ""
    items_json = getattr(order, "items_json", "") or ""
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

    # =========================
    # Layout do Ticket
    # =========================
    write_line("========================================", gap=14)
    write_line(f"PEDIDO #{order.id}", gap=22, bold=True, font_size=14)
    write_line("========================================", gap=22)

    # Cliente
    write_line("CLIENTE", gap=18, bold=True)
    write_line(f"Nome: {cliente_nome}" if cliente_nome else "Nome: (não informado)", gap=18)
    write_line(f"Tel: {cliente_tel}" if cliente_tel else "Tel: (não informado)", gap=22)

    # Entrega/Pagamento
    write_line("DADOS DO PEDIDO", gap=18, bold=True)
    write_line(f"Tipo: {tipo.upper()}" if tipo else "Tipo: (não informado)", gap=18)
    write_line(f"Pagamento: {pagamento.upper()}" if pagamento else "Pagamento: (não informado)", gap=18)
    if total_cents is None and valor_total is not None:
        total_cents = valor_total
    if total_cents is not None and str(total_cents) != "":
        write_line(f"Total: {format_price_cents(int(total_cents))}", gap=22)

    # Endereço
    if endereco.strip():
        write_line("----------------------------------------", gap=14)
        write_line("ENDEREÇO", gap=18, bold=True)
        parts = [p.strip() for p in endereco.split(",")] if "," in endereco else [endereco.strip()]
        for p in parts:
            if p:
                write_line(p, gap=16)
        y -= 6

    # Itens
    write_line("----------------------------------------", gap=14)
    write_line("ITENS", gap=18, bold=True)

    parsed_items: list[dict] = []
    if items_json:
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
                write_line(f"• {qty}x {name} ({format_price_cents(int(subtotal))})", gap=16)
    else:
        items_list = [i.strip() for i in itens.split(",") if i.strip()] if itens else []
        if not items_list:
            write_line("(nenhum item informado)", gap=18)
        else:
            for it in items_list:
                write_line(f"• {it}", gap=16)

    y -= 6

    # Observação
    if obs.strip():
        write_line("----------------------------------------", gap=14)
        write_line("OBSERVAÇÃO", gap=18, bold=True)
        write_line(obs.strip().upper(), gap=20)

    # Rodapé
    write_line("----------------------------------------", gap=18)
    write_line(f"Data: {data_str}", gap=18)
    write_line(f"Status: {status.upper()}" if status else "Status: (não informado)", gap=22, bold=True)
    write_line("========================================", gap=14)

    c.showPage()
    c.save()

    return file_path


# =========================
# Auto-print (por Config)
# =========================

def auto_print_if_possible(order, tenant_id: int, config: Optional[Dict[str, Any]] = None) -> str:
    """
    Decide o que fazer quando um pedido chega/muda status:
    - Se imprimir automático estiver ON:
        - modo 'pdf' => gera PDF
        - modo 'print' => (por enquanto) gera PDF também (fallback)
    Retorna o caminho do PDF gerado (sempre).
    """
    config = config or {}

    enabled = bool(config.get("auto_print", config.get("auto_print_enabled", False)))
    mode = (config.get("mode", config.get("print_mode", "pdf")) or "pdf").lower()  # pdf | print
    _preferred = (config.get("printer_name", config.get("preferred_printer", "")) or "").strip()

    pdf_path = generate_ticket_pdf(order, tenant_id)

    if not enabled:
        return pdf_path

    # Por enquanto, mesmo no modo "print", fazemos fallback para PDF,
    # porque nem sempre existe impressora instalada no PC.
    # Quando você instalar pywin32 e quiser imprimir direto, esse é o ponto de ligar.
    if mode == "print":
        return pdf_path

    return pdf_path
