/* ============================================
   AGENTIC WORKSPACE - APP.JS
   Main Application Logic with GenUI Features
   ============================================ */

// ========================================
// STATE
// ========================================
let currentBotMsgId = null;
let botBuffers = {};

// GenUI: Typing speed tracking
let lastKeyTime = 0;
let keyIntervals = [];
const TYPING_SAMPLE_SIZE = 10;
const SLOW_THRESHOLD_MS = 400;  // Characters typed slower than this = "slow"
const FAST_THRESHOLD_MS = 150;  // Characters typed faster than this = "fast"

// ========================================
// INITIALIZATION
// ========================================
window.addEventListener('pywebviewready', async () => {
    const history = await window.pywebview.api.load_history();
    history.forEach(msg => appendMessage(msg.role, msg.content, false));
    setupDragAndDrop();
    setupTypingSpeedDetection();
    animateHeader();
    loadSessionList();
});

// ========================================
// NEW CHAT / SESSION MANAGEMENT
// ========================================
async function newChat() {
    // Call backend to create new session
    const result = await window.pywebview.api.new_session();
    if (result.status === 'success') {
        clearChatUI();
        console.log('New session started:', result.session_id);
        loadSessionList();
    }
}

function clearChatUI() {
    // Clear chat history DOM
    document.getElementById('chat-history').innerHTML = '';

    // Clear state
    currentBotMsgId = null;
    botBuffers = {};
    checkpointedMessages.clear();

    // Clear checkpoint sidebar
    document.getElementById('checkpoint-blocks').innerHTML = '';
}

async function loadSessionList() {
    const sessions = await window.pywebview.api.list_sessions();
    const list = document.getElementById('session-list');

    if (!sessions || sessions.length === 0) {
        list.innerHTML = '<div class="no-sessions">No previous chats</div>';
        return;
    }

    // Get current session ID to highlight active
    const currentId = await window.pywebview.api.get_current_session_id();

    let html = '';
    sessions.forEach(session => {
        const date = new Date(session.timestamp).toLocaleDateString();
        const activeClass = session.id === currentId ? 'active' : '';
        // Escape title to prevent XSS
        const safeTitle = session.title.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        html += `
            <div class="session-item ${activeClass}" onclick="switchSession('${session.id}')">
                <div class="session-title">${safeTitle}</div>
                <div class="session-date">${date}</div>
            </div>
        `;
    });

    list.innerHTML = html;
}

async function switchSession(sessionId) {
    const result = await window.pywebview.api.switch_session(sessionId);
    if (result.status === 'success') {
        clearChatUI();
        // Load history for this session
        const history = await window.pywebview.api.load_history();
        history.forEach(msg => appendMessage(msg.role, msg.content, false));
        // Refresh list to update active state
        loadSessionList();
    }
}


// ========================================
// GENUI: TYPING SPEED DETECTION
// ========================================
function setupTypingSpeedDetection() {
    const input = document.getElementById('user-input');

    input.addEventListener('keydown', (e) => {
        // Ignore non-character keys
        if (e.key.length !== 1 && e.key !== 'Backspace') return;

        const now = Date.now();
        if (lastKeyTime > 0) {
            const interval = now - lastKeyTime;
            keyIntervals.push(interval);

            // Keep only the last N samples
            if (keyIntervals.length > TYPING_SAMPLE_SIZE) {
                keyIntervals.shift();
            }

            // Calculate average and apply theme
            if (keyIntervals.length >= 5) {
                const avgInterval = keyIntervals.reduce((a, b) => a + b, 0) / keyIntervals.length;
                applyTypingTheme(avgInterval);
            }
        }
        lastKeyTime = now;
    });

    // Reset when input loses focus
    input.addEventListener('blur', () => {
        keyIntervals = [];
        lastKeyTime = 0;
    });
}

function applyTypingTheme(avgInterval) {
    const body = document.body;

    // Remove existing typing classes
    body.classList.remove('typing-slow', 'typing-fast');

    if (avgInterval > SLOW_THRESHOLD_MS) {
        body.classList.add('typing-slow');
    } else if (avgInterval < FAST_THRESHOLD_MS) {
        body.classList.add('typing-fast');
    }
    // Otherwise, neutral theme (no class)
}

