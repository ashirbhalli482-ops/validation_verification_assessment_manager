/**
 * Partial page navigation — swap only #app-main instead of full reload.
 * Server returns a lightweight #app-main fragment when X-Partial-Nav is sent.
 */
(function () {
  'use strict';

  function parsePartialHtml(html) {
    var title = null;
    var titleMatch = html.match(/<!--\s*partial-title:(.*?)\s*-->/);
    if (titleMatch) {
      title = titleMatch[1];
    }
    var doc = new DOMParser().parseFromString(html, 'text/html');
    var nextMain = doc.getElementById('app-main');
    if (!nextMain && html.indexOf('id="app-main"') !== -1) {
      doc = new DOMParser().parseFromString('<body>' + html + '</body>', 'text/html');
      nextMain = doc.getElementById('app-main');
    }
    return { nextMain: nextMain, title: title || doc.title || null };
  }

  function sameOriginLink(link) {
    if (!link || !link.href) return false;
    if (link.classList.contains('nav-dropdown-toggle')) return false;
    if (link.hasAttribute('data-full-nav')) return false;
    if (link.target && link.target !== '_self') return false;
    if (link.getAttribute('href') === '#') return false;
    try {
      var url = new URL(link.href, window.location.origin);
      if (url.origin !== window.location.origin) return false;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return false;
      return true;
    } catch (e) {
      return false;
    }
  }

  function navContainer(el) {
    return el.closest('.sidebar-nav, .app-header, #app-main');
  }

  function shouldPartialSubmit(form) {
    if (!form || form.tagName !== 'FORM') return false;
    if (form.hasAttribute('data-full-nav')) return false;
    if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') return false;
    if (form.querySelector('input[type="file"]')) return false;
    return Boolean(form.closest('#app-main, .sidebar-nav, .app-header'));
  }

  function updateActiveNav() {
    var current = window.location.href.split('#')[0].split('?')[0];
    document.querySelectorAll('.sidebar-nav a.nav-link').forEach(function (link) {
      link.classList.remove('active');
      var href = link.href.split('#')[0].split('?')[0];
      if (href === current) {
        link.classList.add('active');
        var parent = link.parentElement;
        while (parent) {
          if (parent.classList && parent.classList.contains('nav-item')) {
            parent.classList.add('open');
          }
          parent = parent.parentElement;
        }
      }
    });
  }

  function runInlineScripts(container) {
    container.querySelectorAll('script:not([src])').forEach(function (oldScript) {
      var type = (oldScript.getAttribute('type') || 'text/javascript').toLowerCase().trim();
      // Keep JSON / template data blobs (e.g. Django json_script for dependent dropdowns).
      if (
        type &&
        type !== 'text/javascript' &&
        type !== 'application/javascript' &&
        type !== 'module' &&
        type !== 'text/ecmascript' &&
        type !== 'application/ecmascript'
      ) {
        return;
      }
      var code = oldScript.textContent.trim();
      if (!code) {
        oldScript.remove();
        return;
      }
      code = code.replace(
        /document\.addEventListener\s*\(\s*['"]DOMContentLoaded['"]\s*,\s*function\s*\(\)\s*\{/,
        '(function(){'
      );
      if (code.endsWith('});')) {
        code = code.slice(0, -3) + '})();';
      }
      try {
        (new Function(code))();
      } catch (err) {
        console.warn('Partial nav script error:', err);
      }
      oldScript.remove();
    });
  }

  function initSwappedPage() {
    var main = document.getElementById('app-main');
    if (main) runInlineScripts(main);
    updateActiveNav();
    if (typeof window.updateHeaderPageTitle === 'function') {
      window.updateHeaderPageTitle();
    }
    if (window.jQuery) {
      window.jQuery(function ($) {
        $('[id$="SuccessModal"]').modal('show');
      });
    }
    window.scrollTo(0, 0);
  }

  function applyPartialHtml(html, url, pushState) {
    var parsed = parsePartialHtml(html);
    var currentMain = document.getElementById('app-main');
    if (!parsed.nextMain || !currentMain) {
      window.location.href = url;
      return false;
    }
    currentMain.replaceWith(document.importNode(parsed.nextMain, true));
    if (parsed.title) document.title = parsed.title;
    if (pushState) {
      history.pushState({ partialNav: true }, '', url);
    } else {
      history.replaceState({ partialNav: true }, '', url);
    }
    initSwappedPage();
    return true;
  }

  var inflight = null;

  function setLoading(on) {
    document.body.classList.toggle('nav-loading', on);
  }

  function loadPartial(url, pushState) {
    if (inflight) inflight.abort();
    inflight = new AbortController();
    setLoading(true);

    fetch(url, {
      credentials: 'same-origin',
      headers: { 'X-Partial-Nav': '1', 'Accept': 'text/html' },
      signal: inflight.signal,
    })
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.text().then(function (html) {
          return { html: html, url: response.url || url };
        });
      })
      .then(function (result) {
        applyPartialHtml(result.html, result.url, pushState);
      })
      .catch(function (err) {
        if (err.name !== 'AbortError') {
          window.location.href = url;
        }
      })
      .finally(function () {
        setLoading(false);
        inflight = null;
      });
  }

  function submitPartial(form) {
    if (inflight) inflight.abort();
    inflight = new AbortController();
    setLoading(true);

    var action = form.getAttribute('action') || window.location.href;

    fetch(action, {
      method: 'POST',
      body: new FormData(form),
      credentials: 'same-origin',
      redirect: 'follow',
      headers: { 'X-Partial-Nav': '1', 'Accept': 'text/html' },
      signal: inflight.signal,
    })
      .then(function (response) {
        return response.text().then(function (html) {
          return { html: html, url: response.url || action };
        });
      })
      .then(function (result) {
        if (!applyPartialHtml(result.html, result.url, false)) return;
      })
      .catch(function () {
        form.submit();
      })
      .finally(function () {
        setLoading(false);
        inflight = null;
      });
  }

  document.addEventListener('click', function (event) {
    var link = event.target.closest('a');
    if (!link || !navContainer(link) || !sameOriginLink(link)) return;
    event.preventDefault();
    loadPartial(link.href, true);
  });

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!shouldPartialSubmit(form)) return;
    event.preventDefault();
    submitPartial(form);
  }, true);

  window.addEventListener('popstate', function () {
    loadPartial(window.location.href, false);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateActiveNav);
  } else {
    updateActiveNav();
  }
})();
