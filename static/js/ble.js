// ============================================================
// SafeRoute BLE - stable browser sender
// File: static/js/ble.js
// ============================================================

const SAFE_ROUTE_UUID = "0000bafe-0000-1000-8000-00805f9b34fb";
const B0A1_UUID = "0000b0a1-0000-1000-8000-00805f9b34fb";
const B0A2_UUID = "0000b0a2-0000-1000-8000-00805f9b34fb";

const CHUNK_SIZE = 20;
const CHUNK_DELAY = 250; // gives Android GATT server time between writes

let device = null;
let server = null;
let service = null;
let sosChar = null;
let ackChar = null;
let connected = false;
let sending = false;
let ackListenerAttached = false;

const BT_ID_MAP = {
    status: "btStatus",
    log: "btLog",
    deviceList: "btDeviceList",
    chars: "btChars",
    charsSection: "btCharsSection",
    scanBtn: "btScanBtn",
    testBtn: "btTestBtn",
    sosBtn: "btSosBtn",
    disconnectBtn: "btDisconnectBtn",
    messageInput: "btMessageInput",
    sendMessageBtn: "btSendMessageBtn",
    clearMessageBtn: "btClearMessageBtn",
    messageCounter: "btMessageCounter",
    byteStatus: "btByteStatus"
};

const $ = id => document.getElementById(BT_ID_MAP[id] || id);

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function log(message, color = "#d4d4d4") {
    const box = $("log");
    if (!box) return;

    const line = document.createElement("div");
    line.style.color = color;
    line.textContent =
        `[${new Date().toLocaleTimeString()}] ${message}`;

    box.prepend(line);
}

function status(message, type = "info") {
    const el = $("status");
    const text = document.getElementById("btStatusText");
    if (!el) return;

    el.className = `bt-status ${type}`;
    if (text) text.textContent = message;
    else el.textContent = message;
}

