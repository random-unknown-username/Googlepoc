package com.example.aadtool

import android.content.Context
import android.os.Build
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Manages in-memory diagnostic logs and persists them to internal/external storage.
 *
 * @param onUpdate callback invoked on the thread that calls [log]/[clear] whenever
 *                 the log list changes.  Callers typically update a TextView here.
 */
class LogManager(
    private val context: Context,
    private val onUpdate: (List<String>) -> Unit
) {
    private val lines = mutableListOf<String>()
    private val tsFormat = SimpleDateFormat("HH:mm:ss.SSS", Locale.US)

    fun log(message: String) {
        val ts = tsFormat.format(Date())
        lines.add("[$ts] $message")
        onUpdate(lines.toList())
    }

    fun clear() {
        lines.clear()
        onUpdate(emptyList())
    }

    /**
     * Saves the current log to a timestamped file.
     * Returns the absolute path of the saved file, or null on failure.
     */
    fun saveToFile(): String? {
        return try {
            val fileTs = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val logDir = context.getExternalFilesDir(null) ?: context.filesDir
            val file = File(logDir, "aad_diagnostic_$fileTs.txt")
            file.writeText(buildString {
                appendLine("Android Auto Diagnostic Tool – Session Log")
                appendLine("Device : ${Build.MANUFACTURER} ${Build.MODEL} (Android ${Build.VERSION.RELEASE})")
                appendLine("Saved  : $fileTs")
                appendLine("─".repeat(60))
                for (line in lines) appendLine(line)
            })
            file.absolutePath
        } catch (e: Exception) {
            log("ERROR saving log: ${e.message}")
            null
        }
    }
}
