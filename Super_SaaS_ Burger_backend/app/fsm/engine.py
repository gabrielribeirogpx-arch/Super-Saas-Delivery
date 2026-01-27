import json
import re

from app.fsm import states
from app.models.menu_item import MenuItem
from app.models.menu_item_modifier_group import MenuItemModifierGroup
from app.models.modifier import Modifier
from app.services.menu_search import (
    normalize,
    parse_order_text,
    search_menu_items,
    search_menu_items_in_candidates,
)


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


def _modifiers_key(modifiers: list[dict]) -> tuple:
    normalized = []
    for mod in modifiers:
        name = normalize(str(mod.get("name", "") or ""))
        price = int(mod.get("price_cents", 0) or 0)
        if name:
            normalized.append((name, price))
    return tuple(sorted(normalized))


def _add_item_to_cart(
    dados: dict,
    item: MenuItem,
    qty: int,
    modifiers: list[dict] | None = None,
) -> None:
    cart = dados.get("cart")
    if not isinstance(cart, list):
        cart = []

    modifiers = modifiers or []
    modifiers_total_cents = sum(int(mod.get("price_cents", 0) or 0) for mod in modifiers)
    modifiers_signature = _modifiers_key(modifiers)

    for entry in cart:
        if entry.get("item_id") == item.id and _modifiers_key(entry.get("modifiers", [])) == modifiers_signature:
            entry["qty"] = int(entry.get("qty", 0)) + qty
            entry["modifiers_total_cents"] = modifiers_total_cents
            entry["line_total_cents"] = entry["qty"] * (entry["price_cents"] + modifiers_total_cents)
            dados["cart"] = cart
            return

    cart.append(
        {
            "item_id": item.id,
            "name": item.name,
            "qty": qty,
            "price_cents": item.price_cents,
            "modifiers": modifiers,
            "modifiers_total_cents": modifiers_total_cents,
            "line_total_cents": (item.price_cents + modifiers_total_cents) * qty,
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
        modifiers = entry.get("modifiers") or []
        modifiers_total_cents = int(entry.get("modifiers_total_cents", 0) or 0)
        line_total_cents = (price_cents + modifiers_total_cents) * qty
        total_cents += line_total_cents
        suffix = ""
        if isinstance(modifiers, list):
            names = [str(mod.get("name", "") or "").strip() for mod in modifiers if mod.get("name")]
            if names:
                suffix = f" ({', '.join(names)})"
        lines.append(f"- {qty}x {name}{suffix}")
    return "\n".join(lines), total_cents

def iniciar_conversa(conversa, db, tenant_id: int):
    conversa.estado = states.COLETANDO_ITENS
    conversa.dados = json.dumps({})
    return "Olá! 😊\nO que você gostaria hoje?"


def _clear_pending_selection(dados: dict) -> None:
    dados.pop("pending_options", None)
    dados.pop("pending_query", None)


def _build_disambiguation_message(options: list[dict]) -> str:
    lines = ["Encontrei opções parecidas:"]
    for idx, option in enumerate(options, start=1):
        lines.append(f"({idx}) {option['name']}")
    lines.append("Qual você quis? Pode responder com o número ou o nome.")
    return " ".join(lines)


def _is_strong_unique_match(
    query: str, results: list[tuple[MenuItem, float]], score_threshold: float, min_gap: float
) -> bool:
    if not results:
        return False

    normalized_query = normalize(query)
    if not normalized_query:
        return False

    exact_matches = [
        item for item, _score in results if normalize(item.name) == normalized_query
    ]
    if len(exact_matches) == 1:
        return True

    top_score = results[0][1]
    second_score = results[1][1] if len(results) > 1 else 0
    if top_score < score_threshold:
        return False
    if len(results) == 1:
        return True
    return (top_score - second_score) >= min_gap


def _load_modifiers_for_item(db, tenant_id: int, item_id: int) -> list[Modifier]:
    group_ids = (
        db.query(MenuItemModifierGroup.modifier_group_id)
        .filter(
            MenuItemModifierGroup.tenant_id == tenant_id,
            MenuItemModifierGroup.menu_item_id == item_id,
        )
        .all()
    )
    ids = [gid for (gid,) in group_ids]
    if not ids:
        return []
    return (
        db.query(Modifier)
        .filter(Modifier.tenant_id == tenant_id, Modifier.group_id.in_(ids))
        .all()
    )


def _load_modifiers_for_tenant(db, tenant_id: int) -> list[Modifier]:
    return db.query(Modifier).filter(Modifier.tenant_id == tenant_id).all()


def _find_modifiers_in_text(text: str, modifiers: list[Modifier]) -> list[Modifier]:
    normalized_text = normalize(text)
    if not normalized_text:
        return []
    matches: list[Modifier] = []
    for modifier in modifiers:
        mod_name = normalize(modifier.name)
        if mod_name and mod_name in normalized_text:
            matches.append(modifier)
    return matches


def _split_item_and_modifiers(raw_name: str) -> tuple[str, str | None]:
    lowered = raw_name.lower()
    match = re.search(r"\\bcom\\b|\\bc/\\b", lowered)
    if match:
        item_part = raw_name[: match.start()].strip()
        modifiers_part = raw_name[match.end() :].strip()
        return item_part or raw_name, modifiers_part or None
    return raw_name, None

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
        pending_modifier = dados.get("pending_modifier")
        pending_options = dados.get("pending_options")
        if pending_modifier:
            item_id = pending_modifier.get("item_id")
            qty = int(pending_modifier.get("qty", 1) or 1)
            allowed_modifiers = pending_modifier.get("allowed_modifiers") or []
            item = (
                db.query(MenuItem)
                .filter(MenuItem.tenant_id == tenant_id, MenuItem.id == item_id)
                .first()
            )
            if not item:
                dados.pop("pending_modifier", None)
                resposta = "Não encontrei o item do seu pedido. Pode me dizer novamente?"
            else:
                if "sem" in texto_lower or texto_lower.strip() in {"nao", "não"}:
                    _add_item_to_cart(dados, item, qty)
                    dados.pop("pending_modifier", None)
                    resposta = f"Perfeito! Adicionei {qty}x {item.name} sem adicionais. Quer mais alguma coisa?"
                else:
                    allowed_matches = _find_modifiers_in_text(
                        texto,
                        [
                            Modifier(
                                id=mod.get("id"),
                                tenant_id=tenant_id,
                                group_id=mod.get("group_id"),
                                name=mod.get("name"),
                                price_cents=mod.get("price_cents", 0),
                            )
                            for mod in allowed_modifiers
                        ],
                    )
                    selected_modifiers = [
                        {
                            "id": mod.id,
                            "name": mod.name,
                            "price_cents": mod.price_cents,
                        }
                        for mod in allowed_matches
                    ]
                    if not selected_modifiers:
                        allowed_names = [mod.get("name") for mod in allowed_modifiers if mod.get("name")]
                        if allowed_names:
                            resposta = (
                                "Para esse item eu tenho estes adicionais: "
                                f"{', '.join(allowed_names)}. Quer algum deles ou prefere sem adicionais?"
                            )
                        else:
                            resposta = "Esse item não tem adicionais disponíveis. Posso seguir sem adicionais?"
                    else:
                        _add_item_to_cart(dados, item, qty, selected_modifiers)
                        dados.pop("pending_modifier", None)
                        nomes = ", ".join(mod["name"] for mod in selected_modifiers)
                        resposta = (
                            f"Perfeito! Adicionei {qty}x {item.name} com {nomes}. Quer mais alguma coisa?"
                        )
        elif pending_options:
            match = re.match(r"^\s*(\d+)\s*$", texto_lower)
            options = _load_menu_items(db, tenant_id)
            pending_ids = [opt.get("item_id") for opt in pending_options]
            selected_items = [item for item in options if item.id in pending_ids]
            if match:
                idx = int(match.group(1)) - 1
                if idx < 0 or idx >= len(pending_options):
                    resposta = "Opção inválida. Pode escolher o número correto?"
                else:
                    choice = pending_options[idx]
                    item = next((it for it in selected_items if it.id == choice["item_id"]), None)
                    if not item:
                        resposta = "Não encontrei essa opção. Pode tentar de novo?"
                    else:
                        _add_item_to_cart(dados, item, choice["qty"])
                        _clear_pending_selection(dados)
                        resposta = f"Perfeito! Adicionei {choice['qty']}x {item.name}. Quer mais alguma coisa?"
            else:
                resultados = search_menu_items_in_candidates(
                    selected_items, texto, limit=len(selected_items)
                )
                if resultados and _is_strong_unique_match(
                    texto, resultados, score_threshold=0.85, min_gap=0.08
                ):
                    top_item = resultados[0][0]
                    choice = next(
                        (opt for opt in pending_options if opt["item_id"] == top_item.id),
                        None,
                    )
                    if not choice:
                        resposta = "Não encontrei essa opção. Pode tentar de novo?"
                    else:
                        _add_item_to_cart(dados, top_item, choice["qty"])
                        _clear_pending_selection(dados)
                        resposta = (
                            f"Perfeito! Adicionei {choice['qty']}x {top_item.name}. "
                            "Quer mais alguma coisa?"
                        )
                else:
                    resposta = "Pode me dizer o número da opção?"
        elif "finalizar" in texto_lower or texto_lower.strip() in {"nao", "não", "só isso", "so isso"}:
            cart = dados.get("cart")
            if not cart:
                resposta = "Seu carrinho está vazio. Me diga o que você gostaria de pedir."
            else:
                conversa.estado = states.DEFININDO_ENTREGA
                resposta = "Perfeito! 😊 Será entrega ou retirada?"
        elif "cardápio" in texto_lower or "cardapio" in texto_lower or "menu" in texto_lower:
            resposta = "Claro! Me diga o que você gostaria de pedir."
        else:
            candidatos = parse_order_text(texto)
            if not candidatos:
                resposta = "Não entendi o pedido. Pode me dizer o que você gostaria?"
            else:
                adicionados: list[str] = []
                missing: list[str] = []
                ambiguous = None
                tenant_modifiers = _load_modifiers_for_tenant(db, tenant_id)
                for candidato in candidatos:
                    raw_name = candidato["raw_name"]
                    qty = int(candidato.get("qty", 1))
                    item_query, modifiers_text = _split_item_and_modifiers(raw_name)
                    resultados = search_menu_items(db, tenant_id, item_query, limit=3)
                    if not resultados:
                        missing.append(raw_name)
                        continue

                    if _is_strong_unique_match(
                        item_query, resultados, score_threshold=0.88, min_gap=0.1
                    ):
                        top_item = resultados[0][0]
                        allowed_modifiers = _load_modifiers_for_item(db, tenant_id, top_item.id)
                        allowed_ids = {mod.id for mod in allowed_modifiers}
                        selected_modifiers: list[dict] = []
                        invalid_modifiers: list[Modifier] = []
                        if modifiers_text:
                            mentioned = _find_modifiers_in_text(modifiers_text, tenant_modifiers)
                            for mod in mentioned:
                                if mod.id in allowed_ids:
                                    selected_modifiers.append(
                                        {
                                            "id": mod.id,
                                            "name": mod.name,
                                            "price_cents": mod.price_cents,
                                        }
                                    )
                                else:
                                    invalid_modifiers.append(mod)
                        if invalid_modifiers:
                            invalid_names = ", ".join(mod.name for mod in invalid_modifiers)
                            allowed_names = [mod.name for mod in allowed_modifiers]
                            dados["pending_modifier"] = {
                                "item_id": top_item.id,
                                "qty": qty,
                                "allowed_modifiers": [
                                    {
                                        "id": mod.id,
                                        "group_id": mod.group_id,
                                        "name": mod.name,
                                        "price_cents": mod.price_cents,
                                    }
                                    for mod in allowed_modifiers
                                ],
                            }
                            if allowed_names:
                                resposta = (
                                    f"Para {top_item.name}, não tenho {invalid_names}. "
                                    f"Posso adicionar {', '.join(allowed_names)} ou seguir sem adicionais. "
                                    "Como prefere?"
                                )
                            else:
                                resposta = (
                                    f"Para {top_item.name}, não tenho {invalid_names}. "
                                    "Esse item não tem adicionais cadastrados. Posso seguir sem adicionais?"
                                )
                            break
                        _add_item_to_cart(dados, top_item, qty, selected_modifiers)
                        if selected_modifiers:
                            nomes = ", ".join(mod["name"] for mod in selected_modifiers)
                            adicionados.append(f"{qty}x {top_item.name} com {nomes}")
                        else:
                            adicionados.append(f"{qty}x {top_item.name}")
                    else:
                        ambiguous = {
                            "query": item_query,
                            "options": [
                                {"item_id": item.id, "name": item.name, "qty": qty}
                                for item, _score in resultados
                            ],
                        }
                        break

                if ambiguous:
                    dados["pending_options"] = ambiguous["options"]
                    dados["pending_query"] = ambiguous["query"]
                    resposta = _build_disambiguation_message(ambiguous["options"])
                elif missing and not adicionados:
                    resposta = (
                        "Não achei esse item no nosso cardápio. "
                        "Pode me dizer de outro jeito ou escolher algo parecido?"
                    )
                else:
                    mensagem_itens = ""
                    if adicionados:
                        mensagem_itens = f"Adicionei {', '.join(adicionados)}. "
                    if missing:
                        mensagem_itens += (
                            "Não achei alguns itens. Pode me dizer de outro jeito ou escolher algo parecido? "
                        )
                    resposta = f"{mensagem_itens}Quer mais alguma coisa?"

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
            "Perfeito! Seu pedido ficou:\n"
            f"{resumo}\n"
            f"Total: {_format_price_cents(total_cents)}\n"
            "Confirma?"
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