// ========================================
// GENUI: TONE-BASED MESSAGE STYLING
// ========================================
function applyToneToMessage(messageId, tone) {
    const msgElement = document.getElementById(messageId);
    if (msgElement && tone) {
        // Remove any existing tone classes
        msgElement.classList.remove('tone-calm', 'tone-excited', 'tone-serious', 'tone-playful');

        // Add the appropriate tone class
        const toneClass = `tone-${tone.toLowerCase()}`;
        if (['tone-calm', 'tone-excited', 'tone-serious', 'tone-playful'].includes(toneClass)) {
            msgElement.classList.add(toneClass);
        }
    }
}

// ========================================
// SIDEBAR
// ========================================
// ========================================
// SIDEBAR
// ========================================
let currentSidebarView = 'chats';

function toggleSidebar(view = null) {
    const sidebar = document.getElementById('sidebar');
    const title = document.getElementById('sidebar-title');

    // If no view specified (e.g. close button), just toggle or close
    if (!view) {
        sidebar.classList.remove('visible');
        updateSidebarPosition();
        return;
    }

    // If opening a new view or switching views
    if (!sidebar.classList.contains('visible') || currentSidebarView !== view) {
        // Update content visibility
        document.getElementById('view-chats').style.display = view === 'chats' ? 'block' : 'none';
        document.getElementById('view-settings').style.display = view === 'settings' ? 'block' : 'none';

        // Update title
        title.textContent = view === 'chats' ? 'Chats' : 'Settings';

        // Update tabs active state
        document.getElementById('tab-chats').classList.toggle('active', view === 'chats');
        document.getElementById('tab-settings').classList.toggle('active', view === 'settings');

        currentSidebarView = view;
        sidebar.classList.add('visible');
    } else {
        // Clicking the same tab again closes it
        sidebar.classList.remove('visible');

        // Remove active state from tabs
        document.getElementById('tab-chats').classList.remove('active');
        document.getElementById('tab-settings').classList.remove('active');
    }

    updateSidebarPosition();
}

function updateSidebarPosition() {
    const sidebar = document.getElementById('sidebar');
    anime({
        targets: sidebar,
        translateX: sidebar.classList.contains('visible') ? ['-100%', '0%'] : ['0%', '-100%'],
        duration: 350,
        easing: 'easeOutQuad'
    });
}

// ========================================
// HEADER ANIMATION
// ========================================
function animateHeader() {
    anime({
        targets: '.logo',
        translateY: [-8, 0],
        opacity: [0, 1],
        duration: 600,
        easing: 'easeOutQuad'
    });
}

// ========================================
// SETTINGS & CONFIGURATION
// ========================================
async function toggleAgents() {
    const enabled = document.getElementById('agent-toggle').checked;
    await window.pywebview.api.toggle_multi_agent(enabled);
}

async function updateProvider() {
    const p = document.getElementById('provider-select').value;
    await window.pywebview.api.set_provider(p);

    // Show/hide cloud API section vs Bonsai panel
    const isLocal = (p === 'bonsai');
    document.getElementById('cloud-api-section').style.display = isLocal ? 'none' : 'block';
    document.getElementById('bonsai-panel').style.display      = isLocal ? 'block' : 'none';

    if (isLocal) {
        await refreshBonsaiStatus();
    }
}

async function updateModel() {
    const m = document.getElementById('model-input').value;
    await window.pywebview.api.set_model(m);
}

// ========================================
// CUSTOM PROVIDER DROPDOWN
// ========================================
function toggleProviderDropdown() {
    const dropdown = document.getElementById('provider-dropdown');
    dropdown.classList.toggle('open');
}

