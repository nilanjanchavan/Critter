/**
 * Critter Desktop Companion - Background Service Worker
 *
 * Connects to the local Critter bridge on 127.0.0.1:8765, broadcasts navigation
 * events, and handles safe tab-closing commands with stale-tab protection.
 */

try {
  importScripts('compat.js');
} catch (e) {
  // compat.js already in scope or bundled
}

const Compat = self.CritterCompat;

const ConnectionState = {
  DISCONNECTED: 'disconnected',
  CONNECTING: 'connecting',
  AUTHENTICATING: 'authenticating',
  CONNECTED: 'connected',
  AUTH_FAILED: 'auth_failed'
};

class BridgeClient {
  constructor() {
    this.ws = null;
    this.state = ConnectionState.DISCONNECTED;
    this.sessionId = null;
    this.retryDelay = 1000;
    this.pingInterval = null;
    this.reconnectTimer = null;
  }

  async init() {
    console.log('[Critter] Initializing BridgeClient...');
    this.registerTabListeners();
    this.registerExtensionMessageListeners();
    await this.connect();
  }

  async getConfig() {
    const data = await Compat.getStorage(['bridge_host', 'bridge_port', 'auth_token']);
    return {
      host: data.bridge_host || '127.0.0.1',
      port: data.bridge_port || 8765,
      token: data.auth_token || ''
    };
  }

  updateState(newState, details = {}) {
    this.state = newState;
    Compat.setStorage({
      connection_state: newState,
      session_id: this.sessionId,
      ...details
    });
    console.log(`[Critter] State changed to: ${newState}`);
  }

  async connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const config = await this.getConfig();
    if (!config.token) {
      this.updateState(ConnectionState.DISCONNECTED, { error: 'No auth token configured' });
      console.warn('[Critter] No auth token configured. Open extension popup to pair.');
      return;
    }

    const url = `ws://${config.host}:${config.port}`;
    this.updateState(ConnectionState.CONNECTING);
    console.log(`[Critter] Connecting to bridge at ${url}...`);

    try {
      this.ws = new WebSocket(url);
    } catch (err) {
      console.error('[Critter] Failed to construct WebSocket:', err);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.updateState(ConnectionState.AUTHENTICATING);
      // 1. Send authentication message immediately
      const authMsg = {
        type: 'auth',
        token: config.token,
        client: 'critter-companion',
        version: '1.0.0',
        browser: Compat.isFirefox ? 'firefox' : 'chromium'
      };
      this.send(authMsg);
    };

