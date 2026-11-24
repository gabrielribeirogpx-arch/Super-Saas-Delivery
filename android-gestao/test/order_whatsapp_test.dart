import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/services/order_whatsapp.dart';

void main() {
  test('prefills the status message with the public order number', () {
    final link = orderWhatsAppUrl({
      'id': 1234,
      'daily_order_number': 3,
      'customer_name': 'João & Ana',
      'customer_phone': '(11) 91234-5678',
      'status': 'OUT_FOR_DELIVERY',
    });

    expect(link?.scheme, 'https');
    expect(link?.host, 'wa.me');
    expect(link?.path, '/5511912345678');
    expect(link?.queryParameters['text'], 'Olá, João & Ana! Seu pedido #3 saiu para entrega.');
  });

  test('uses the legacy phone and name when the modern fields are unavailable', () {
    final link = orderWhatsAppUrl({
      'id': 6,
      'customer_phone': '',
      'cliente_telefone': '+55 11 91234-5678',
      'cliente_nome': 'Maria',
      'status': 'ENTREGUE',
    });

    expect(link?.path, '/5511912345678');
    expect(link?.queryParameters['text'], contains('Maria! Seu pedido #6 foi entregue'));
  });

  test('requires a valid phone and avoids inventing an unknown status', () {
    expect(orderWhatsAppUrl({'id': 1, 'customer_phone': '123'}), isNull);
    expect(orderWhatsAppUrl({'customer_phone': '11912345678'}), isNull);
    expect(
      orderWhatsAppUrl({'id': 1, 'customer_phone': '11912345678', 'status': 'UNKNOWN'})
          ?.queryParameters['text'],
      'Olá, Cliente! Entramos em contato sobre o seu pedido #1.',
    );
  });
}