function selectProvider(value, label) {
    const dropdown = document.getElementById('provider-dropdown');
    const selected = dropdown.querySelector('.dropdown-selected');
    const selectedText = selected.querySelector('.selected-text');
    const hiddenInput = document.getElementById('provider-select');

    // Update selected display
    selected.setAttribute('data-value', value);
    selectedText.textContent = label;

    // Update hidden input
    hiddenInput.value = value;

    // Update selected class on options
    dropdown.querySelectorAll('.dropdown-option').forEach(opt => {
        opt.classList.toggle('selected', opt.getAttribute('data-value') === value);
    });

    // Close dropdown
    dropdown.classList.remove('open');

    // Trigger provider update
    updateProvider();
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('provider-dropdown');
    if (dropdown && !dropdown.contains(e.target)) {
        dropdown.classList.remove('open');
    }
});

async function saveKey() {
    const k = document.getElementById('api-key').value;
    const p = document.getElementById('provider-select').value;
    if (!k) {
        alert("Please enter a key");
        return;
    }
    const res = await window.pywebview.api.set_api_key(k, p);
    alert(res);
}

// ========================================
// RAG / FILE HANDLING
// ========================================
async function clearRag() {
    const res = await window.pywebview.api.clear_rag_context();
    document.getElementById('file-list').innerHTML = '';
    document.getElementById('sidebar-file-list').innerHTML = '';
    alert(res);
}

function setupDragAndDrop() {
    const dz = document.getElementById('drop-zone');
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
        dz.addEventListener(evt, e => {
            e.preventDefault();
            e.stopPropagation();
        });
    });
    dz.addEventListener('dragover', () => dz.classList.add('active'));
    dz.addEventListener('dragleave', () => dz.classList.remove('active'));
    dz.addEventListener('drop', e => processFiles(e.dataTransfer.files));
}

function handleFileSelect(e) {
    processFiles(e.target.files);
}

async function processFiles(filesList) {
    const dz = document.getElementById('drop-zone');
    dz.classList.remove('active');
    const files = Array.from(filesList);
    const uploadData = [];

    for (const file of files) {
        const reader = new FileReader();
        const promise = new Promise(resolve => {
            reader.onload = e => resolve({ name: file.name, content: e.target.result });
            reader.readAsDataURL(file);
        });
        uploadData.push(await promise);
    }

    if (uploadData.length > 0) {
        dz.innerText = "Ingesting...";
        const res = await window.pywebview.api.upload_files(uploadData);
        if (res.status === 'success') {
            updateFileList(res.files);
            dz.innerText = "Files ready!";
            setTimeout(() => {
                dz.innerText = "Drag PDF/CSV here\nor Click to upload";
            }, 3000);
        } else {
            alert("Error: " + res.message);
            dz.innerText = "Drag PDF/CSV here\nor Click to upload";
        }
    }
}

function updateFileList(files) {
    const list = document.getElementById('file-list');
    const sidebarList = document.getElementById('sidebar-file-list');
    const html = files.map(f => `<div class="file-tag">${f}</div>`).join('');
    list.innerHTML = html;
    sidebarList.innerHTML = html;

    anime({
        targets: '.file-tag',
        opacity: [0, 1],
        translateY: [6, 0],
        delay: anime.stagger(40),
        duration: 300,
        easing: 'easeOutQuad'
    });
}

// ========================================
// CHAT FUNCTIONALITY
// ========================================
function handleEnter(e) {
    if (e.key === 'Enter') sendPrompt();
}

function sendPrompt() {
    const input = document.getElementById('user-input');
    const val = input.value.trim();
    if (!val) return;

    input.value = '';
    appendMessage('user', val);

    const botId = 'bot-' + Date.now();
    currentBotMsgId = botId;
    botBuffers[botId] = "";
    createBotBubble(botId);

    // Reset typing speed detection for next message
    keyIntervals = [];
    lastKeyTime = 0;

    window.pywebview.api.start_chat_stream(val);
}

function receiveChunk(chunk, targetId) {
    const id = targetId || currentBotMsgId;
    const div = document.getElementById(id);
    if (div) {
        botBuffers[id] = (botBuffers[id] || "") + chunk;
        div.innerHTML = marked.parse(botBuffers[id]);
        scrollToBottom();
    }
}

