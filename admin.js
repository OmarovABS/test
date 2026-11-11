(function () {
  'use strict';

  var root = null;
  var adminOpen = false;
  var editingProductId = null;
  var adminUser = false;

  function telegramHeaders() {
    var tg = window.Telegram && window.Telegram.WebApp;
    var headers = {};
    if (tg && tg.initData) headers['X-Telegram-Init-Data'] = tg.initData;
    return headers;
  }

  async function api(url, options) {
    var request = options || {};
    request.headers = Object.assign({}, telegramHeaders(), request.headers || {});
    var response = await fetch(url, request);
    if (!response.ok) {
      var errorBody = {};
      try { errorBody = await response.json(); } catch (e) {}
      throw new Error(errorBody.detail || 'Ошибка запроса (' + response.status + ')');
    }
    if (response.status === 204) return null;
    return response.json();
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
    });
  }

  function money(value) {
    return new Intl.NumberFormat('ru-RU').format(Number(value) || 0) + ' сум';
  }

  function toast(message) {
    var element = document.getElementById('pf-admin-toast');
    if (!element) return;
    element.textContent = message;
    element.style.display = 'block';
    clearTimeout(toast.timer);
    toast.timer = setTimeout(function () { element.style.display = 'none'; }, 3000);
  }

  function setAdminView(open) {
    adminOpen = open;
    var panel = document.getElementById('pf-admin-panel');
    var toggle = document.getElementById('pf-admin-toggle');
    var storefront = document.querySelector('.app');
    if (panel) panel.classList.toggle('pf-open', open);
    if (storefront) storefront.style.display = open ? 'none' : '';
    if (toggle) toggle.textContent = open ? 'На витрину' : 'Админка';
    if (open) {
      loadProducts();
      loadOrders();
    } else if (window.PF && typeof window.PF.refreshMenu === 'function') {
      window.PF.refreshMenu().catch(function () {});
    }
  }

  async function loadProducts() {
    var list = document.getElementById('pf-admin-products');
    if (!list) return;
    list.innerHTML = '<div class="pf-admin-status">Загрузка блюд…</div>';
    try {
      var result = await api('/api/admin/products');
      var products = result.products || [];
      if (!products.length) {
        list.innerHTML = '<div class="pf-admin-empty">В меню пока нет блюд.</div>';
        return;
      }
      list.innerHTML = products.map(function (product) {
        var image = product.image_url || '';
        return '<article class="pf-admin-product" data-id="' + Number(product.id) + '">' +
          (image ? '<img src="' + escapeHtml(image) + '" alt="">' : '<img src="" alt="Нет фото">') +
          '<div class="pf-admin-product-main"><strong>' + escapeHtml(product.name) + '</strong>' +
          '<small>' + escapeHtml(product.category) + ' · ' + money(product.price) + '</small></div>' +
          '<div class="pf-admin-controls"><label class="pf-admin-toggle-switch"><input type="checkbox" data-action="active" ' + (product.is_active ? 'checked' : '') + '><span>' + (product.is_active ? 'В наличии' : 'Стоп-лист') + '</span></label>' +
          '<button class="pf-admin-mini" type="button" data-action="edit">Редактировать</button>' +
          '<button class="pf-admin-mini danger" type="button" data-action="delete">Удалить</button></div></article>';
      }).join('');
      products.forEach(function (product) {
        var row = list.querySelector('[data-id="' + Number(product.id) + '"]');
        if (row) row.__product = product;
      });
    } catch (error) {
      list.innerHTML = '<div class="pf-admin-empty">' + escapeHtml(error.message) + '</div>';
    }
  }

  async function loadOrders() {
    var list = document.getElementById('pf-admin-orders');
    if (!list) return;
    list.innerHTML = '<div class="pf-admin-status">Загрузка заказов…</div>';
    try {
      var result = await api('/api/admin/orders');
      var stats = result.today || {};
      document.getElementById('pf-stat-count').textContent = stats.count || 0;
      document.getElementById('pf-stat-revenue').textContent = money(stats.revenue || 0);
      var orders = result.orders || [];
      if (!orders.length) {
        list.innerHTML = '<div class="pf-admin-empty">Пока заказов нет.</div>';
        return;
      }
      list.innerHTML = orders.map(function (order) {
        var lines = (order.items || []).map(function (item) {
          return item.name + ' × ' + item.qty + ' — ' + money(item.price * item.qty);
        }).join('\n');
        return '<article class="pf-admin-order"><div><strong>Заказ #' + Number(order.id) + ' · ' + escapeHtml(order.username ? '@' + order.username : 'Клиент ' + order.user_id) + '</strong>' +
          '<small>' + escapeHtml(order.created_at || '') + (order.phone ? ' · ' + escapeHtml(order.phone) : '') + '</small>' +
          '<div class="pf-admin-order-items">' + escapeHtml(lines) + '\nАдрес: ' + escapeHtml(order.address || 'Не указан') +
          (order.comment ? '\nКомментарий: ' + escapeHtml(order.comment) : '') + '</div></div>' +
          '<div class="pf-admin-order-total">' + money(order.total_price) + '</div></article>';
      }).join('');
    } catch (error) {
      list.innerHTML = '<div class="pf-admin-empty">' + escapeHtml(error.message) + '</div>';
    }
  }

  function openProductForm(product) {
    var form = document.getElementById('pf-admin-form');
    var modal = document.getElementById('pf-admin-modal');
    editingProductId = product ? product.id : null;
    form.reset();
    form.elements.name.value = product ? product.name : '';
    form.elements.description.value = product ? product.description : '';
    form.elements.price.value = product ? product.price : '';
    form.elements.category.value = product ? product.category : '';
    form.elements.image_url.value = product && /^https?:\/\//i.test(product.image_url || '') ? product.image_url : '';
    form.elements.is_active.checked = product ? Boolean(product.is_active) : true;
    var preview = document.getElementById('pf-admin-image-preview');
    var previewImg = preview ? preview.querySelector('img') : null;
    if (preview && previewImg) {
      if (product && product.image_url) {
        previewImg.src = product.image_url;
        preview.style.display = 'block';
      } else {
        previewImg.removeAttribute('src');
        preview.style.display = 'none';
      }
    }
    document.getElementById('pf-admin-modal-title').textContent = product ? 'Редактировать блюдо' : 'Новое блюдо';
    modal.classList.add('open');
  }

  function bindEvents() {
    document.getElementById('pf-admin-toggle').addEventListener('click', function () { setAdminView(!adminOpen); });
    document.getElementById('pf-admin-reload').addEventListener('click', function () { loadProducts(); loadOrders(); });
    document.getElementById('pf-admin-add').addEventListener('click', function () { openProductForm(null); });
    document.getElementById('pf-admin-cancel').addEventListener('click', function () { document.getElementById('pf-admin-modal').classList.remove('open'); });
    document.getElementById('pf-admin-modal').addEventListener('click', function (event) {
      if (event.target.id === 'pf-admin-modal') event.currentTarget.classList.remove('open');
    });
    Array.prototype.forEach.call(document.querySelectorAll('.pf-admin-tab'), function (button) {
      button.addEventListener('click', function () {
        document.querySelectorAll('.pf-admin-tab').forEach(function (tab) { tab.classList.toggle('active', tab === button); });
        document.getElementById('pf-admin-products-view').hidden = button.dataset.tab !== 'products';
        document.getElementById('pf-admin-orders-view').hidden = button.dataset.tab !== 'orders';
        if (button.dataset.tab === 'orders') loadOrders(); else loadProducts();
      });
    });
    document.getElementById('pf-admin-products').addEventListener('click', async function (event) {
      var button = event.target.closest('[data-action]');
      if (!button) return;
      var row = button.closest('[data-id]');
      if (!row) return;
      var id = Number(row.dataset.id);
      if (button.dataset.action === 'edit') openProductForm(row.__product);
      if (button.dataset.action === 'delete' && window.confirm('Удалить блюдо «' + row.__product.name + '»?')) {
        try { await api('/api/admin/products/' + id, { method: 'DELETE' }); toast('Блюдо удалено'); loadProducts(); }
        catch (error) { toast(error.message); }
      }
    });
    document.getElementById('pf-admin-products').addEventListener('change', async function (event) {
      var input = event.target;
      if (!input.matches('[data-action="active"]')) return;
      var row = input.closest('[data-id]');
      var label = input.parentElement.querySelector('span');
      try {
        await api('/api/admin/products/' + Number(row.dataset.id), {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_active: input.checked })
        });
        label.textContent = input.checked ? 'В наличии' : 'Стоп-лист';
        row.__product.is_active = input.checked;
        toast(input.checked ? 'Блюдо снова доступно' : 'Блюдо добавлено в стоп-лист');
      } catch (error) {
        input.checked = !input.checked;
        toast(error.message);
      }
    });
    document.getElementById('pf-admin-form').addEventListener('submit', async function (event) {
      event.preventDefault();
      var form = event.currentTarget;
      var data = new FormData(form);
      data.set('is_active', form.elements.is_active.checked ? 'true' : 'false');
      try {
        await api(editingProductId ? '/api/admin/products/' + editingProductId : '/api/admin/products', {
          method: editingProductId ? 'PUT' : 'POST', body: data
        });
        document.getElementById('pf-admin-modal').classList.remove('open');
        toast(editingProductId ? 'Изменения сохранены' : 'Блюдо добавлено');
        loadProducts();
        if (window.PF && window.PF.refreshMenu) window.PF.refreshMenu().catch(function () {});
      } catch (error) { toast(error.message); }
    });
  }

  async function initialize() {
    try {
      var response = await fetch('/backend/admin_snippet.html', { cache: 'no-store' });
      if (!response.ok) return;
      var markup = await response.text();
      var template = document.createElement('template');
      template.innerHTML = markup;
      root = template.content;
      document.body.appendChild(root);
      var me = await api('/api/me');
      adminUser = Boolean(me.is_admin);
      if (!adminUser) {
        document.getElementById('pf-admin-root').remove();
        return;
      }
      document.getElementById('pf-admin-toggle').style.display = 'block';
      bindEvents();
    } catch (error) {
      // Do not disrupt the customer storefront if the API is unavailable.
      console.warn('Admin panel unavailable:', error.message);
    }
  }

  initialize();
})();
