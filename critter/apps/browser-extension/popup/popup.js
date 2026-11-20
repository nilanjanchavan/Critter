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

    saveBtn.disabled = true;
    saveBtn.textContent = 'Connecting...';

    chrome.storage.local.set({
      bridge_host: host,
      bridge_port: port,
      auth_token: token
    }, () => {
      chrome.runtime.sendMessage({ action: 'reconnect' }, () => {
        setTimeout(() => {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save & Connect';
          // Refresh state
          chrome.storage.local.get(['connection_state', 'error'], (d) => {
            updateBadge(d.connection_state || 'connecting', d.error);
          });
        }, 1000);
      });
    });
  });

  function updateBadge(state, errorMsg) {
    statusBadge.className = 'badge';
    switch (state) {
      case 'connected':
        statusBadge.classList.add('badge-connected');
        statusText.textContent = 'Connected';
        break;
      case 'connecting':
      case 'authenticating':
        statusBadge.classList.add('badge-connecting');
        statusText.textContent = 'Connecting...';
        break;
      case 'auth_failed':
        statusBadge.classList.add('badge-error');
        statusText.textContent = 'Auth Failed';
        break;
      default:
        statusBadge.classList.add('badge-disconnected');
        statusText.textContent = 'Disconnected';
    }
  }

  // Listen for background state updates while popup is open
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.connection_state) {
      updateBadge(changes.connection_state.newValue);
    }
  });
});