function createBotBubble(id) {
    const container = document.getElementById('chat-history');
    const wrapper = document.createElement('div');
    wrapper.className = "message-wrapper bot-wrapper";
    wrapper.setAttribute('data-msg-id', id);
    wrapper.innerHTML = `
        <div class="message bot" id="${id}"><span class="loading-dots">Thinking</span></div>
        <button class="checkpoint-btn" onclick="toggleCheckpoint('${id}')" title="Checkpoint this answer">✓</button>
    `;
    container.appendChild(wrapper);
    animateMessage(wrapper);
    scrollToBottom();

    // Create corresponding sidebar block
    createCheckpointBlock(id);
}

function clearBubble(id) {
    const div = document.getElementById(id);
    if (div) {
        div.innerHTML = "";
        botBuffers[id] = "";
    }
}

function appendMessage(role, text, animate = true) {
    if (role === 'bot') {
        const id = 'bot-' + Math.random().toString(36).substr(2, 9);
        botBuffers[id] = text;
        createBotBubble(id);
        document.getElementById(id).innerHTML = marked.parse(text);
    } else {
        const container = document.getElementById('chat-history');
        const wrapper = document.createElement('div');
        wrapper.className = "message-wrapper user-wrapper";
        wrapper.innerHTML = `<div class="message user">${text.replace(/</g, "&lt;")}</div>`;
        container.appendChild(wrapper);
        if (animate) {
            animateMessage(wrapper);
        }
    }
    scrollToBottom();
}

function animateMessage(wrapper) {
    anime({
        targets: wrapper,
        opacity: [0, 1],
        translateY: [10, 0],
        duration: 300,
        easing: 'easeOutQuad'
    });
}

function scrollToBottom() {
    document.getElementById('chat-history').scrollTop = document.getElementById('chat-history').scrollHeight;
}

function receiveError(e) {
    alert("Error: " + e);
}

function streamComplete(tone) {
    // Apply tone-based styling if provided
    if (currentBotMsgId && tone) {
        applyToneToMessage(currentBotMsgId, tone);
    }

    // Update the tooltip for the checkpoint block
    updateCheckpointTooltip(currentBotMsgId);

    currentBotMsgId = null;
}

// ========================================
// CHECKPOINT SIDEBAR FUNCTIONALITY
// ========================================
let checkpointedMessages = new Set();

function createCheckpointBlock(msgId) {
    const container = document.getElementById('checkpoint-blocks');
    const block = document.createElement('div');
    block.className = 'checkpoint-block';
    block.id = `checkpoint-${msgId}`;
    block.setAttribute('data-msg-id', msgId);
    block.setAttribute('data-tooltip', 'Loading...');
    block.onclick = () => navigateToMessage(msgId);
    container.appendChild(block);

    // Animate block appearance
    anime({
        targets: block,
        opacity: [0, 1],
        translateX: [10, 0],
        duration: 300,
        easing: 'easeOutQuad'
    });
}

function updateCheckpointTooltip(msgId) {
    const block = document.getElementById(`checkpoint-${msgId}`);
    const msgDiv = document.getElementById(msgId);
    if (block && msgDiv) {
        // Get first 30 chars of text content as tooltip
        const text = msgDiv.textContent.trim();
        const preview = text.length > 30 ? text.substring(0, 30) + '...' : text;
        block.setAttribute('data-tooltip', preview || 'Answer');
    }
}

function toggleCheckpoint(msgId) {
    const btn = document.querySelector(`.message-wrapper[data-msg-id="${msgId}"] .checkpoint-btn`);
    const block = document.getElementById(`checkpoint-${msgId}`);

    if (checkpointedMessages.has(msgId)) {
        // Uncheck
        checkpointedMessages.delete(msgId);
        btn?.classList.remove('checked');
        block?.classList.remove('checked');
    } else {
        // Check
        checkpointedMessages.add(msgId);
        btn?.classList.add('checked');
        block?.classList.add('checked');

        // Animate the check
        if (block) {
            anime({
                targets: block,
                scale: [1.3, 1],
                duration: 300,
                easing: 'easeOutBack'
            });
        }
    }
}

function navigateToMessage(msgId) {
    const msgElement = document.getElementById(msgId);
    if (msgElement) {
        msgElement.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Highlight briefly
        anime({
            targets: msgElement,
            boxShadow: ['0 0 0 2px var(--accent)', '0 0 0 0px transparent'],
            duration: 1000,
            easing: 'easeOutQuad'
        });
    }
}

