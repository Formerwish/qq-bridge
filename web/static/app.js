// 控制台交互：导航收起/高亮、峰谷行增删、按钮波纹、概览轻量状态校验。无前端框架。
(function () {
  const csrf = document.querySelector('meta[name="csrf"]')?.content || '';

  async function api(path, options = {}) {
    const headers = Object.assign({ 'X-CSRF-Token': csrf }, options.headers || {});
    const resp = await fetch(path, Object.assign({ credentials: 'same-origin' }, options, { headers }));
    if (resp.status === 401) {
      location.href = '/login?next=' + encodeURIComponent(location.pathname);
      throw new Error('未登录');
    }
    const data = await resp.json().catch(() => ({ ok: false, error: '响应格式异常' }));
    if (!resp.ok || data.ok === false) throw new Error(data.error || ('请求失败 ' + resp.status));
    return data;
  }

  // ── 左侧导航：高亮 + 收起（记忆到 localStorage）────────────────
  (function () {
    const layout = document.querySelector('.pro-layout');
    const toggle = document.getElementById('pro-collapse');
    if (!layout) return;
    const key = 'qb.sider.collapsed';
    if (localStorage.getItem(key) === '1') layout.classList.add('collapsed');
    toggle?.addEventListener('click', () => {
      layout.classList.toggle('collapsed');
      localStorage.setItem(key, layout.classList.contains('collapsed') ? '1' : '0');
    });
    const path = location.pathname;
    document.querySelectorAll('.pro-menu a[data-path]').forEach((a) => {
      const p = a.dataset.path;
      a.classList.toggle('active', p === '/' ? path === '/' : path === p || path.startsWith(p + '/'));
    });
  })();

  // ── 运行时长：从 data-sec 起本地自增 ───────────────────────────
  const uptime = document.getElementById('uptime');
  if (uptime) {
    let sec = Number(uptime.dataset.sec || 0);
    const render = () => {
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      uptime.textContent = h + 'h ' + m + 'm';
    };
    render();
    setInterval(() => { sec += 1; render(); }, 1000);
  }

  // ── 峰谷：增删时段 + 星期勾选同步 ──────────────────────────────
  (function () {
    const list = document.getElementById('periods-table');
    const tpl = document.getElementById('row-template');
    if (!list) return;

    function syncDays(row) {
      const hidden = row.querySelector('input[name="days"]');
      if (!hidden) return;
      hidden.value = [...row.querySelectorAll('.day-check')].filter((b) => b.checked).map((b) => b.value).join(',');
    }
    function initRow(row) {
      const hidden = row.querySelector('input[name="days"]');
      if (!hidden) return;
      const active = new Set((hidden.value || '').split(',').filter(Boolean));
      row.querySelectorAll('.day-check').forEach((box) => {
        box.checked = active.has(box.value);
        box.addEventListener('change', () => syncDays(row));
      });
      syncDays(row);
    }

    list.querySelectorAll('.period-row').forEach(initRow);
    document.getElementById('add-row')?.addEventListener('click', () => {
      if (!tpl) return;
      const row = tpl.content.firstElementChild.cloneNode(true);
      list.appendChild(row);
      initRow(row);
      row.querySelector('input[name="name"]')?.focus();
    });
    list.addEventListener('click', (event) => {
      const btn = event.target.closest('.del-row');
      if (!btn) return;
      const row = btn.closest('.period-row');
      if (!row) return;
      if (list.querySelectorAll('.period-row').length <= 1) {
        row.querySelectorAll('input:not([type=hidden])').forEach((i) => { i.value = ''; });
        row.querySelectorAll('.day-check').forEach((b) => { b.checked = false; });
        syncDays(row);
        return;
      }
      row.remove();
    });
    document.getElementById('periods-form')?.addEventListener('submit', () => {
      list.querySelectorAll('.period-row').forEach(syncDays);
    });
  })();

  // ── 刷新按钮 ───────────────────────────────────────────────────
  document.getElementById('refresh')?.addEventListener('click', () => location.reload());

  // ── 概览：每 30 秒校验一次登录/桥接（失败只在标题前加 ⚠）────────
  if (document.getElementById('status-cards')) {
    setInterval(async () => {
      try {
        await api('/api/status');
        document.title = document.title.replace(/^⚠ /, '');
      } catch (err) {
        if (err.message !== '未登录') document.title = '⚠ ' + document.title.replace(/^⚠ /, '');
      }
    }, 30000);
  }

  // ── 按钮点击波纹 ───────────────────────────────────────────────
  document.addEventListener('pointerdown', (event) => {
    const btn = event.target.closest('.btn');
    if (!btn || btn.disabled) return;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    const ripple = document.createElement('span');
    ripple.className = 'rip';
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = (event.clientX - rect.left - size / 2) + 'px';
    ripple.style.top = (event.clientY - rect.top - size / 2) + 'px';
    btn.appendChild(ripple);
    setTimeout(() => ripple.remove(), 550);
  });
})();

