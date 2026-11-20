/**
 * Browser API compatibility layer isolating Chrome vs. Firefox differences.
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.CritterCompat = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const isFirefox = typeof browser !== 'undefined' && typeof browser.runtime !== 'undefined';
  const api = isFirefox ? browser : chrome;

  return {
    isFirefox: isFirefox,
    isChromium: !isFirefox,
    api: api,

    /**
     * Normalize storage get with fallback defaults.
     */
    async getStorage(keys) {
      if (isFirefox) {
        return await browser.storage.local.get(keys);
      }
      return new Promise((resolve) => {
        chrome.storage.local.get(keys, (res) => resolve(res || {}));
      });
    },

    /**
     * Normalize storage set.
     */
    async setStorage(items) {
      if (isFirefox) {
        return await browser.storage.local.set(items);
      }
      return new Promise((resolve) => {
        chrome.storage.local.set(items, () => resolve());
      });
    },

    /**
     * Normalize tab query.
     */
    async queryTabs(queryInfo) {
      if (isFirefox) {
        return await browser.tabs.query(queryInfo);
      }
      return new Promise((resolve) => {
        chrome.tabs.query(queryInfo, (tabs) => resolve(tabs || []));
      });
    },

    /**
     * Normalize tab get by ID.
     */
    async getTab(tabId) {
      if (isFirefox) {
        try {
          return await browser.tabs.get(tabId);
        } catch {
          return null;
        }
      }
      return new Promise((resolve) => {
        chrome.tabs.get(tabId, (tab) => {
          if (chrome.runtime.lastError) {
            resolve(null);
          } else {
            resolve(tab);
          }
        });
      });
    },

    /**
     * Normalize tab remove.
     */
    async removeTab(tabId) {
      if (isFirefox) {
        return await browser.tabs.remove(tabId);
      }
      return new Promise((resolve, reject) => {
        chrome.tabs.remove(tabId, () => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve();
          }
        });
      });
    },

    /**
     * Get extension origin (e.g. chrome-extension://<id> or moz-extension://<uuid>).
     */
    getExtensionOrigin() {
      const url = api.runtime.getURL('');
      return url.endsWith('/') ? url.slice(0, -1) : url;
    }
  };
});