function esc(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function deviceName() {
    return device?.name?.trim() || "Unknown BLE Device";
}

function isGattConnected() {
    return !!(
        device &&
        device.gatt &&
        device.gatt.connected &&
        connected
    );
}

function resetButtons() {
    const ready = isGattConnected() && !!sosChar;

    $("testBtn").disabled = !ready || sending;
    $("sosBtn").disabled = !ready || sending;
    $("messageInput").disabled = !ready || sending;
    $("sendMessageBtn").disabled = !ready || sending;
    $("clearMessageBtn").disabled = !ready || sending;
    $("disconnectBtn").disabled = !isGattConnected() || sending;
}

function clearBleState() {
    connected = false;
    server = null;
    service = null;
    sosChar = null;
    ackChar = null;
    ackListenerAttached = false;
    resetButtons();
}

function handleDisconnect() {
    log("🔌 BLE device disconnected.", "#ffb74d");
    clearBleState();

    status(
        "🔌 Bluetooth device disconnected. Connect again.",
        "warning"
    );

    $("deviceList").innerHTML = "";
}

async function connectToDevice() {
    if (!device) {
        throw new Error("No BLE device selected.");
    }

    status(`🔗 Connecting to ${deviceName()}...`, "info");

    if (device.gatt.connected) {
        server = device.gatt;
    } else {
        server = await device.gatt.connect();
    }

    log("✅ GATT Connected!", "#81c784");

    service = await server.getPrimaryService(SAFE_ROUTE_UUID);

    log(
        `✅ SafeRoute service found: ${service.uuid}`,
        "#81c784"
    );

    const characteristics = await service.getCharacteristics();

    if ($("chars")) $("chars").innerHTML = "";
    if ($("charsSection")) $("charsSection").classList.remove("hidden");

    sosChar = null;
    ackChar = null;

    for (const c of characteristics) {
        const p = c.properties || {};
        const props = [];

        if (p.read) props.push("READ");
        if (p.write) props.push("WRITE");
        if (p.writeWithoutResponse) {
            props.push("WRITE WITHOUT RESPONSE");
        }
        if (p.notify) props.push("NOTIFY");
        if (p.indicate) props.push("INDICATE");

        $("chars")?.insertAdjacentHTML(
            "beforeend",
            `
            <div class="char">
                <b>Characteristic</b>
                <div class="uuid">${esc(c.uuid)}</div>
                <div>Properties: ${esc(props.join(", ") || "NONE")}</div>
            </div>
            `
        );

        log(
            `${c.uuid} [${props.join(", ") || "NONE"}]`,
            "#b0bec5"
        );

        if (c.uuid.toLowerCase() === B0A1_UUID) {
            sosChar = c;
        }

        if (c.uuid.toLowerCase() === B0A2_UUID) {
            ackChar = c;
        }
    }

    if (!sosChar) {
        throw new Error("B0A1 SOS WRITE characteristic was not found.");
    }

    if (
        !sosChar.properties.write &&
        !sosChar.properties.writeWithoutResponse
    ) {
        throw new Error("B0A1 is not writable.");
    }

    log(
        `🚨 Found B0A1 WRITE characteristic: ${sosChar.uuid}`,
        "#81c784"
    );

    // Enable ACK notifications.
    if (
        ackChar &&
        (ackChar.properties.notify || ackChar.properties.indicate)
    ) {
        try {
            await ackChar.startNotifications();

            if (!ackListenerAttached) {
                ackChar.addEventListener(
                    "characteristicvaluechanged",
                    onAck
                );
                ackListenerAttached = true;
            }

            log(
                "✅ B0A2 ACK notifications enabled.",
                "#81c784"
            );
        } catch (e) {
            log(
                `⚠️ B0A2 notification setup failed: ${e.message}`,
                "#ffb74d"
            );
        }
    }

    connected = true;

    resetButtons();

    status(
        `✅ Connected to ${deviceName()} — SafeRoute BLE READY`,
        "success"
    );

    log("======================================", "#81c784");
    log("✅ SAFE ROUTE BLE READY", "#81c784");
    log(`📦 Chunk size: ${CHUNK_SIZE} bytes`, "#81c784");
    log(
        "📡 Write mode: WRITE WITHOUT RESPONSE first",
        "#81c784"
    );
    log("======================================", "#81c784");
}

function onAck(event) {
    try {
        const text = new TextDecoder().decode(event.target.value);

        log(`📥 ACK received: ${text}`, "#81c784");

        status(
            `✅ Phone ACK: ${text}`,
            "success"
        );
    } catch (e) {
        log(
            `⚠️ ACK decode failed: ${e.message}`,
            "#ffb74d"
        );
    }
}

// IMPORTANT:
// The Android receiver supports WRITE and WRITE WITHOUT RESPONSE.
// We use WRITE WITHOUT RESPONSE first because it avoids a response
// queue/race when many 20-byte packets are sent quickly.
async function writeOne(data) {
    if (!isGattConnected() || !sosChar) {
        throw new Error(
            "GATT connection is no longer available."
        );
    }

    const bytes =
        data instanceof Uint8Array
            ? data
            : new Uint8Array(data);

    if (bytes.length > CHUNK_SIZE) {
        throw new Error(
            `BLE packet is ${bytes.length} bytes. Maximum is ${CHUNK_SIZE}.`
        );
    }

    // Best option for the current Android GATT server.
    if (
        sosChar.properties.writeWithoutResponse &&
        typeof sosChar.writeValueWithoutResponse === "function"
    ) {
        await sosChar.writeValueWithoutResponse(bytes);
        return;
    }

    // Fallback only if WRITE WITHOUT RESPONSE is unavailable.
    if (
        sosChar.properties.write &&
        typeof sosChar.writeValueWithResponse === "function"
    ) {
        await sosChar.writeValueWithResponse(bytes);
        return;
    }

    if (sosChar.properties.write) {
        await sosChar.writeValue(bytes);
        return;
    }

    throw new Error("B0A1 has no supported write method.");
}

async function sendChunks(bytes) {
    const total = Math.ceil(bytes.length / CHUNK_SIZE);

    log(
        `📦 Total data: ${bytes.length} bytes`,
        "#4fc3f7"
    );

    log(
        `📦 Splitting into ${total} BLE packets...`,
        "#4fc3f7"
    );

    for (let i = 0; i < total; i++) {
        if (!isGattConnected()) {
            throw new Error(
                `BLE disconnected before packet ${i + 1}/${total}.`
            );
        }

        const start = i * CHUNK_SIZE;
        const end = Math.min(
            start + CHUNK_SIZE,
            bytes.length
        );

        const chunk = bytes.slice(start, end);

        log(
            `📤 BLE packet ${i + 1}/${total}: ${chunk.length} bytes`,
            "#4fc3f7"
        );

        // No aggressive 3x retry here.
        // Retrying after Android reports "GATT Service no longer exists"
        // can make the disconnect worse.
        await writeOne(chunk);

        if (i < total - 1) {
            await sleep(CHUNK_DELAY);
        }
    }

    log(
        `✅ All ${total} BLE packets written successfully.`,
        "#81c784"
    );
}

async function sendTextMessage(text) {
    if (!isGattConnected() || !sosChar) {
        throw new Error(
            "BLE is not ready. Connect to the phone first."
        );
    }

    const encoded = new TextEncoder().encode(text);

    if (encoded.length > CHUNK_SIZE) {
        throw new Error(
            "Normal message must be 20 bytes or less."
        );
    }

    sending = true;
    resetButtons();

    try {
        status(
            "📨 Sending message to phone...",
            "info"
        );

        log(
            `📨 MESSAGE: ${text}`,
            "#ce93d8"
        );

        await writeOne(encoded);

        log(
            `📤 HEX: ${Array.from(encoded)
                .map(b => b.toString(16).padStart(2, "0").toUpperCase())
                .join(" ")}`,
            "#4fc3f7"
        );

        log(
            "✅ COMPLETE MESSAGE WRITTEN TO B0A1.",
            "#81c784"
        );

        status(
            "✅ Message sent to phone over BLE.",
            "success"
        );
    } finally {
        sending = false;
        resetButtons();
    }
}

function updateCounter() {
    const text = $("messageInput").value;
    const bytes = new TextEncoder().encode(text);

    $("messageCounter").textContent =
        `${text.length} / 20 characters`;

    $("byteStatus").textContent =
        `Bytes: ${bytes.length} / 20`;

    if (bytes.length > 20) {
        $("byteStatus").style.background = "#f8d7da";
        $("byteStatus").style.color = "#721c24";
        $("sendMessageBtn").disabled = true;
    } else {
        $("byteStatus").style.background = "#d4edda";
        $("byteStatus").style.color = "#155724";
    }
}

async function getBleCurrentLocation() {
    if (navigator.geolocation) {
        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                });
            });
            return {
                latitude: Number(position.coords.latitude),
                longitude: Number(position.coords.longitude),
                speed: Number(position.coords.speed || 0)
            };
        } catch (e) {}
    }

    // Reuse Safe Route's already-detected location when available.
    try {
        if (typeof currentLocation !== "undefined" && currentLocation) {
            return {
                latitude: Number(currentLocation.lat),
                longitude: Number(currentLocation.lon),
                speed: 0
            };
        }
    } catch (e) {}

    // Last-resort Amravati map center, never silently pretending it is GPS.
    return { latitude: 20.9374, longitude: 77.7796, speed: 0, fallback: true };
}