// ── 深浅色主题切换 ─────────────────────────────────────────────
(function () {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const dark = document.documentElement.dataset.theme !== 'dark';
    if (dark) document.documentElement.dataset.theme = 'dark';
    else delete document.documentElement.dataset.theme;
    localStorage.setItem('qb.theme', dark ? 'dark' : 'light');
  });
})();

// ── 表格分页（客户端，>=12 行自动生效）────────────────────────
(function () {
  document.querySelectorAll('.panel table.table').forEach((table) => {
    const tbody = table.tBodies[0];
    if (!tbody || tbody.rows.length < 12) return;
    const size = Math.max(5, Number(table.dataset.pageSize || 15));
    const rows = Array.from(tbody.rows);
    const total = rows.length;
    const pageCount = Math.ceil(total / size);
    let page = 1;
    const pager = document.createElement('div');
    pager.className = 'table-pager';
    pager.innerHTML = '<span class="pager-total"></span><div class="pager-actions"></div>';
    table.insertAdjacentElement('afterend', pager);
    const totalEl = pager.querySelector('.pager-total');
    const actions = pager.querySelector('.pager-actions');

    function render() {
      const start = (page - 1) * size;
      rows.forEach((row, i) => {
        row.style.display = i >= start && i < start + size ? '' : 'none';
      });
      totalEl.textContent = '共 ' + total + ' 条 · 第 ' + page + '/' + pageCount + ' 页';
      actions.innerHTML = '';
      const mk = (label, target, disabled, cls) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'btn btn-sm ' + (cls || '');
        b.textContent = label;
        b.disabled = disabled;
        b.addEventListener('click', () => { page = target(); render(); });
        actions.appendChild(b);
      };
      mk('上一页', () => Math.max(1, page - 1), page === 1);
      const from = Math.max(1, Math.min(page - 2, pageCount - 4));
      for (let i = from; i <= Math.min(pageCount, from + 4); i++) {
        mk(String(i), () => i, false, i === page ? 'btn-primary' : 'btn-outline-secondary');
      }
      mk('下一页', () => Math.min(pageCount, page + 1), page === pageCount);
    }
    render();
  });
})();

// ── flash → 右上角 toast（4.5s 自动消失，可点击关闭）────────────
(function () {
  const stack = document.getElementById('toast-stack');
  if (!stack) return;
  const fires = Array.from(document.querySelectorAll('.alert'));
  fires.forEach((el) => {
    const toast = document.createElement('div');
    toast.className = 'toast ' + (el.classList.contains('alert-warn') ? 'toast-warn' : 'toast-ok');
    toast.textContent = el.textContent.trim();
    toast.title = '点击关闭';
    toast.addEventListener('click', () => toast.remove());
    stack.appendChild(toast);
    el.remove();
    setTimeout(() => {
      toast.classList.add('toast-out');
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  });
})();

// ── 表格密度（紧凑/默认/宽松，全局记忆）──────────────────────
(function () {
  const MODES = [['compact', '紧凑'], ['default', '默认'], ['relaxed', '宽松']];
  const saved = localStorage.getItem('qb.density') || 'default';
  function apply(table, mode) {
    table.classList.toggle('table-sm', mode === 'compact');
    table.classList.toggle('table-relaxed', mode === 'relaxed');
  }
  document.querySelectorAll('.panel table.table').forEach((table) => {
    if (table.dataset.noTools) return;
    if (!table.tBodies[0] || table.tBodies[0].rows.length < 8) return;
    const bar = document.createElement('div');
    bar.className = 'table-tools';
    bar.innerHTML = '<span class="muted small">密度</span>';
    const seg = document.createElement('div');
    seg.className = 'seg';
    MODES.forEach(([mode, label]) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'seg-btn' + (mode === saved ? ' active' : '');
      b.textContent = label;
      b.addEventListener('click', () => {
        localStorage.setItem('qb.density', mode);
        seg.querySelectorAll('.seg-btn').forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        document.querySelectorAll('.panel table.table').forEach((tb) => apply(tb, mode));
      });
      seg.appendChild(b);
    });
    bar.appendChild(seg);
    table.parentNode.insertBefore(bar, table);
    apply(table, saved);
  });
})();

// ── 峰谷：概率滑块显示（0 = 不覆盖）──────────────────────────
(function () {
  function bindProb(card) {
    const range = card.querySelector('.pv-range');
    const out = card.querySelector('.pv-prob-val');
    if (!range || !out) return;
    const render = () => {
      const v = Number(range.value);
      out.textContent = v > 0 ? v + '%' : '不覆盖';
    };
    range.addEventListener('input', render);
    render();
  }
  document.querySelectorAll('.pv-card').forEach(bindProb);
  document.getElementById('add-row')?.addEventListener('click', () => {
    setTimeout(() => {
      const cards = document.querySelectorAll('#periods-table .pv-card');
      if (cards.length) bindProb(cards[cards.length - 1]);
    }, 0);
  });
})();

// ── 复制会话 ID ─────────────────────────────────────────────
(function () {
  document.querySelectorAll('.copy-key').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const text = btn.dataset.key || '';
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = '已复制';
        setTimeout(() => { btn.textContent = '复制 ID'; }, 1500);
      } catch (e) {
        btn.textContent = '复制失败';
      }
    });
  });
})();