// Setup scroll sync between chat and checkpoint sidebar
function setupScrollSync() {
    const chatHistory = document.getElementById('chat-history');
    const checkpointBlocks = document.getElementById('checkpoint-blocks');

    if (!chatHistory || !checkpointBlocks) return;

    chatHistory.addEventListener('scroll', () => {
        // Calculate scroll percentage
        const scrollPercent = chatHistory.scrollTop / (chatHistory.scrollHeight - chatHistory.clientHeight);

        // Find which message is most visible
        const wrappers = chatHistory.querySelectorAll('.message-wrapper.bot-wrapper');
        const chatRect = chatHistory.getBoundingClientRect();
        const chatCenter = chatRect.top + chatRect.height / 2;

        let closestWrapper = null;
        let closestDistance = Infinity;

        wrappers.forEach(wrapper => {
            const rect = wrapper.getBoundingClientRect();
            const distance = Math.abs(rect.top + rect.height / 2 - chatCenter);
            if (distance < closestDistance) {
                closestDistance = distance;
                closestWrapper = wrapper;
            }
        });

        // Update active state on blocks
        document.querySelectorAll('.checkpoint-block').forEach(block => {
            block.classList.remove('active');
        });

        if (closestWrapper) {
            const msgId = closestWrapper.getAttribute('data-msg-id');
            const activeBlock = document.getElementById(`checkpoint-${msgId}`);
            if (activeBlock) {
                activeBlock.classList.add('active');
            }
        }
    });
}

// Initialize scroll sync when ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupScrollSync);
} else {
    setupScrollSync();
}


// ============================================================
// BONSAI 8B LOCAL MODEL — UI LOGIC
// ============================================================

let _bonsaiDownloading = false;
let _bonsaiStarting    = false;

// ----- Status refresh -----

async function refreshBonsaiStatus() {
    const modelKey = document.getElementById('bonsai-model-select').value;
    let status;
    try {
        status = await window.pywebview.api.get_local_model_status(modelKey);
    } catch (e) {
        console.warn('refreshBonsaiStatus error:', e);
        return;
    }

    const dot      = document.getElementById('bonsai-status-dot');
    const text     = document.getElementById('bonsai-status-text');
    const dlSec    = document.getElementById('bonsai-download-section');
    const srvSec   = document.getElementById('bonsai-server-section');
    const warnBin  = document.getElementById('bonsai-binary-warn');
    const btnDl    = document.getElementById('btn-download-bonsai');
    const btnStart = document.getElementById('btn-start-bonsai');
    const btnStop  = document.getElementById('btn-stop-bonsai');

    // Binary warning
    warnBin.style.display = status.binary_found ? 'none' : 'block';

    if (status.server_running) {
        dot.className  = 'status-dot status-online';
        text.textContent = '● Server running — ready to chat';
        dlSec.style.display  = 'none';
        srvSec.style.display = 'block';
        btnStart.style.display = 'none';
        btnStop.style.display  = 'block';
        _bonsaiStarting = false;
    } else if (_bonsaiStarting) {
        dot.className  = 'status-dot status-busy';
        text.textContent = 'Starting server…';
    } else if (status.model_downloaded) {
        dot.className  = 'status-dot status-offline';
        text.textContent = 'Model ready — server not running';
        dlSec.style.display  = 'none';
        srvSec.style.display = 'block';
        btnStart.style.display = 'block';
        btnStop.style.display  = 'none';
    } else if (_bonsaiDownloading) {
        dot.className  = 'status-dot status-busy';
        text.textContent = 'Downloading model…';
        dlSec.style.display  = 'block';
        srvSec.style.display = 'none';
    } else {
        dot.className  = 'status-dot status-offline';
        text.textContent = status.partial_exists
            ? 'Partial download found — resume available'
            : 'Model not downloaded';
        dlSec.style.display  = 'block';
        srvSec.style.display = 'none';
        btnDl.disabled = !status.binary_found && modelKey === 'bonsai-8b-q4' ? false : !status.binary_found;
    }
}

