(function (global) {
  'use strict';

  var MINIMUMS = {
    chrome: [109, 0],
    edge: [109, 0],
    firefox: [114, 0],
    safari: [16, 4]
  };

  function versionIsLower(versionText, minimum) {
    var parts = String(versionText || '').split('.');
    var major = parseInt(parts[0], 10) || 0;
    var minor = parseInt(parts[1], 10) || 0;
    return major < minimum[0] || (major === minimum[0] && minor < minimum[1]);
  }

  function browserSupport(userAgent) {
    var ua = String(userAgent || '');
    var match;

    if (/MSIE\s|Trident\//.test(ua)) {
      return { supported: false, browser: 'Internet Explorer', reason: 'legacy-browser' };
    }

    match = ua.match(/Edge\/([\d.]+)/);
    if (match) {
      return { supported: false, browser: 'Microsoft Edge Legacy', reason: 'legacy-browser' };
    }

    match = ua.match(/Edg\/([\d.]+)/);
    if (match) {
      return {
        supported: !versionIsLower(match[1], MINIMUMS.edge),
        browser: 'Microsoft Edge',
        reason: 'version'
      };
    }

    match = ua.match(/(?:Chrome|CriOS)\/([\d.]+)/);
    if (match) {
      return {
        supported: !versionIsLower(match[1], MINIMUMS.chrome),
        browser: 'Google Chrome',
        reason: 'version'
      };
    }

    match = ua.match(/Firefox\/([\d.]+)/);
    if (match) {
      return {
        supported: !versionIsLower(match[1], MINIMUMS.firefox),
        browser: 'Mozilla Firefox',
        reason: 'version'
      };
    }

    match = ua.match(/Version\/([\d.]+).*Safari\//);
    if (match) {
      return {
        supported: !versionIsLower(match[1], MINIMUMS.safari),
        browser: 'Safari',
        reason: 'version'
      };
    }

    // Unknown browsers are allowed to try the standards-based app. Browsers
    // without module support are caught by the nomodule fallback in index.html.
    return { supported: true, browser: 'Unknown', reason: 'unknown' };
  }

  function showWarning() {
    var document = global.document;
    if (!document) return;

    var warning = document.getElementById('browser-compatibility-warning');
    var root = document.getElementById('root');
    var urlField = document.getElementById('browser-compatibility-url');

    if (warning) warning.removeAttribute('hidden');
    if (root) root.setAttribute('hidden', 'hidden');
    if (urlField) {
      urlField.value = global.location ? global.location.href : '';
      urlField.onclick = function () {
        this.select();
      };
    }
  }

  function hasRequiredPlatformFeatures() {
    return Boolean(
      global.Promise &&
      global.fetch &&
      global.URL &&
      global.Map &&
      global.Set &&
      Array.prototype.includes
    );
  }

  var api = {
    browserSupport: browserSupport,
    showWarning: showWarning
  };
  global.SiorikBrowserCompatibility = api;

  var support = browserSupport(global.navigator && global.navigator.userAgent);
  if (!support.supported || !hasRequiredPlatformFeatures()) {
    showWarning();
  }
})(window);
