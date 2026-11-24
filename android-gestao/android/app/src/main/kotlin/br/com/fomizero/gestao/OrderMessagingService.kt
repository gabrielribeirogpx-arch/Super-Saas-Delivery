package br.com.fomizero.gestao

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

internal const val ORDER_CHANNEL = "incoming_orders"
internal const val OPEN_ORDERS = "br.com.fomizero.gestao.OPEN_ORDERS"
internal val pushLock = Any()

internal fun Context.pushPreferences() = getSharedPreferences("order_notifications", Context.MODE_PRIVATE)

internal fun Context.orderNotificationManager(): NotificationManager {
    val manager = getSystemService(NotificationManager::class.java)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        manager.createNotificationChannel(
            NotificationChannel(ORDER_CHANNEL, "Novos pedidos", NotificationManager.IMPORTANCE_HIGH)
        )
    }
    return manager
}

class OrderMessagingService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        if (message.data["kind"] != "new_order") return
        val binding = message.data["binding"] ?: return
        val event = message.data["event"]?.toIntOrNull()?.takeIf { it > 0 } ?: return
        synchronized(pushLock) {
            val preferences = pushPreferences()
            if (preferences.getString("binding", null) != binding) return
            val manager = orderNotificationManager()
            if (!manager.areNotificationsEnabled()) return
            // Persist recent events so provider retries do not ring the device again.
            val recent = preferences.getString("recent", "").orEmpty().split(',').filter { it.isNotEmpty() }
            val key = event.toString()
            if (key in recent) return
            preferences.edit().putString("recent", (recent + key).takeLast(100).joinToString(",")).commit()
            val intent = Intent(this, MainActivity::class.java).setAction(OPEN_ORDERS)
                .putExtra("binding", binding)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            val tap = PendingIntent.getActivity(this, event, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                Notification.Builder(this, ORDER_CHANNEL)
            } else {
                @Suppress("DEPRECATION")
                Notification.Builder(this).setPriority(Notification.PRIORITY_HIGH)
                    .setDefaults(Notification.DEFAULT_ALL)
            }
            manager.notify(event, builder
                .setSmallIcon(R.drawable.ic_order_notification)
                .setContentTitle("Novo pedido")
                .setContentText("Abra o Fomizero Gestão para acompanhar.")
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setAutoCancel(true)
                .setContentIntent(tap)
                .build())
        }
    }
}
