package br.com.fomizero.gestao

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.graphics.drawable.Icon
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

private const val LEGACY_ORDER_CHANNEL = "incoming_orders"
private const val BELL_ORDER_CHANNEL = "incoming_orders_counter_bell"
internal const val OPEN_ORDERS = "br.com.fomizero.gestao.OPEN_ORDERS"
internal val pushLock = Any()

internal fun Context.pushPreferences() = getSharedPreferences("order_notifications", Context.MODE_PRIVATE)

internal fun Context.orderNotificationManager(): NotificationManager =
    getSystemService(NotificationManager::class.java)

private fun Context.counterBellUri(): Uri = Uri.Builder()
    .scheme(ContentResolver.SCHEME_ANDROID_RESOURCE)
    .authority(packageName)
    .appendPath("raw")
    .appendPath("order_counter_bell")
    .build()

internal fun Context.orderNotificationChannelId(manager: NotificationManager): String {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return LEGACY_ORDER_CHANNEL
    if (manager.getNotificationChannel(BELL_ORDER_CHANNEL) != null) return BELL_ORDER_CHANNEL

    // A channel's sound cannot be changed after creation. Keep the previous channel
    // if its sound or importance was customized rather than resetting those choices.
    val previous = manager.getNotificationChannel(LEGACY_ORDER_CHANNEL)
    if (previous != null && (
        previous.importance != NotificationManager.IMPORTANCE_HIGH ||
        previous.sound != RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION) ||
        (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && previous.hasUserSetSound())
    )) return LEGACY_ORDER_CHANNEL

    val channel = NotificationChannel(BELL_ORDER_CHANNEL, "Novos pedidos · Campainha", NotificationManager.IMPORTANCE_HIGH)
    if (previous != null) {
        previous.vibrationPattern?.let { channel.vibrationPattern = it }
        channel.enableVibration(previous.shouldVibrate())
        channel.enableLights(previous.shouldShowLights())
        channel.lightColor = previous.lightColor
        channel.setShowBadge(previous.canShowBadge())
        channel.lockscreenVisibility = previous.lockscreenVisibility
    }
    channel.setSound(counterBellUri(), AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_NOTIFICATION)
        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
        .build())
    manager.createNotificationChannel(channel)
    return BELL_ORDER_CHANNEL
}

class OrderMessagingService : FirebaseMessagingService() {
    private val brandIcon by lazy { Icon.createWithResource(this, R.mipmap.ic_launcher) }

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
                Notification.Builder(this, orderNotificationChannelId(manager))
            } else {
                @Suppress("DEPRECATION")
                Notification.Builder(this).setPriority(Notification.PRIORITY_HIGH)
                    .setDefaults(Notification.DEFAULT_VIBRATE or Notification.DEFAULT_LIGHTS)
                    .setSound(counterBellUri())
            }
            manager.notify(event, builder
                .setSmallIcon(R.drawable.ic_order_notification)
                .setColor(0xffef1018.toInt())
                .setLargeIcon(brandIcon)
                .setContentTitle("Novo pedido")
                .setContentText("Abra o Fomizero Gestão para acompanhar.")
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setAutoCancel(true)
                .setContentIntent(tap)
                .build())
        }
    }
}
