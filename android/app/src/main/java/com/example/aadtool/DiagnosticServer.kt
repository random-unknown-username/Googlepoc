package com.example.aadtool

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException

/** Maximum number of bytes to capture from each incoming connection. */
private const val CAPTURE_BYTES = 512

/**
 * A lightweight TCP diagnostic server that listens on [port] and logs every
 * connection attempt.  All I/O runs on [Dispatchers.IO] via coroutines.
 *
 * Call [start] to begin listening.
 * Call [stop] to close the server socket and halt the accept loop.
 */
class DiagnosticServer(
    private val port: Int,
    private val logManager: LogManager,
    private val scope: CoroutineScope,
    private val onStatusChanged: (Boolean) -> Unit
) {
    @Volatile
    private var serverSocket: ServerSocket? = null

    fun start() {
        if (serverSocket?.isClosed == false) {
            logManager.log("Server already running on port $port.")
            return
        }
        scope.launch(Dispatchers.IO) {
            try {
                ServerSocket(port).use { ss ->
                    serverSocket = ss
                    withContext(Dispatchers.Main) {
                        logManager.log(">>> TCP listener started on port $port")
                        onStatusChanged(true)
                    }
                    while (isActive && !ss.isClosed) {
                        try {
                            val client: Socket = ss.accept()
                            // Handle each connection in its own coroutine
                            launch { handleConnection(client) }
                        } catch (e: SocketException) {
                            // Server socket was closed – exit cleanly
                            break
                        }
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    logManager.log("ERROR starting server: ${e.message}")
                    onStatusChanged(false)
                }
            } finally {
                serverSocket = null
                withContext(Dispatchers.Main) {
                    logManager.log(">>> TCP listener stopped")
                    onStatusChanged(false)
                }
            }
        }
    }

    fun stop() {
        try {
            serverSocket?.close()
        } catch (_: Exception) { /* ignored */ }
        serverSocket = null
    }

    private suspend fun handleConnection(socket: Socket) {
        val remote = "${socket.inetAddress.hostAddress}:${socket.port}"
        withContext(Dispatchers.Main) {
            logManager.log("─── Connection from $remote")
        }
        try {
            socket.use { s ->
                s.soTimeout = 3_000 // 3 s read timeout
                val stream = s.getInputStream()
                val buf = ByteArray(CAPTURE_BYTES)
                val read = stream.read(buf)
                withContext(Dispatchers.Main) {
                    if (read > 0) {
                        val hex = buf.take(read).joinToString(" ") { "%02X".format(it) }
                        val text = String(buf, 0, read, Charsets.UTF_8)
                            .replace(Regex("[^\\x20-\\x7E]"), ".")
                        logManager.log("  [$remote] read $read bytes")
                        logManager.log("  HEX : $hex")
                        logManager.log("  TEXT: $text")
                    } else {
                        logManager.log("  [$remote] connection closed immediately (no data)")
                    }
                }
            }
        } catch (e: Exception) {
            withContext(Dispatchers.Main) {
                logManager.log("  [$remote] read error: ${e.message}")
            }
        }
    }
}
