package br.com.fomizero.gestao

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "br.com.fomizero.gestao/web"
        ).setMethodCallHandler { call, result ->
            if (call.method != "open") {
                result.notImplemented()
                return@setMethodCallHandler
            }

            val url = call.arguments as? String
            val uri = url?.let(Uri::parse)
            val host = uri?.host.orEmpty()
            if (uri == null || uri.scheme != "https" ||
                !host.endsWith(".fomizero.com.br") ||
                uri.userInfo != null || uri.port != -1
            ) {
                result.error("invalid_url", "Endereço do painel inválido.", null)
                return@setMethodCallHandler
            }

            try {
                startActivity(Intent(Intent.ACTION_VIEW, uri))
                result.success(null)
            } catch (_: ActivityNotFoundException) {
                result.error("browser_unavailable", "Navegador indisponível.", null)
            }
        }
    }
}
