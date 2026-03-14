package com.example.aadtool

import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Android Auto Diagnostic Tool – MainActivity
 *
 * Provides a UI for:
 *  1. Entering connection parameters (IP, port, optional extras).
 *  2. Starting a local TCP listener to observe Android Auto connection attempts.
 *  3. Launching the Android Auto WirelessStartupActivity via an explicit Intent.
 */
class MainActivity : Activity() {

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    private lateinit var logManager: LogManager
    private var diagnosticServer: DiagnosticServer? = null

    // Views
    private lateinit var etTargetIp: EditText
    private lateinit var etTargetPort: EditText
    private lateinit var etServiceNetwork: EditText
    private lateinit var etBtDevice: EditText
    private lateinit var etFlags: EditText
    private lateinit var btnStartTest: Button
    private lateinit var btnStopServer: Button
    private lateinit var btnClearLogs: Button
    private lateinit var btnSaveLogs: Button
    private lateinit var tvServerStatus: TextView
    private lateinit var statusDot: View
    private lateinit var tvLog: TextView
    private lateinit var logScrollView: ScrollView

    // Android Auto component under test
    private val aaPackage  = "com.google.android.projection.gearhead"
    private val aaActivity = "com.google.android.projection.gearhead.WirelessStartupActivity"

    // Intent extra keys used by Android Auto wireless pairing
    private val EXTRA_IP_ADDRESS      = "ip_address"
    private val EXTRA_PORT            = "port"
    private val EXTRA_SERVICE_NETWORK = "service_network_name"
    private val EXTRA_BT_DEVICE       = "bluetooth_device_name"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Bind views
        etTargetIp      = findViewById(R.id.etTargetIp)
        etTargetPort    = findViewById(R.id.etTargetPort)
        etServiceNetwork = findViewById(R.id.etServiceNetwork)
        etBtDevice      = findViewById(R.id.etBtDevice)
        etFlags         = findViewById(R.id.etFlags)
        btnStartTest    = findViewById(R.id.btnStartTest)
        btnStopServer   = findViewById(R.id.btnStopServer)
        btnClearLogs    = findViewById(R.id.btnClearLogs)
        btnSaveLogs     = findViewById(R.id.btnSaveLogs)
        tvServerStatus  = findViewById(R.id.tvServerStatus)
        statusDot       = findViewById(R.id.statusDot)
        tvLog           = findViewById(R.id.tvLog)
        logScrollView   = findViewById(R.id.logScrollView)

        logManager = LogManager(this) { lines -> refreshLog(lines) }

        logManager.log("Android Auto Diagnostic Tool started.")
        logManager.log("Target component: $aaPackage")
        logManager.log("Activity: $aaActivity")
        logManager.log("Fill in the parameters below and press [Start Test].")

        btnStartTest.setOnClickListener  { onStartTest() }
        btnStopServer.setOnClickListener { onStopServer() }
        btnClearLogs.setOnClickListener  { logManager.clear() }
        btnSaveLogs.setOnClickListener   { onSaveLogs() }
    }

    // ── Log console ──────────────────────────────────────────────────────────

    private fun refreshLog(lines: List<String>) {
        val text = if (lines.isEmpty()) getString(R.string.log_console_hint)
                   else lines.joinToString("\n")
        tvLog.text = text
        logScrollView.post { logScrollView.fullScroll(View.FOCUS_DOWN) }
    }

    // ── Start Test ───────────────────────────────────────────────────────────

    private fun onStartTest() {
        val ip      = etTargetIp.text.toString().trim()
        val portStr = etTargetPort.text.toString().trim()

        if (ip.isEmpty() || portStr.isEmpty()) {
            Toast.makeText(this, "IP address and port are required.", Toast.LENGTH_SHORT).show()
            return
        }
        val port = portStr.toIntOrNull()
        if (port == null || port !in 1..65535) {
            Toast.makeText(this, "Port must be 1–65535.", Toast.LENGTH_SHORT).show()
            return
        }

        // Start the diagnostic TCP listener before launching the intent so it
        // is ready when Android Auto tries to connect back.
        startDiagnosticServer(port)
        launchAndroidAutoActivity(ip, port)
    }

    // ── Diagnostic server ─────────────────────────────────────────────────────

    private fun startDiagnosticServer(port: Int) {
        diagnosticServer?.stop()
        diagnosticServer = DiagnosticServer(
            port            = port,
            logManager      = logManager,
            scope           = scope,
            onStatusChanged = { running -> updateServerStatus(running) }
        )
        diagnosticServer?.start()
    }

    private fun onStopServer() {
        diagnosticServer?.stop()
        diagnosticServer = null
        updateServerStatus(false)
    }

    private fun updateServerStatus(running: Boolean) {
        tvServerStatus.text = if (running)
            getString(R.string.server_status_running)
        else
            getString(R.string.server_status_stopped)

        val color = if (running) Color.parseColor("#2E7D32") else Color.parseColor("#C62828")
        val dot = GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(color)
        }
        statusDot.background = dot

        btnStartTest.isEnabled  = !running
        btnStopServer.isEnabled = running
    }

    // ── Android Auto intent ───────────────────────────────────────────────────

    private fun launchAndroidAutoActivity(ip: String, port: Int) {
        val serviceNetwork = etServiceNetwork.text.toString().trim()
        val btDevice       = etBtDevice.text.toString().trim()
        val flagsRaw       = etFlags.text.toString().trim()

        logManager.log("Launching Android Auto WirelessStartupActivity…")
        logManager.log("  ip=$ip  port=$port")
        if (serviceNetwork.isNotEmpty()) logManager.log("  service_network=$serviceNetwork")
        if (btDevice.isNotEmpty())       logManager.log("  bt_device=$btDevice")
        if (flagsRaw.isNotEmpty())       logManager.log("  flags=$flagsRaw")

        val intent = Intent().apply {
            component = ComponentName(aaPackage, aaActivity)
            putExtra(EXTRA_IP_ADDRESS, ip)
            putExtra(EXTRA_PORT, port)
            if (serviceNetwork.isNotEmpty()) putExtra(EXTRA_SERVICE_NETWORK, serviceNetwork)
            if (btDevice.isNotEmpty())       putExtra(EXTRA_BT_DEVICE, btDevice)
            // Parse optional free-form flags: "key=value,key2=value2"
            if (flagsRaw.isNotEmpty()) {
                flagsRaw.split(",").forEach { pair ->
                    val kv = pair.trim().split("=", limit = 2)
                    if (kv.size == 2) putExtra(kv[0].trim(), kv[1].trim())
                }
            }
        }

        try {
            startActivity(intent)
            logManager.log("Intent dispatched – watching for incoming connection…")
        } catch (e: Exception) {
            logManager.log("ERROR launching activity: ${e.message}")
            logManager.log("(Is Android Auto installed and is the activity exported?)")
            Toast.makeText(this, "Could not launch Android Auto: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    // ── Save logs ─────────────────────────────────────────────────────────────

    private fun onSaveLogs() {
        val path = logManager.saveToFile()
        if (path != null) {
            logManager.log("Log saved to: $path")
            Toast.makeText(this, "Log saved:\n$path", Toast.LENGTH_LONG).show()
        } else {
            Toast.makeText(this, "Failed to save log.", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        diagnosticServer?.stop()
        scope.cancel()
    }
}