function createGoogleMapsLink(latitude, longitude) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(latitude + "," + longitude)}`;
}

async function sendSOS() {
    if (!isGattConnected() || !sosChar) {
        status("❌ BLE is not ready.", "error");
        return;
    }
    if (sending) return;

    sending = true;
    resetButtons();
    status("🚨 Getting current location and sending emergency SOS...", "info");
    log("🚨 Preparing SOS...", "#ff5252");

    try {
        const location = await getBleCurrentLocation();
        const mapsLink = createGoogleMapsLink(location.latitude, location.longitude);

        const locationBox = document.getElementById("btLocationText");
        const locationLink = document.getElementById("btMapLink");
        if (locationBox) {
            locationBox.innerHTML = `<strong>📍 Current Location</strong><br>Latitude: ${location.latitude.toFixed(6)}<br>Longitude: ${location.longitude.toFixed(6)}${location.fallback ? "<br><small>⚠️ GPS unavailable; using Amravati fallback.</small>" : ""}`;
        }
        if (locationLink) {
            locationLink.href = mapsLink;
            locationLink.style.display = "inline-block";
        }

        const sosData = {
            message_id: "SOS-BLE-" + Date.now(),
            source_device_id: device?.id || "UNKNOWN",
            forwarding_device_id: "WEB_BLE",
            latitude: location.latitude,
            longitude: location.longitude,
            location_link: mapsLink,
            speed: location.speed || 0,
            timestamp: Math.floor(Date.now() / 1000),
            emergency_type: "GENERAL",
            from: "GuardianAI_Web"
        };

        const json = JSON.stringify(sosData);
        const encoded = new TextEncoder().encode(json);
        log(`📍 Location: ${sosData.latitude}, ${sosData.longitude}`, "#4fc3f7");
        log(`📦 SOS size: ${encoded.length} bytes`, "#b0bec5");

        await sendChunks(encoded);

        try {
            const response = await fetch("/api/emergency/bluetooth-forward", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(sosData)
            });
            const result = await response.json();
            if (response.ok && result.success) {
                log("✅ Server acknowledged SOS.", "#81c784");
            } else {
                log(`⚠️ BLE SOS sent, server returned ${response.status}.`, "#ffb74d");
            }
        } catch (e) {
            log(`⚠️ BLE SOS sent; server forwarding unavailable: ${e.message}`, "#ffb74d");
        }

        status("✅ Emergency SOS sent successfully through Bluetooth.", "success");
        log("✅ SOS transmission complete.", "#81c784");
    } catch (e) {
        log(`❌ SOS write failed: ${e.message}`, "#ef5350");
        status(`❌ SOS failed: ${e.message}`, "error");
    } finally {
        sending = false;
        resetButtons();
    }
}

// ------------------------------------------------------------
// UI EVENTS
// ------------------------------------------------------------

$("scanBtn").addEventListener("click", async () => {
    if (!navigator.bluetooth) {
        status(
            "❌ Web Bluetooth is not supported. Use Chrome/Edge.",
            "error"
        );
        return;
    }

    $("scanBtn").disabled = true;
    $("scanBtn").textContent =
        "⏳ Select Bluetooth device...";

    try {
        log(
            "🔍 Opening Bluetooth chooser...",
            "#4fc3f7"
        );

        device =
            await navigator.bluetooth.requestDevice({
                acceptAllDevices: true,
                optionalServices: [
                    SAFE_ROUTE_UUID
                ]
            });

        log(
            `✅ Device selected: ${deviceName()}`,
            "#81c784"
        );

        $("deviceList").innerHTML = `
            <div class="device">
                <div class="device-name">
                    📱 ${esc(deviceName())}
                </div>
                <div class="device-id">
                    Device ID: ${esc(device.id || "Unavailable")}
                </div>
                <div class="connected-label">
                    🟢 BLE Device Selected
                </div>
            </div>
        `;

        device.addEventListener(
            "gattserverdisconnected",
            handleDisconnect
        );

        await connectToDevice();

    } catch (e) {
        if (e.name === "NotFoundError") {
            log(
                "⏹️ Bluetooth selection cancelled.",
                "#ffb74d"
            );
            status(
                "Bluetooth selection cancelled.",
                "warning"
            );
        } else {
            log(
                `❌ Scan/connect error: ${e.message}`,
                "#ef5350"
            );
            status(
                `❌ ${e.message}`,
                "error"
            );
        }
    } finally {
        $("scanBtn").disabled = false;
        $("scanBtn").textContent =
            "📡 Scan for BLE Devices";
        resetButtons();
    }
});

$("messageInput").addEventListener(
    "input",
    updateCounter
);

$("clearMessageBtn").addEventListener(
    "click",
    () => {
        $("messageInput").value = "";
        updateCounter();
        status("Message cleared.", "info");
    }
);

$("sendMessageBtn").addEventListener(
    "click",
    async () => {
        const text = $("messageInput").value.trim();

        if (!text) {
            status(
                "❌ Type a message first.",
                "error"
            );
            return;
        }

        try {
            await sendTextMessage(text);
        } catch (e) {
            log(
                `❌ Message failed: ${e.message}`,
                "#ef5350"
            );
            status(
                `❌ Message failed: ${e.message}`,
                "error"
            );
        }
    }
);

$("testBtn").addEventListener(
    "click",
    async () => {
        if (!isGattConnected() || !sosChar) return;

        sending = true;
        resetButtons();

        try {
            status(
                "🧪 Testing B0A1 WRITE...",
                "info"
            );

            await writeOne(
                new TextEncoder().encode("PING")
            );

            log(
                "✅ PING write succeeded.",
                "#81c784"
            );

            status(
                "✅ B0A1 WRITE test succeeded.",
                "success"
            );
        } catch (e) {
            log(
                `❌ PING write failed: ${e.message}`,
                "#ef5350"
            );

            status(
                `❌ B0A1 WRITE failed: ${e.message}`,
                "error"
            );
        } finally {
            sending = false;
            resetButtons();
        }
    }
);

$("sosBtn").addEventListener(
    "click",
    sendSOS
);

$("disconnectBtn").addEventListener(
    "click",
    () => {
        try {
            if (device?.gatt?.connected) {
                device.gatt.disconnect();
            }
        } catch (e) {
            log(
                `⚠️ Disconnect error: ${e.message}`,
                "#ffb74d"
            );
        }

        handleDisconnect();
    }
);

// ------------------------------------------------------------
// INITIAL STATE
// ------------------------------------------------------------

if (!navigator.bluetooth) {
    status(
        "❌ Web Bluetooth is not supported. Use Chrome or Edge.",
        "error"
    );
    $("scanBtn").disabled = true;
} else {
    log(
        "✅ Web Bluetooth is supported.",
        "#81c784"
    );

    log(
        "📌 UUIDs: BAFE / B0A1 / B0A2",
        "#b0bec5"
    );
}

resetButtons();


// ============================================================
// MAIN GUARDIAN AI MODAL INTEGRATION
// ============================================================
function refreshBluetoothLocation() {
    getBleCurrentLocation().then(location => {
        const box = document.getElementById("btLocationText");
        const link = document.getElementById("btMapLink");
        if (box) {
            box.innerHTML = `<strong>📍 Current Location</strong><br>Latitude: ${location.latitude.toFixed(6)}<br>Longitude: ${location.longitude.toFixed(6)}`;
        }
        if (link) {
            link.href = createGoogleMapsLink(location.latitude, location.longitude);
            link.style.display = "inline-block";
        }
    });
}

function openBluetoothSafety(emergencyMode = false) {
    const modal = document.getElementById("bluetoothModal");
    if (!modal) return;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    refreshBluetoothLocation();
    if (emergencyMode) {
        status("🚨 Emergency mode active. Connect your safety device.", "warning");
        if (!isGattConnected()) {
            setTimeout(() => document.getElementById("btScanBtn")?.click(), 400);
        }
    }
}

function closeBluetoothSafety() {
    const modal = document.getElementById("bluetoothModal");
    if (!modal) return;
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
}

document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeBluetoothSafety();
});
document.getElementById("bluetoothModal")?.addEventListener("click", event => {
    if (event.target.id === "bluetoothModal") closeBluetoothSafety();
});
