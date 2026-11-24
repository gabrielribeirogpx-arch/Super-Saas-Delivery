package br.com.fomizero.gestao

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.UUID

class MainActivity : FlutterActivity() {
    private var channel: MethodChannel? = null
    private var permissionResult: MethodChannel.Result? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "fomizero/order_push")
        channel?.setMethodCallHandler { call, result ->
            val preferences = pushPreferences()
            val account = call.argument<String>("account")
            when (call.method) {
                "available" -> result.success(FirebaseApp.getApps(this).any { it.name == FirebaseApp.DEFAULT_APP_NAME })
                "current" -> result.success(
                    if (account == preferences.getString("account", null)) registration() else null
                )
                "prepare" -> {
                    if (Build.VERSION.SDK_INT >= 33 &&
                        checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
                    ) {
                        permissionResult = result
                        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 91)
                    } else {
                        getRegistration(result, renew = false)
                    }
                }
                "renew" -> getRegistration(result, renew = true)
                "activate" -> {
                    val registration = requireNotNull(call.argument<Map<String, String>>("registration"))
                    synchronized(pushLock) {
                        if (preferences.getString("binding", null) != registration["binding"]) {
                            orderNotificationManager().cancelAll()
                            preferences.edit().remove("recent").apply()
                        }
                        result.success(preferences.edit().putString("account", account)
                            .putString("token", registration["token"])
                            .putString("binding", registration["binding"]).commit())
                    }
                }
                "clear" -> {
                    synchronized(pushLock) {
                        val old = registration()
                        preferences.edit().clear().commit()
                        orderNotificationManager().cancelAll()
                        result.success(old)
                    }
                }
                "consumeTap" -> {
                    val binding = preferences.getString("binding", null)
                    val match = account != null && account == preferences.getString("account", null) &&
                        binding != null && intent?.action == OPEN_ORDERS &&
                        intent?.getStringExtra("binding") == binding
                    intent?.removeExtra("binding")
                    result.success(match)
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun registration(): Map<String, String>? {
        val preferences = pushPreferences()
        val token = preferences.getString("token", null) ?: return null
        val binding = preferences.getString("binding", null) ?: return null
        return mapOf("token" to token, "binding" to binding)
    }

    private fun getRegistration(result: MethodChannel.Result, renew: Boolean) {
        val manager = orderNotificationManager()
        if (!manager.areNotificationsEnabled() ||
            (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(ORDER_CHANNEL)?.importance == 0)
        ) {
            result.error("permission", "Notifications disabled", null)
            return
        }
        val binding = if (renew) registration()?.get("binding") else UUID.randomUUID().toString()
        if (binding == null) {
            result.success(null)
            return
        }
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (task.isSuccessful) {
                result.success(mapOf("token" to task.result, "binding" to binding))
            } else {
                result.error("unavailable", "Push registration unavailable", null)
            }
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 91) {
            val result = permissionResult ?: return
            permissionResult = null
            getRegistration(result, renew = false)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (intent.action == OPEN_ORDERS) channel?.invokeMethod("notificationTapped", null)
    }

    override fun cleanUpFlutterEngine(flutterEngine: FlutterEngine) {
        channel?.setMethodCallHandler(null)
        channel = null
        super.cleanUpFlutterEngine(flutterEngine)
    }
}