// Auto-refresh status every 4 s while Bonsai panel is visible
setInterval(() => {
    const panel = document.getElementById('bonsai-panel');
    if (panel && panel.style.display !== 'none') {
        refreshBonsaiStatus();
    }
}, 4000);

// ----- Variant change -----

async function onBonsaiVariantChange() {
    await refreshBonsaiStatus();
}

// ----- Download -----

async function downloadBonsai() {
    const modelKey = document.getElementById('bonsai-model-select').value;

    _bonsaiDownloading = true;
    document.getElementById('bonsai-progress-wrap').style.display = 'block';
    document.getElementById('btn-download-bonsai').style.display  = 'none';
    document.getElementById('btn-cancel-download').style.display  = 'block';

    const dot  = document.getElementById('bonsai-status-dot');
    const text = document.getElementById('bonsai-status-text');
    dot.className    = 'status-dot status-busy';
    text.textContent = 'Starting download…';

    await window.pywebview.api.download_bonsai(modelKey);
}

// Called from Python: updateDownloadProgress(percent, message)
function updateDownloadProgress(pct, msg) {
    const fill  = document.getElementById('bonsai-progress-fill');
    const label = document.getElementById('bonsai-progress-label');
    const dot   = document.getElementById('bonsai-status-dot');
    const text  = document.getElementById('bonsai-status-text');

    if (pct === -1.0) {
        // Error
        _bonsaiDownloading = false;
        dot.className    = 'status-dot status-error';
        text.textContent = msg;
        document.getElementById('btn-download-bonsai').style.display  = 'block';
        document.getElementById('btn-cancel-download').style.display  = 'none';
        document.getElementById('bonsai-progress-wrap').style.display = 'none';
        return;
    }

    if (pct >= 100) {
        // Complete
        _bonsaiDownloading = false;
        fill.style.width   = '100%';
        label.textContent  = msg;
        dot.className      = 'status-dot status-offline';
        text.textContent   = 'Download complete';

        setTimeout(() => {
            document.getElementById('bonsai-progress-wrap').style.display = 'none';
            refreshBonsaiStatus();
        }, 1500);
        return;
    }

    fill.style.width  = `${pct}%`;
    label.textContent = msg;
    dot.className     = 'status-dot status-busy';
    text.textContent  = `Downloading… ${pct.toFixed(1)}%`;
}

async function cancelBonsaiDownload() {
    const modelKey = document.getElementById('bonsai-model-select').value;
    _bonsaiDownloading = false;
    await window.pywebview.api.cancel_download_bonsai(modelKey);
    document.getElementById('bonsai-progress-wrap').style.display = 'none';
    document.getElementById('btn-download-bonsai').style.display  = 'block';
    document.getElementById('btn-cancel-download').style.display  = 'none';
    await refreshBonsaiStatus();
}

// ----- Server start / stop -----

async function startBonsai() {
    const modelKey   = document.getElementById('bonsai-model-select').value;
    const gpuLayers  = parseInt(document.getElementById('bonsai-gpu-layers').value) || 0;

    _bonsaiStarting = true;
    const dot  = document.getElementById('bonsai-status-dot');
    const text = document.getElementById('bonsai-status-text');
    dot.className    = 'status-dot status-busy';
    text.textContent = 'Loading model into memory… (this may take 30–60 s)';

    document.getElementById('btn-start-bonsai').disabled = true;

    await window.pywebview.api.start_bonsai(modelKey, gpuLayers);
}

// Called from Python when server is ready or failed
function onBonsaiServerReady(ok) {
    _bonsaiStarting = false;
    document.getElementById('btn-start-bonsai').disabled = false;
    if (ok) {
        refreshBonsaiStatus();
    } else {
        const dot  = document.getElementById('bonsai-status-dot');
        const text = document.getElementById('bonsai-status-text');
        dot.className    = 'status-dot status-error';
        text.textContent = '✗ Server failed to start — check ~/.myapp/llama_server.log';
    }
}

async function stopBonsai() {
    await window.pywebview.api.stop_bonsai();
    setTimeout(refreshBonsaiStatus, 500);
}
