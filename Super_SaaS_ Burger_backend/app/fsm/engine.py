import json
import re

from app.fsm import states
from app.models.menu_item import MenuItem


def _format_price_cents(price_cents: int) -> str:
    price = price_cents / 100
    return f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _load_menu_items(db, tenant_id: int) -> list[MenuItem]:
    return (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True))
        .order_by(MenuItem.name.asc())
        .all()
    )


def _format_menu(items: list[MenuItem]) -> str:
    if not items:
        return "Desculpe, o cardápio está indisponível no momento."
    lines = ["🍔 Cardápio:"]
    for idx, item in enumerate(items, start=1):
        lines.append(f"{idx}. {item.name} ({_format_price_cents(item.price_cents)})")
    lines.append("\nResponda com o número e a quantidade (ex: '2x 1' ou '1 2').")
    return "\n".join(lines)


def _parse_item_selection(texto: str) -> tuple[int, int] | None:
    match = re.match(r"^\s*(\d+)\s*x\s*(\d+)\s*$", texto)
    if match:
        qty = int(match.group(1))
        item_num = int(match.group(2))
        return item_num, qty

    match = re.match(r"^\s*(\d+)\s+(\d+)\s*$", texto)
    if match:
        item_num = int(match.group(1))
        qty = int(match.group(2))
        return item_num, qty

    match = re.match(r"^\s*(\d+)\s*$", texto)
    if match:
        item_num = int(match.group(1))
        return item_num, 1

    return None


def _add_item_to_cart(dados: dict, item: MenuItem, qty: int) -> None:
    cart = dados.get("cart")
    if not isinstance(cart, list):
        cart = []

    for entry in cart:
        if entry.get("item_id") == item.id:
            entry["qty"] = int(entry.get("qty", 0)) + qty
            entry["line_total_cents"] = entry["qty"] * entry["price_cents"]
            dados["cart"] = cart
            return

    cart.append(
        {
            "item_id": item.id,
            "name": item.name,
            "qty": qty,
            "price_cents": item.price_cents,
            "line_total_cents": item.price_cents * qty,
        }
    )
    dados["cart"] = cart


def _build_cart_summary(cart: list[dict]) -> tuple[str, int]:
    if not cart:
        return "(sem itens)", 0

    total_cents = 0
    lines = []
    for entry in cart:
        qty = int(entry.get("qty", 0))
        name = entry.get("name", "")
        price_cents = int(entry.get("price_cents", 0))
        line_total_cents = price_cents * qty
        total_cents += line_total_cents
        lines.append(f"{qty}x {name} - {_format_price_cents(line_total_cents)}")
    return "\n".join(lines), total_cents

def iniciar_conversa(conversa, db, tenant_id: int):
    conversa.estado = states.COLETANDO_ITENS
    conversa.dados = json.dumps({})
    menu_text = _format_menu(_load_menu_items(db, tenant_id))
    return f"Olá! 😊\n{menu_text}"

def processar_mensagem(conversa, texto, db, tenant_id: int):
    try:
        dados = json.loads(conversa.dados or "{}")
        if not isinstance(dados, dict):
            dados = {}
    except Exception:
        dados = {}

    estado = conversa.estado

    if estado == states.COLETANDO_ITENS:
        texto_lower = texto.lower()
        if "cardápio" in texto_lower or "cardapio" in texto_lower or "menu" in texto_lower:
            resposta = _format_menu(_load_menu_items(db, tenant_id))
        elif "mais" in texto_lower:
            resposta = _format_menu(_load_menu_items(db, tenant_id))
        elif "finalizar" in texto_lower:
            cart = dados.get("cart")
            if not cart:
                resposta = "Seu carrinho está vazio. Escolha uma opção do cardápio."
            else:
                conversa.estado = states.DEFININDO_ENTREGA
                resposta = "Perfeito! 😊 Será entrega ou retirada?"
        else:
            selection = _parse_item_selection(texto_lower)
            if not selection:
                resposta = "Escolha uma opção válida do cardápio usando o número."
            else:
                item_num, qty = selection
                items = _load_menu_items(db, tenant_id)
                if item_num < 1 or item_num > len(items) or qty < 1:
                    resposta = "Escolha uma opção válida do cardápio usando o número."
                else:
                    item = items[item_num - 1]
                    _add_item_to_cart(dados, item, qty)
                    resposta = (
                        f"Adicionado: {qty}x {item.name}.\n"
                        "Quer mais algo? Responda 'mais' para ver o cardápio ou 'finalizar'."
                    )

    elif estado == states.DEFININDO_ENTREGA:
        texto_lower = texto.lower()
        if "retir" in texto_lower:
            dados["tipo_entrega"] = "RETIRADA"
            conversa.estado = states.COLETANDO_OBSERVACAO
            resposta = "Alguma observação no pedido? Se não, responda: sem observações."
        elif "entreg" in texto_lower:
            dados["tipo_entrega"] = "ENTREGA"
            conversa.estado = states.COLETANDO_ENDERECO
            resposta = "Certo 👍 Qual o endereço completo para entrega?"
        else:
            resposta = "Você prefere entrega ou retirada?"

    elif estado == states.COLETANDO_ENDERECO:
        dados["endereco"] = texto
        conversa.estado = states.COLETANDO_OBSERVACAO
        resposta = "Alguma observação no pedido? Se não, responda: sem observações."

    elif estado == states.COLETANDO_OBSERVACAO:
        dados["observacao"] = texto
        conversa.estado = states.DEFININDO_PAGAMENTO
        resposta = "Qual será a forma de pagamento? Pix, Cartão ou Dinheiro?"

    elif estado == states.DEFININDO_PAGAMENTO:
        texto_lower = texto.lower()
        if "pix" in texto_lower:
            dados["pagamento"] = "PIX"
        elif "cart" in texto_lower:
            dados["pagamento"] = "CARTAO"
        elif "din" in texto_lower:
            dados["pagamento"] = "DINHEIRO"
        else:
            return "Forma de pagamento inválida. Use Pix, Cartão ou Dinheiro."

        cart = dados.get("cart")
        if not isinstance(cart, list):
            cart = []
        resumo, total_cents = _build_cart_summary(cart)
        dados["itens"] = resumo
        dados["total_cents"] = total_cents

        conversa.estado = states.CONFIRMACAO
        resposta = (
            f"🧾 RESUMO DO PEDIDO:\n\n"
            f"Itens:\n{resumo}\n"
            f"Total: {_format_price_cents(total_cents)}\n"
            f"Entrega: {dados.get('tipo_entrega')}\n"
            f"Endereço: {dados.get('endereco', '-')}\n"
            f"Observação: {dados.get('observacao')}\n"
            f"Pagamento: {dados.get('pagamento')}\n\n"
            f"Está tudo correto? (sim / não)"
        )

    elif estado == states.CONFIRMACAO:
        if texto.lower().startswith("s"):
            conversa.estado = states.PEDIDO_CRIADO
            resposta = "Pedido confirmado! 🍔 Já estamos preparando."
        else:
            conversa.estado = states.COLETANDO_ITENS
            dados = {}
            resposta = "Sem problemas 😊 Vamos recomeçar. O que você gostaria de pedir?"

    else:
        resposta = "Erro no atendimento. Vamos recomeçar."
        conversa.estado = states.COLETANDO_ITENS
        dados = {}

    conversa.dados = json.dumps(dados)
    return resposta
