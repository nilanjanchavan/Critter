document.addEventListener('DOMContentLoaded', async () => {
  const originInput = document.getElementById('extension-origin');
  const copyOriginBtn = document.getElementById('copy-origin-btn');
  const hostInput = document.getElementById('bridge-host');
  const portInput = document.getElementById('bridge-port');
  const tokenInput = document.getElementById('auth-token');
  const toggleTokenBtn = document.getElementById('toggle-token-visibility');
  const saveBtn = document.getElementById('save-btn');
  const statusBadge = document.getElementById('status-badge');
  const statusText = document.getElementById('status-text');
  const statusHint = document.getElementById('status-hint');

  // 1. Get and display extension origin
  const extensionOrigin = chrome.runtime.getURL('').replace(/\/$/, '');
  originInput.value = extensionOrigin;

  copyOriginBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(extensionOrigin);
      const originalText = copyOriginBtn.textContent;
      copyOriginBtn.textContent = 'Copied!';
      setTimeout(() => { copyOriginBtn.textContent = originalText; }, 1500);
    } catch {
      originInput.select();
      document.execCommand('copy');
    }
  });

  // 2. Load stored settings
  chrome.storage.local.get(['bridge_host', 'bridge_port', 'auth_token', 'connection_state', 'error'], (data) => {
    if (data.bridge_host) hostInput.value = data.bridge_host;
    if (data.bridge_port) portInput.value = data.bridge_port;
    if (data.auth_token) tokenInput.value = data.auth_token;
    updateBadge(data.connection_state || 'disconnected', data.error);
  });

  // 3. Toggle token visibility
  toggleTokenBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (tokenInput.type === 'password') {
      tokenInput.type = 'text';
      toggleTokenBtn.textContent = 'Hide';
    } else {
      tokenInput.type = 'password';
      toggleTokenBtn.textContent = 'Show';
    }
  });

  // 4. Save and trigger reconnection
  saveBtn.addEventListener('click', () => {
    const host = hostInput.value.trim() || '127.0.0.1';
    const port = parseInt(portInput.value, 10) || 8765;
    const token = tokenInput.value.trim();

    if (!token) {
      showHint('error', '⚠️ Please enter your Bridge Auth Token. Run `critter --bridge-token` in terminal to get it.');
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = 'Connecting...';
    showHint('info', `Connecting to ws://${host}:${port}...`);

    chrome.storage.local.set({
      bridge_host: host,
      bridge_port: port,
      auth_token: token
    }, () => {
      chrome.runtime.sendMessage({ action: 'reconnect' }, (resp) => {
        // Handle lastError if service worker was waking up
        if (chrome.runtime.lastError) {
          console.warn('[Critter Popup] Background wake error:', chrome.runtime.lastError.message);
        }

        setTimeout(() => {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save & Connect';
          // Refresh state from storage
          chrome.storage.local.get(['connection_state', 'error'], (d) => {
            updateBadge(d.connection_state || 'connecting', d.error);
          });
        }, 1200);
      });
    });
  });

  function showHint(type, text) {
    statusHint.style.display = 'block';
    statusHint.className = `status-hint hint-${type}`;
    statusHint.textContent = text;
  }

  function updateBadge(state, errorMsg) {
    statusBadge.className = 'badge';
    switch (state) {
      case 'connected':
        statusBadge.classList.add('badge-connected');
        statusText.textContent = 'Connected';
        showHint('success', '✓ Connected to Critter bridge! Tab events are actively monitored.');
        break;
      case 'connecting':
      case 'authenticating':
        statusBadge.classList.add('badge-connecting');
        statusText.textContent = 'Connecting...';
        showHint('info', 'Connecting to ws://127.0.0.1:8765...');
        break;
      case 'auth_failed':
        statusBadge.classList.add('badge-error');
        statusText.textContent = 'Auth Failed';
        showHint('error', `⚠️ Auth Failed: ${errorMsg || 'Token rejected or origin not paired. Check `critter --list-origins`.'}`);
        break;
      default:
        statusBadge.classList.add('badge-disconnected');
        statusText.textContent = 'Disconnected';
        showHint('error', errorMsg || '⚠️ Disconnected. Make sure Critter is running on your desktop (e.g. `critter --pets dog,cat` or `critter --bridge`).');
    }
  }

  // Listen for background state updates while popup is open
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.connection_state) {
      chrome.storage.local.get(['error'], (d) => {
        updateBadge(changes.connection_state.newValue, d.error);
      });
    }
  });
});

