console.log("🔌 Connecting to backend...");

const socket = io("http://127.0.0.1:5000", {
    transports: ["websocket"],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});

// ===== CONNECTION STATUS =====
socket.on("connect", () => {
    console.log("✅ Connected to backend!");
});

socket.on("disconnect", () => {
    console.log("❌ Disconnected from backend!");
});

// ===== CHAT UI UPDATES =====
const chatBox = document.getElementById("chat-box");
const micBtn = document.getElementById("mic-btn");
const statusText = document.getElementById("status");

// Add messages to chatbox
function addMessage(text, sender = "ai") {
    const message = document.createElement("div");
    message.className = sender === "ai" ? "ai-message" : "user-message";
    message.innerHTML = text;
    chatBox.appendChild(message);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ===== RECEIVE AI RESPONSE =====
socket.on("ai_response", (data) => {
    addMessage(data.text, "ai");
});

// ===== UPDATE STATUS =====
socket.on("ai_update", (data) => {
    if (data.state === "listening") {
        statusText.innerText = "🎤 Listening...";
    } else if (data.state === "processing") {
        statusText.innerText = "⚙️ Processing...";
    } else if (data.state === "thinking") {
        statusText.innerText = "🤖 Thinking...";
    } else {
        statusText.innerText = "✅ ASK ANYTHING";
    }
});

// ===== SHOW WHAT USER SAID =====
socket.on("user_command", (data) => {
    addMessage("🗣️ " + data.text, "user");
});

// ===== MIC BUTTON CLICK =====
micBtn.addEventListener("click", () => {
    console.log("🎤 Mic clicked — sending request to backend");
    socket.emit("listen_for_command");
});
