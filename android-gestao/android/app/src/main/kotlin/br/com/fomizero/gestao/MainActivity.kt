package br.com.fomizero.gestao

import android.Manifest
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import com.google.android.gms.tasks.Tasks
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.UUID
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException

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
                        if (FirebaseApp.getApps(this).any { it.name == FirebaseApp.DEFAULT_APP_NAME }) {
                            FirebaseMessaging.getInstance().isAutoInitEnabled = false
                        }
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
            (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(orderNotificationChannelId(manager))?.importance == NotificationManager.IMPORTANCE_NONE)
        ) {
            result.error("permission", "Notifications disabled", null)
            return
        }
        val binding = if (renew) registration()?.get("binding") else UUID.randomUUID().toString()
        if (binding == null) {
            result.success(null)
            return
        }
        val messaging = try {
            FirebaseMessaging.getInstance()
        } catch (_: IllegalStateException) {
            result.error("firebase_config", null, null)
            return
        }
        // Only an explicit opt-in or an existing subscription starts Firebase auto-init.
        messaging.isAutoInitEnabled = true
        requestPushToken(messaging, result, binding, SystemClock.elapsedRealtime() + 45_000L, retry = !renew)
    }

    private fun requestPushToken(
        messaging: FirebaseMessaging,
        result: MethodChannel.Result,
        binding: String,
        deadline: Long,
        retry: Boolean,
    ) {
        val remaining = deadline - SystemClock.elapsedRealtime()
        if (remaining <= 0) {
            result.error("firebase_timeout", null, null)
            return
        }
        Tasks.withTimeout(messaging.token, remaining, TimeUnit.MILLISECONDS).addOnCompleteListener { task ->
            val token = if (task.isSuccessful) task.result else null
            if (!token.isNullOrBlank()) {
                result.success(mapOf("token" to token, "binding" to binding))
                return@addOnCompleteListener
            }

            val error = pushRegistrationError(task.exception)
            if (error == "firebase_unreachable" && retry && deadline - SystemClock.elapsedRealtime() >= 15_000L) {
                Handler(Looper.getMainLooper()).postDelayed({
                    requestPushToken(messaging, result, binding, deadline, retry = false)
                }, 1000)
            } else {
                result.error(error, null, null)
            }
        }
    }

    private fun pushRegistrationError(error: Exception?): String {
        // Firebase errors may contain request data. Match known codes locally
        // and send only our own fixed error codes across the channel.
        for (cause in generateSequence<Throwable>(error) { it.cause }.take(8)) {
            when (cause.message) {
                "MISSING_INSTANCEID_SERVICE" -> return "play_services"
                "FIS_AUTH_ERROR", "AUTHENTICATION_FAILED", "INVALID_SENDER" -> return "firebase_config"
                "SERVICE_NOT_AVAILABLE", "INTERNAL_SERVER_ERROR", "InternalServerError" ->
                    return "firebase_unreachable"
            }
            if (cause is TimeoutException) return "firebase_timeout"
        }
        return "firebase_registration"
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
