import json
from app.fsm import states

def iniciar_conversa(conversa):
    conversa.estado = states.COLETANDO_ITENS
    conversa.dados = json.dumps({})
    return "Olá! 😊 O que você gostaria de pedir hoje?"

def processar_mensagem(conversa, texto):
    dados = json.loads(conversa.dados)

    estado = conversa.estado

    if estado == states.COLETANDO_ITENS:
        dados["itens"] = texto
        conversa.estado = states.DEFININDO_ENTREGA
        resposta = "Perfeito! 😊 Será entrega ou retirada?"

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

        conversa.estado = states.CONFIRMACAO
        resposta = (
            f"🧾 RESUMO DO PEDIDO:\n\n"
            f"Itens: {dados.get('itens')}\n"
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
