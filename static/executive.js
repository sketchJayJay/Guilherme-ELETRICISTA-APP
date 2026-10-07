/* Shared interactions for Guilherme Executive. */
(() => {
  let menuTrigger = null;
  const mobile = window.matchMedia('(max-width: 760px)');
  window.closeSidebar = function() {
    const sidebar = document.querySelector('.sidebar');
    const wasOpen = sidebar?.classList.contains('open');
    sidebar?.classList.remove('open');
    document.body.classList.remove('sidebar-open');
    document.querySelectorAll('[aria-controls="appSidebar"]').forEach(b => b.setAttribute('aria-expanded', 'false'));
    const main = document.querySelector('.main');
    const bottom = document.querySelector('.mobile-bottom');
    if (main) main.inert = false;
    if (bottom) bottom.inert = false;
    if (wasOpen && menuTrigger?.isConnected && mobile.matches) menuTrigger.focus({preventScroll:true});
  };
  window.toggleSidebar = function() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar || !mobile.matches) return;
    if (sidebar.classList.contains('open')) { closeSidebar(); return; }
    menuTrigger = document.activeElement;
    sidebar.classList.add('open');
    document.body.classList.add('sidebar-open');
    document.querySelectorAll('[aria-controls="appSidebar"]').forEach(b => b.setAttribute('aria-expanded', 'true'));
    document.querySelector('.main').inert = true;
    const bottom = document.querySelector('.mobile-bottom');
    if (bottom) bottom.inert = true;
    sidebar.querySelector('.sidebar-close')?.focus({preventScroll:true});
  };
  mobile.addEventListener('change', () => closeSidebar());
  document.querySelector('.sidebar')?.addEventListener('keydown', e => {
    if (e.key !== 'Tab' || !mobile.matches || !document.body.classList.contains('sidebar-open')) return;
    const focusable = [...e.currentTarget.querySelectorAll('a[href],button')].filter(x => x.getClientRects().length);
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
  document.querySelectorAll('[data-go-back]').forEach(link => link.addEventListener('click', e => {
    // Do not navigate out of the app when this page was opened from an external link.
    try {
      if (document.referrer && new URL(document.referrer).origin === location.origin && history.length > 1) {
        e.preventDefault(); history.back();
      }
    } catch (_) {}
  }));
  document.querySelectorAll('.flash-dismiss').forEach(b => b.addEventListener('click', () => b.closest('.flash').remove()));
  document.querySelectorAll('.field').forEach((field,i) => {
    const label=field.querySelector(':scope > label');
    const target=field.querySelector('input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]),select,textarea');
    if (!label || !target || label.htmlFor) return;
    if (!target.id) target.id='guilherme-field-'+i;
    label.htmlFor=target.id;
  });
  const searchDialog = document.getElementById('searchDialog');
  const createDialog = document.getElementById('createDialog');
  function openDialog(dialog) {
    if (!dialog) return;
    closeSidebar();
    document.querySelectorAll('dialog[open]').forEach(other => { if (other !== dialog) other.close(); });
    if (!dialog.open) dialog.showModal();
  }
  document.querySelectorAll('[data-open-search]').forEach(b => b.addEventListener('click', () => {
    openDialog(searchDialog);
    document.getElementById('commandSearch')?.focus();
  }));
  document.querySelectorAll('[data-open-create]').forEach(b => b.addEventListener('click', () => openDialog(createDialog)));
  document.querySelectorAll('dialog').forEach(dialog => {
    dialog.querySelector('[data-close-dialog]')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', e => {
      if (e.target !== dialog) return;
      const r = dialog.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close();
    });
  });
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k' && searchDialog) {
      e.preventDefault(); openDialog(searchDialog); document.getElementById('commandSearch').focus();
    }
  });
  const input = document.getElementById('commandSearch');
  const results = document.getElementById('commandResults');
  const hint = document.getElementById('searchHint');
  if (input && results && hint) {
    let debounce, controller, version = 0, active = -1;
    const selectResult = index => {
      const rows = [...results.querySelectorAll('.command-result')];
      active = rows.length ? (index + rows.length) % rows.length : -1;
      rows.forEach((row,i) => row.setAttribute('aria-selected', i === active ? 'true' : 'false'));
      if (active >= 0) {
        input.setAttribute('aria-activedescendant', rows[active].id);
        rows[active].scrollIntoView({block:'nearest'});
      } else input.removeAttribute('aria-activedescendant');
    };
    async function search() {
      const currentVersion = ++version;
      controller?.abort();
      results.replaceChildren(); active = -1;
      input.removeAttribute('aria-activedescendant');
      input.setAttribute('aria-expanded','false');
      const q = input.value.trim();
      if (q.length < 2) { hint.textContent = 'Digite pelo menos 2 caracteres para buscar.'; return; }
      hint.textContent = 'Buscando...';
      controller = new AbortController();
      try {
        const response = await fetch(document.body.dataset.searchUrl + '?' + new URLSearchParams({q}), {signal:controller.signal, credentials:'same-origin'});
        if (!response.ok || response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('search');
        const data = await response.json();
        if (currentVersion !== version || !searchDialog.open) return;
        const items = Array.isArray(data.results) ? data.results : [];
        hint.textContent = items.length ? items.length + ' resultado(s) encontrado(s)' : 'Nenhum resultado. Tente outro nome ou número.';
        items.forEach((item,i) => {
          const a = document.createElement('a');
          a.className = 'command-result'; a.id = 'search-result-' + i;
          a.href = item.url; a.setAttribute('role','option'); a.setAttribute('aria-selected','false');
          const kind = document.createElement('span'); kind.textContent = item.kind;
          const copy = document.createElement('span');
          const title = document.createElement('strong'); title.textContent = item.title;
          const detail = document.createElement('small'); detail.textContent = item.detail;
          copy.append(title,detail); a.append(kind,copy); results.append(a);
        });
        input.setAttribute('aria-expanded', items.length ? 'true' : 'false');
      } catch (e) {
        if (e.name !== 'AbortError' && currentVersion === version) hint.textContent = 'Não foi possível buscar agora. Tente novamente.';
      }
    }
    input.addEventListener('input', () => {
      clearTimeout(debounce); ++version; controller?.abort();
      results.replaceChildren(); active = -1;
      input.setAttribute('aria-expanded','false');
      input.removeAttribute('aria-activedescendant');
      debounce = setTimeout(search, 220);
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); selectResult(active + (e.key === 'ArrowDown' ? 1 : -1));
      } else if (e.key === 'Enter') {
        const rows = [...results.querySelectorAll('.command-result')];
        if (rows.length) { e.preventDefault(); location.assign(rows[Math.max(0,active)].href); }
      }
    });
    searchDialog.addEventListener('close', () => {
      ++version; controller?.abort(); clearTimeout(debounce);
      input.value=''; results.replaceChildren(); active=-1;
      input.setAttribute('aria-expanded','false'); input.removeAttribute('aria-activedescendant');
      hint.textContent='Digite pelo menos 2 caracteres para buscar.';
    });
  }
  document.querySelectorAll('[data-toggle-password]').forEach(button => button.addEventListener('click', () => {
    const target = document.getElementById(button.dataset.togglePassword);
    if (!target) return;
    const visible = target.type === 'password';
    target.type = visible ? 'text' : 'password';
    button.setAttribute('aria-pressed', visible ? 'true' : 'false');
    button.setAttribute('aria-label', visible ? 'Ocultar senha' : 'Mostrar senha');
  }));
  // Keep the PWA installable and preserve the existing push service worker.
  if ('serviceWorker' in navigator && document.body.dataset.searchUrl && window.isSecureContext) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
})();