// ── 设置页：ID 计数 + 未保存提示 ─────────────────────────────
(function () {
  const form = document.getElementById('settings-form');
  if (!form) return;
  const dirty = document.getElementById('settings-dirty');
  const countIds = (text) => String(text || '').split(/[,\s]+/).filter((x) => x.trim()).length;
  const refreshCounts = () => {
    form.querySelectorAll('textarea[data-count]').forEach((el) => {
      const label = form.querySelector(`[data-count-for="${el.dataset.count}"]`);
      if (label) label.textContent = countIds(el.value) + ' 个';
    });
  };
  refreshCounts();
  form.addEventListener('input', () => { refreshCounts(); if (dirty) dirty.hidden = false; });
  form.addEventListener('submit', () => { if (dirty) dirty.hidden = true; });
})();

// ── 白名单列表编辑器：增 / 删 / 改（写回隐藏字段）──────────────
(function () {
  const dirty = document.getElementById('settings-dirty');
  const editors = document.querySelectorAll('.list-editor');
  if (!editors.length) return;

  function parse(value) {
    return String(value || '').split(/[,\s]+/).map((s) => s.trim()).filter((s) => /^\d+$/.test(s));
  }

  function initEditor(root) {
    const hidden = root.querySelector('input[type=hidden]');
    const tbody = root.querySelector('tbody');
    const empty = root.querySelector('.le-empty');
    const count = root.querySelector('.le-count');
    const input = root.querySelector('.le-new');
    const addBtn = root.querySelector('.le-add');
    const counter = document.querySelector(`[data-count-for="${root.dataset.name}"]`);
    let items = parse(hidden.value).filter((v, i, a) => a.indexOf(v) === i);
    let editIndex = -1;

    function commit() {
      hidden.value = items.join(',');
      count.textContent = items.length + ' 个';
      if (counter) counter.textContent = items.length;
      if (dirty) dirty.hidden = false;
    }

    function render() {
      tbody.innerHTML = '';
      items.forEach((id, index) => {
        const tr = document.createElement('tr');
        if (editIndex === index) {
          tr.innerHTML = `<td>${index + 1}</td><td><input class="form-control le-edit" value="${id}" inputmode="numeric"></td>` +
            '<td class="text-end"><span class="le-actions"><button type="button" class="btn btn-primary le-save">保存</button><button type="button" class="btn btn-text le-cancel">取消</button></span></td>';
          tbody.appendChild(tr);
          const box = tr.querySelector('.le-edit');
          box.focus();
          box.select();
          box.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); save(box.value); } if (e.key === 'Escape') { editIndex = -1; render(); } });
          tr.querySelector('.le-save').addEventListener('click', () => save(box.value));
          tr.querySelector('.le-cancel').addEventListener('click', () => { editIndex = -1; render(); });
          return;
        }
        tr.innerHTML = `<td>${index + 1}</td><td class="le-id">${id}</td>` +
          '<td class="text-end"><span class="le-actions"><button type="button" class="btn btn-outline-secondary le-edit">编辑</button><button type="button" class="btn btn-link text-danger p-0 le-del">删除</button></span></td>';
        tbody.appendChild(tr);
        tr.querySelector('.le-edit').addEventListener('click', () => { editIndex = index; render(); });
        tr.querySelector('.le-del').addEventListener('click', () => {
          items.splice(index, 1);
          editIndex = -1;
          commit();
          render();
        });
      });
      if (empty) empty.hidden = items.length > 0;
      count.textContent = items.length + ' 个';
      if (counter) counter.textContent = items.length;
    }

    function save(value) {
      const v = String(value || '').trim();
      if (!/^\d+$/.test(v)) { input.focus(); return; }
      if (items.some((x, i) => x === v && i !== editIndex)) { editIndex = -1; render(); return; }
      items[editIndex] = v;
      editIndex = -1;
      commit();
      render();
    }

    function add() {
      const v = String(input.value || '').trim();
      if (!/^\d+$/.test(v)) { input.focus(); return; }
      if (!items.includes(v)) { items.push(v); commit(); render(); }
      input.value = '';
      input.focus();
    }

    addBtn.addEventListener('click', add);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } });
    render();
  }

  editors.forEach(initEditor);
})();

