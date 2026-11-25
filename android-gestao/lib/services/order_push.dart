import 'package:flutter/services.dart';

class OrderPush {
  static const _channel = MethodChannel('fomizero/order_push');

  void onTap(Future<void> Function()? callback) {
    _channel.setMethodCallHandler(callback == null
        ? null
        : (call) async {
            if (call.method == 'notificationTapped') await callback();
          });
  }

  Future<bool> available() async {
    try {
      return await _channel.invokeMethod<bool>('available') ?? false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<Map<String, String>?> current(String account) =>
      _channel.invokeMapMethod<String, String>('current', {'account': account});

  Future<Map<String, String>?> prepare({required bool renew}) =>
      _channel.invokeMapMethod<String, String>(renew ? 'renew' : 'prepare');

  Future<void> activate(String account, Map<String, String> registration) async {
    final stored = await _channel.invokeMethod<bool>('activate', {
      'account': account,
      'registration': registration,
    });
    if (stored != true) throw PlatformException(code: 'registration_storage');
  }

  Future<Map<String, String>?> clear() =>
      _channel.invokeMapMethod<String, String>('clear');

  Future<bool> consumeTap(String account) async =>
      await _channel.invokeMethod<bool>('consumeTap', {'account': account}) ?? false;
}
