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
  final message = switch (status) {
    'RECEBIDO' || 'RECEIVED' || 'PENDING' =>
      'Olá, $name! Recebemos o seu pedido #$number. Em breve iniciaremos o atendimento.',
    'CONFIRMADO' || 'CONFIRMED' =>
      'Olá, $name! Seu pedido #$number foi confirmado.',
    'EM_PREPARO' || 'PREPARANDO' || 'PREPARING' =>
      'Olá, $name! Seu pedido #$number já está sendo preparado.',
    'PRONTO' || 'READY' || 'READY_FOR_DELIVERY' =>
      'Olá, $name! Seu pedido #$number está pronto.',
    'SAIU' || 'SAIU_PARA_ENTREGA' || 'OUT_FOR_DELIVERY' || 'IN_TRANSIT' =>
      'Olá, $name! Seu pedido #$number saiu para entrega.',
    'ENTREGUE' || 'DELIVERED' || 'CONCLUIDO' || 'COMPLETED' =>
      'Olá, $name! Seu pedido #$number foi entregue. Obrigado pela preferência!',
    'CANCELADO' || 'CANCELLED' || 'CANCELED' =>
      'Olá, $name. Informamos que o pedido #$number foi cancelado.',
    _ => 'Olá, $name! Entramos em contato sobre o seu pedido #$number.',
  };
  return Uri.https('wa.me', '/$phone', {'text': message});
}