// ── 用量图 tooltip ─────────────────────────────────────────
(function () {
  const tip = document.getElementById('ubar-tip');
  if (!tip) return;
  document.querySelectorAll('.ubar-wrap').forEach((bar) => {
    bar.addEventListener('mouseenter', () => {
      const d = bar.dataset;
      tip.innerHTML = '<div>' + d.time + ' · <span class="' + (d.peak === '1' ? 'tip-peak' : 'tip-off') + '">' + d.period + '</span></div>' +
        '<div>tokens <b>' + d.tokens + '</b></div><div>费用 <b>¥' + d.cost + '</b></div>';
      tip.hidden = false;
    });
    bar.addEventListener('mousemove', (e) => {
      tip.style.left = Math.min(window.innerWidth - 200, e.clientX + 14) + 'px';
      tip.style.top = (e.clientY + 16) + 'px';
    });
    bar.addEventListener('mouseleave', () => { tip.hidden = true; });
  });
})();

// ── 峰谷：分群限额编辑 ────────────────────────────────────────
(function () {
  const list = document.getElementById('periods-table');
  const form = document.getElementById('periods-form');
  if (!list || !form) return;

  const rowHtml = (groups = '', minute = '', hour = '') =>
    '<input class="pv-input gl-groups" value="' + groups + '" placeholder="群号，逗号分隔">' +
    '<input class="pv-input gl-minute" type="number" min="1" value="' + minute + '" placeholder="每分钟">' +
    '<input class="pv-input gl-hour" type="number" min="1" value="' + hour + '" placeholder="每小时">' +
    '<button class="pv-del gl-del" type="button">删除</button>';

  function syncSpec(row) {
    const items = [];
    row.querySelectorAll('.gl-row').forEach((item) => {
      const groups = (item.querySelector('.gl-groups')?.value || '').trim();
      const minute = (item.querySelector('.gl-minute')?.value || '').trim();
      const hour = (item.querySelector('.gl-hour')?.value || '').trim();
      if (!groups || (!minute && !hour)) return;
      items.push(groups + ':' + (minute || '0') + ':' + (hour || '0'));
    });
    const spec = row.querySelector('.gl-spec');
    if (spec) spec.value = items.join(';');
  }

  function initRow(row) {
    row.querySelectorAll('.gl-row').forEach((item) => {
      item.querySelectorAll('input').forEach((input) => input.addEventListener('input', () => syncSpec(row)));
    });
    syncSpec(row);
  }

  list.querySelectorAll('.period-row').forEach(initRow);

  list.addEventListener('click', (event) => {
    const add = event.target.closest('.gl-add');
    if (add) {
      const row = add.closest('.period-row');
      const box = row?.querySelector('.gl-list');
      if (!row || !box) return;
      const item = document.createElement('div');
      item.className = 'gl-row';
      item.innerHTML = rowHtml();
      box.appendChild(item);
      item.querySelectorAll('input').forEach((input) => input.addEventListener('input', () => syncSpec(row)));
      item.querySelector('.gl-groups')?.focus();
      return;
    }
    const del = event.target.closest('.gl-del');
    if (del) {
      const row = del.closest('.period-row');
      del.closest('.gl-row')?.remove();
      if (row) syncSpec(row);
    }
  });

  form.addEventListener('submit', () => {
    list.querySelectorAll('.period-row').forEach(syncSpec);
  });
})();

// ── 页面保存类按钮：移动到右上角固定操作条 ──────────────────
(function () {
  const isPageAction = (btn) => /保存|计算命中|创建|应用/.test(btn.textContent || '');
  const buttons = [...document.querySelectorAll('button[type="submit"].btn-primary')]
    .filter((btn) => isPageAction(btn) && !btn.closest('table') && !btn.closest('.inline') && !btn.closest('.star-form'));
  if (!buttons.length || document.querySelector('.page-actions')) return;

  const byForm = new Map();
  for (const btn of buttons) {
    const form = btn.form || btn.closest('form');
    if (!form) continue;
    if (!byForm.has(form)) byForm.set(form, []);
    byForm.get(form).push(btn);
  }

  const bar = document.createElement('div');
  bar.className = 'page-actions';
  bar.setAttribute('role', 'toolbar');
  bar.setAttribute('aria-label', '本页操作');

  let index = 0;
  for (const [form, list] of byForm) {
    if (!form.id) form.id = 'page-form-' + index++;
    const source = list[0];
    const clone = source.cloneNode(true);
    clone.setAttribute('form', form.id);
    if (source.disabled) clone.disabled = true;
    bar.appendChild(clone);
    list.forEach((btn) => btn.classList.add('is-moved'));
  }
  if (bar.children.length) document.body.appendChild(bar);
})();
