String? _phone(Object? value) {
  final digits = (value?.toString() ?? '').replaceAll(RegExp(r'\D'), '');
  if (digits.startsWith('55') && (digits.length == 12 || digits.length == 13)) {
    return digits;
  }
  return digits.length == 10 || digits.length == 11 ? '55$digits' : null;
}

String orderCustomerName(Map<String, dynamic> order) {
  for (final key in ['customer_name', 'cliente_nome']) {
    final value = order[key]?.toString().trim();
    if (value != null && value.isNotEmpty) return value;
  }
  return 'Cliente';
}

Uri? orderWhatsAppUrl(Map<String, dynamic> order) {
  final phone = _phone(order['customer_phone']) ?? _phone(order['cliente_telefone']);
  final number = order['daily_order_number'] ?? order['id'];
  if (phone == null || number == null) return null;

  final name = orderCustomerName(order);
  final status = order['status']?.toString().trim().toUpperCase();
  final deliveryType = order['tipo_entrega']?.toString().trim() ?? '';
  final fulfillment = (deliveryType.isEmpty
      ? order['order_type']?.toString().trim() ?? ''
      : deliveryType).toUpperCase();
  final pickup = fulfillment == 'RETIRADA' || fulfillment == 'PICKUP';
  final delivery = fulfillment == 'ENTREGA' || fulfillment == 'DELIVERY';
  final message = switch (status) {
    'RECEBIDO' || 'RECEIVED' || 'PENDING' =>
      'Olá, $name! Recebemos seu pedido #$number! Estamos conferindo os detalhes.',
    'CONFIRMADO' || 'CONFIRMED' =>
      'Olá, $name! Seu pedido #$number foi confirmado! Já vamos organizar o preparo.',
    'EM_PREPARO' || 'PREPARANDO' || 'PREPARING' =>
      'Olá, $name! Seu pedido #$number está em preparo!',
    'PRONTO' || 'READY' || 'READY_FOR_DELIVERY' when pickup =>
      'Olá, $name! Seu pedido #$number está pronto para retirada. Pode passar na loja para buscar.',
    'PRONTO' || 'READY' || 'READY_FOR_DELIVERY' when delivery =>
      'Olá, $name! Seu pedido #$number está pronto e aguardando a saída para entrega.',
    'PRONTO' || 'READY' || 'READY_FOR_DELIVERY' =>
      'Olá, $name! Seu pedido #$number está pronto!',
    'SAIU' || 'SAIU_PARA_ENTREGA' || 'OUT_FOR_DELIVERY' || 'IN_TRANSIT' =>
      'Olá, $name! Seu pedido #$number está a caminho! Se precisar passar alguma orientação para a entrega, responda por aqui.',
    'ENTREGUE' || 'DELIVERED' || 'CONCLUIDO' || 'COMPLETED' when pickup =>
      'Olá, $name! Seu pedido #$number foi retirado. Esperamos que aproveite!',
    'ENTREGUE' || 'DELIVERED' || 'CONCLUIDO' || 'COMPLETED' =>
      'Olá, $name! Seu pedido #$number foi entregue. Esperamos que aproveite! Obrigado por pedir com a gente.',
    'CANCELADO' || 'CANCELLED' || 'CANCELED' =>
      'Olá, $name. Seu pedido #$number foi cancelado. Se tiver dúvidas, fale com a gente por aqui.',
    _ => 'Olá, $name! Entramos em contato sobre o seu pedido #$number.',
  };
  return Uri.https('wa.me', '/$phone', {'text': message});
}
