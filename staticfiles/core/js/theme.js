(function (window, document) {
  'use strict';

  var THEME_KEY = 'lynx.theme';
  var THEMES = ['light', 'dark'];

  function getStoredTheme() {
    try {
      var value = window.localStorage.getItem(THEME_KEY);
      if (THEMES.indexOf(value) !== -1) {
        return value;
      }
    } catch (e) { /* ignore */ }
    return 'light';
  }

  function removeThemeClasses(target) {
    THEMES.forEach(function (name) {
      target.classList.remove('theme-' + name);
    });
  }

  function applyTheme(theme) {
    var safeTheme = THEMES.indexOf(theme) !== -1 ? theme : 'light';
    var root = document.documentElement;
    var body = document.body;
    if (!body || !body.classList) { return; }
    removeThemeClasses(body);
    removeThemeClasses(root);
    body.classList.add('theme-' + safeTheme);
    root.classList.add('theme-' + safeTheme);
    root.setAttribute('data-theme', safeTheme);
    body.setAttribute('data-theme', safeTheme);
    var switches = document.querySelectorAll('[data-theme-switch]');
    switches.forEach(function (node) {
      if (node.getAttribute('data-theme-switch') === safeTheme) {
        node.classList.add('theme-switch-active');
      } else {
        node.classList.remove('theme-switch-active');
      }
    });
  }

  function persistTheme(theme) {
    var safeTheme = THEMES.indexOf(theme) !== -1 ? theme : 'light';
    try {
      window.localStorage.setItem(THEME_KEY, safeTheme);
    } catch (e) { /* ignore */ }
    applyTheme(safeTheme);
  }

  function bindThemeSwitches() {
    var switches = document.querySelectorAll('[data-theme-switch]');
    switches.forEach(function (node) {
      node.addEventListener('click', function (event) {
        event.preventDefault();
        var desired = node.getAttribute('data-theme-switch');
        if (!desired) { return; }
        persistTheme(desired);
      });
    });
  }

  function initThemeSwitcher() {
    applyTheme(getStoredTheme());
    bindThemeSwitches();
    window.addEventListener('storage', function (evt) {
      if (evt.key === THEME_KEY) {
        applyTheme(evt.newValue);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initThemeSwitcher);
  } else {
    initThemeSwitcher();
  }
})(window, document);