    this.ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        await this.handleMessage(msg);
      } catch (err) {
        console.error('[Critter] Error parsing incoming message:', err, event.data);
      }
    };

    this.ws.onclose = (event) => {
      console.log(`[Critter] WebSocket closed (code ${event.code}, reason: "${event.reason}")`);
      this.cleanup();
      if (event.code === 1008 && event.reason.toLowerCase().includes('token')) {
        this.updateState(ConnectionState.AUTH_FAILED, { error: 'Authentication token rejected' });
      } else {
        this.updateState(ConnectionState.DISCONNECTED);
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (err) => {
      console.warn('[Critter] WebSocket connection error:', err);
    };
  }

  scheduleReconnect() {
    if (this.reconnectTimer) return;
    console.log(`[Critter] Scheduling reconnect in ${this.retryDelay}ms...`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.retryDelay = Math.min(this.retryDelay * 2, 30000);
      this.connect();
    }, this.retryDelay);
  }

  cleanup() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    this.sessionId = null;
    this.ws = null;
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  async handleMessage(msg) {
    switch (msg.type) {
      case 'auth_ack':
        this.sessionId = msg.session_id;
        this.retryDelay = 1000;
        this.updateState(ConnectionState.CONNECTED);
        console.log(`[Critter] Successfully authenticated! Session: ${this.sessionId}`);
        this.startHeartbeat();
        this.reportActiveTab();
        break;

      case 'auth_err':
        console.error(`[Critter] Authentication rejected: ${msg.reason}`);
        this.updateState(ConnectionState.AUTH_FAILED, { error: msg.reason });
        break;

      case 'close_tab':
        await this.handleCloseTabCommand(msg);
        break;

      case 'pong':
        // Heartbeat acknowledged
        break;

      default:
        console.log('[Critter] Received unhandled message:', msg);
    }
  }

  startHeartbeat() {
    if (this.pingInterval) clearInterval(this.pingInterval);
    this.pingInterval = setInterval(() => {
      this.send({ type: 'ping' });
    }, 25000);
  }

  /**
   * Safe tab closing with verification that tab still exists and matches expected domain.
   */
  async handleCloseTabCommand(command) {
    const tabId = command.tab_id;
    const expectedDomain = (command.expected_domain || '').toLowerCase();
    const sessionId = command.session_id;

    console.log(`[Critter] Received close_tab command for Tab #${tabId} (expected domain: ${expectedDomain})`);

    // 1. Verify tab exists
    const tab = await Compat.getTab(tabId);
    if (!tab) {
      console.warn(`[Critter] Cannot close Tab #${tabId}: tab no longer exists`);
      this.send({
        type: 'tab_close_ack',
        tab_id: tabId,
        session_id: sessionId,
        success: false,
        error: 'tab_not_found'
      });
      return;
    }

    // 2. Stale Tab Protection: verify domain has not changed
    let tabDomain = '';
    try {
      const u = new URL(tab.url);
      tabDomain = u.hostname.toLowerCase();
    } catch {
      // Ignored
    }

    if (expectedDomain && tabDomain && !tabDomain.includes(expectedDomain) && !expectedDomain.includes(tabDomain)) {
      console.warn(`[Critter] Suppressed closing Tab #${tabId}: domain changed to ${tabDomain} != expected ${expectedDomain}`);
      this.send({
        type: 'tab_close_ack',
        tab_id: tabId,
        session_id: sessionId,
        success: false,
        error: 'stale_tab_domain_mismatch'
      });
      return;
    }

    // 3. Perform closing
    try {
      await Compat.removeTab(tabId);
      console.log(`[Critter] Successfully closed Tab #${tabId}`);
      this.send({
        type: 'tab_close_ack',
        tab_id: tabId,
        session_id: sessionId,
        success: true
      });
    } catch (err) {
      console.error(`[Critter] Failed removing Tab #${tabId}:`, err);
      this.send({
        type: 'tab_close_ack',
        tab_id: tabId,
        session_id: sessionId,
        success: false,
        error: err.message
      });
    }
  }

  registerTabListeners() {
    const api = Compat.api;

    // Navigation updates
    api.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      if (this.state !== ConnectionState.CONNECTED) return;
      if (!tab || !tab.url) return;

      // Only notify when URL is known and scheme is http/https
      if (!tab.url.startsWith('http://') && !tab.url.startsWith('https://')) return;

      // Notify on complete or URL change
      if (changeInfo.status === 'complete' || changeInfo.url) {
        this.send({
          type: 'tab_navigated',
          tab_id: tabId,
          url: tab.url,
          title: tab.title || '',
          incognito: Boolean(tab.incognito)
        });
      }
    });

    // Tab activation (switching tabs)
    api.tabs.onActivated.addListener(async (activeInfo) => {
      if (this.state !== ConnectionState.CONNECTED) return;
      const tab = await Compat.getTab(activeInfo.tabId);
      if (!tab || !tab.url) return;
      if (!tab.url.startsWith('http://') && !tab.url.startsWith('https://')) return;

      this.send({
        type: 'tab_activated',
        tab_id: tab.id,
        url: tab.url,
        title: tab.title || '',
        incognito: Boolean(tab.incognito)
      });
    });

    // Tab closed
    api.tabs.onRemoved.addListener((tabId) => {
      if (this.state !== ConnectionState.CONNECTED) return;
      this.send({
        type: 'tab_closed',
        tab_id: tabId
      });
    });
  }

  async reportActiveTab() {
    const tabs = await Compat.queryTabs({ active: true, currentWindow: true });
    if (tabs.length > 0 && tabs[0].url) {
      const tab = tabs[0];
      if (tab.url.startsWith('http://') || tab.url.startsWith('https://')) {
        this.send({
          type: 'tab_activated',
          tab_id: tab.id,
          url: tab.url,
          title: tab.title || '',
          incognito: Boolean(tab.incognito)
        });
      }
    }
  }

  registerExtensionMessageListeners() {
    Compat.api.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'reconnect') {
        this.retryDelay = 1000;
        this.cleanup();
        this.connect();
        sendResponse({ success: true });
      } else if (request.action === 'get_origin') {
        sendResponse({ origin: Compat.getExtensionOrigin() });
      }
    });
  }
}

// Instantiate and start client
const client = new BridgeClient();
client.init();
