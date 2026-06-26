const API_URL = '/api';
console.log('app.js v7 loaded');

// Helper to generate dynamic local SVG avatar when offline
function getLocalAvatarUrl(name, bgColor = '0D8ABC') {
    const parts = name.trim().split(/\s+/);
    let initials = '';
    if (parts.length > 0 && parts[0]) {
        initials += parts[0][0];
        if (parts.length > 1 && parts[parts.length - 1]) {
            initials += parts[parts.length - 1][0];
        }
    }
    initials = initials.toUpperCase() || 'U';
    
    // Choose dynamic color if bgColor is 'random'
    if (bgColor === 'random') {
        const colors = ['0D8ABC', '10b981', '6366f1', 'f59e0b', 'ef4444', 'ec4899', '8b5cf6'];
        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        bgColor = colors[Math.abs(hash) % colors.length];
    }
    
    const hexColor = bgColor.replace('#', '');
    return `data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23${hexColor}'/><text x='50%' y='54%' font-family='sans-serif' font-weight='bold' font-size='38' fill='%23ffffff' dominant-baseline='middle' text-anchor='middle'>${initials}</text></svg>`;
}
let SYSTEM_SETTINGS = {
    hospital_name: 'Ghana National Hospital',
    nhis_id: 'GHA-NHIS-9921',
    expiry_threshold: 30,
    exchange_rate: 1.0,
    currency: 'GH₵'
};

document.addEventListener('DOMContentLoaded', () => {
    // Check Authentication
    const isLogin = window.location.pathname.endsWith('login.html');
    const userRole = localStorage.getItem('medai_role');
    
    if (isLogin && userRole) {
        // Redirection Guard: If already logged in, skip the login page
        window.location.href = userRole === 'pharmacist' ? '/pharmacist.html' : '/index.html';
        return;
    }
    
    if (!isLogin && !userRole) {
        window.location.href = '/login.html';
        return;
    }
    
    // RBAC: Pharmacist Route Guards
    const path = window.location.pathname;
    if (userRole === 'pharmacist' && !isLogin) {
        const allowedPharmacistPages = ['/pharmacist.html', '/pos.html', '/inventory.html', '/refunds.html'];
        if (!allowedPharmacistPages.includes(path) && path !== '/') { // if they try to access reports/index/settings/audit/users
            window.location.href = '/pharmacist.html';
            return;
        }
    }
    
    // User Profile display update
    updateProfileDisplay(userRole);

    handleLogoutBinding();

    // Collapsible sidebar
    initSidebarToggle();

    // Determine which page we are on
    if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/') {
        loadDashboardData();
        loadRecommendations();
        loadCharts();
    } else if (window.location.pathname.endsWith('forecasting.html')) {
        loadForecasting();
    } else if (window.location.pathname.endsWith('pharmacist.html')) {
        loadPharmacistPersonalDashboard();
        loadRecommendations(); // internal alerts list
    } else if (window.location.pathname.endsWith('reports.html')) {
        loadReports();
    } else if (window.location.pathname.endsWith('inventory.html')) {
        // inventory.html handles loading itself
    } else if (window.location.pathname.endsWith('pos.html')) {
        initPOS();
    } else if (window.location.pathname.endsWith('users.html')) {
        loadUsers();
    } else if (window.location.pathname.endsWith('audit.html')) {
        loadAuditLogs();
    }

    // Load Global Settings
    loadGlobalSettings();

    // --- REAL-TIME SYNC: Refresh data every 30s ---
    setInterval(() => {
        if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/') {
            loadDashboardData();
        } else if (window.location.pathname.endsWith('pharmacist.html')) {
            loadPharmacistPersonalDashboard();
        } else if (window.location.pathname.endsWith('inventory.html')) {
            loadInventory();
        } else if (window.location.pathname.endsWith('users.html')) {
            loadUsers();
        } else if (window.location.pathname.endsWith('audit.html')) {
            loadAuditLogs();
        }
    }, 30000); // 30 seconds
});

// ──────────────────────────────────────────────
// COLLAPSIBLE SIDEBAR
// ──────────────────────────────────────────────
function initSidebarToggle() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;

    // Wrap bare text nodes inside nav links with <span class="nav-label">
    // so CSS can hide them without affecting the icon
    document.querySelectorAll('.nav-links a').forEach(link => {
        link.childNodes.forEach(node => {
            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                const span = document.createElement('span');
                span.className = 'nav-label';
                span.textContent = node.textContent;
                node.replaceWith(span);
            }
        });
    });

    // Create toggle button and inject it into the sidebar
    const toggleBtn = document.createElement('button');
    toggleBtn.id = 'sidebar-toggle';
    toggleBtn.setAttribute('title', 'Toggle sidebar');
    toggleBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
    sidebar.appendChild(toggleBtn);

    // Apply saved collapsed state
    const isCollapsed = localStorage.getItem('sidebar_collapsed') === 'true';
    const mainContent = document.querySelector('.main-content');
    if (isCollapsed) {
        sidebar.classList.add('collapsed');
        if (mainContent) mainContent.classList.add('sidebar-collapsed');
        toggleBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
    }

    // Toggle on click
    toggleBtn.addEventListener('click', () => {
        const collapsed = sidebar.classList.toggle('collapsed');
        if (mainContent) mainContent.classList.toggle('sidebar-collapsed', collapsed);
        toggleBtn.innerHTML = collapsed
            ? '<i class="fa-solid fa-chevron-right"></i>'
            : '<i class="fa-solid fa-chevron-left"></i>';
        localStorage.setItem('sidebar_collapsed', collapsed);
    });
}

function toggleTheme() {
    document.body.classList.toggle('dark-theme');
    const isDark = document.body.classList.contains('dark-theme');
    localStorage.setItem('medai_theme', isDark ? 'dark' : 'light');
}

// Check theme on load
if (localStorage.getItem('medai_theme') === 'dark') {
    document.body.classList.add('dark-theme');
}

async function handleLogoutBinding() {
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            const username = localStorage.getItem('medai_username');
            if (username) {
                await fetch(`${API_URL}/logout`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username })
                });
            }
            // Exhaustive Session Clear
            localStorage.clear(); 
            window.location.href = '/login.html';
        });
    }
}

async function updateProfileDisplay(role) {
    const roleTexts = document.querySelectorAll('.user-role-text');
    const nameTexts = document.querySelectorAll('.user-name-text');
    
    roleTexts.forEach(el => el.textContent = role === 'admin' ? 'System Admin' : 'Pharmacist');
    const username = localStorage.getItem('medai_username') || 'User';
    nameTexts.forEach(el => el.textContent = username);

    // NAVIGATION VISIBILITY Logic (Executed Synchronously)
    const adminOnlyEls = document.querySelectorAll('.admin-only');
    const pharmOnlyEls = document.querySelectorAll('.pharm-only');
    
    if (role === 'pharmacist') {
        adminOnlyEls.forEach(el => el.style.display = 'none');
        pharmOnlyEls.forEach(el => el.style.display = 'block');
    } else {
        // Admin oversees management, but operational tasks are for pharmacists
        adminOnlyEls.forEach(el => el.style.display = 'block');
        pharmOnlyEls.forEach(el => el.style.display = 'none');
    }
    
    // Fetch live profile details from database to avoid stale localStorage!
    let profilePic = localStorage.getItem('medai_profile_pic');
    try {
        const users = await fetchAPI('/users');
        if (users) {
            const currentUser = users.find(u => u.username === username);
            if (currentUser && currentUser.profile_pic) {
                profilePic = currentUser.profile_pic;
                localStorage.setItem('medai_profile_pic', profilePic);
            }
        }
    } catch (e) {
        console.error("Error fetching live profile picture:", e);
    }
    
    const profileImgs = document.querySelectorAll('.user-profile img, .user-profile-img');
    profileImgs.forEach(img => {
        if (profilePic && profilePic !== 'null') {
            img.src = profilePic;
        } else {
            img.src = getLocalAvatarUrl(username, '0D8ABC');
        }
    });
}

async function loadGlobalSettings() {
    const res = await fetch(`${API_URL}/settings`);
    const data = await res.json();
    if (data) {
        SYSTEM_SETTINGS = data;
        // Update any static titles if present
        const reportTitle = document.getElementById('report-facility-title');
        if (reportTitle) reportTitle.textContent = `${data.hospital_name} - Stock Valuation & Alert Summary`;
    }
}

async function fetchAPI(endpoint) {
    try {
        const res = await fetch(`${API_URL}${endpoint}`);
        if (res.status === 401) {
            // SESSION EXPIRED OR INVALID
            localStorage.removeItem('medai_role');
            localStorage.removeItem('medai_username');
            window.location.href = '/login.html';
            return null;
        }
        if (!res.ok) throw new Error('API Error');
        return await res.json();
    } catch (err) {
        console.error('Fetch Error:', err);
        return null;
    }
}

// ---------------- ADD PRODUCT MODAL ----------------

function openAddProductModal() {
    document.getElementById('add-product-modal').style.display = 'flex';
    // Set minimum expiry date to tomorrow
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const minDate = tomorrow.toISOString().split('T')[0];
    document.getElementById('ap-expiry-date').min = minDate;
}

function closeAddProductModal() {
    document.getElementById('add-product-modal').style.display = 'none';
    // Clear all fields
    ['ap-name','ap-manufacturer','ap-mfg-date','ap-qty','ap-reorder','ap-cost','ap-price','ap-expiry-date','ap-sales'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = id === 'ap-sales' ? '0' : '';
    });
    const errEl = document.getElementById('ap-error');
    if (errEl) errEl.style.display = 'none';
}

async function saveNewProduct() {
    const name     = document.getElementById('ap-name').value.trim();
    const category = document.getElementById('ap-category').value;
    const mfr      = document.getElementById('ap-manufacturer').value.trim();
    const mfgDate  = document.getElementById('ap-mfg-date').value;
    const qty      = parseInt(document.getElementById('ap-qty').value);
    const reorder  = parseInt(document.getElementById('ap-reorder').value);
    const cost     = parseFloat(document.getElementById('ap-cost').value);
    const price    = parseFloat(document.getElementById('ap-price').value);
    const expiryDate = document.getElementById('ap-expiry-date').value;
    const sales    = parseInt(document.getElementById('ap-sales').value) || 0;

    const errEl = document.getElementById('ap-error');

    // Calculate days to expiry from picked date
    let daysExp = 0;
    if (expiryDate) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const expiry = new Date(expiryDate);
        daysExp = Math.round((expiry - today) / (1000 * 60 * 60 * 24));
    }

    if (!name || !mfr || !mfgDate || isNaN(qty) || isNaN(reorder) || isNaN(cost) || isNaN(price) || !expiryDate || daysExp < 1) {
        errEl.textContent = !expiryDate || daysExp < 1
            ? 'Expiry date must be at least 1 day in the future.'
            : 'Please fill in all required fields.';
        errEl.style.display = 'block';
        return;
    }

    const payload = { name, category, manufacturer: mfr, manufacturing_date: mfgDate, qty, reorder, cost, price, days_to_expiry: daysExp, expiry_date: expiryDate, sales_last_30: sales };

    errEl.style.display = 'none';

    const saveBtn = document.querySelector('#add-product-modal .btn[onclick="saveNewProduct()"]');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...'; }

    try {
        const res = await fetch(`${API_URL}/inventory`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            closeAddProductModal();
            loadInventory(); // Refresh the table
        } else {
            errEl.textContent = data.message || 'Failed to save product. Try again.';
            errEl.style.display = 'block';
        }
    } catch (e) {
        errEl.textContent = 'Network error. Please check connection.';
        errEl.style.display = 'block';
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Product'; }
    }
}

function openEditProductModal() {
    document.getElementById('edit-product-modal').style.display = 'flex';
    // Set minimum expiry date to tomorrow
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const minDate = tomorrow.toISOString().split('T')[0];
    document.getElementById('ep-expiry-date').min = minDate;
}

function closeEditProductModal() {
    document.getElementById('edit-product-modal').style.display = 'none';
    // Clear all fields
    ['ep-batch-id','ep-name','ep-manufacturer','ep-mfg-date','ep-qty','ep-reorder','ep-cost','ep-price','ep-expiry-date','ep-sales'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = id === 'ep-sales' ? '0' : '';
    });
    const errEl = document.getElementById('ep-error');
    if (errEl) errEl.style.display = 'none';
}

async function editProduct(batchId) {
    // Fetch the product details
    const items = await fetchAPI('/inventory');
    const item = items.find(i => i.Batch_ID === batchId);
    if (!item) return;

    // Populate the edit modal
    document.getElementById('ep-batch-id').value = item.Batch_ID;
    document.getElementById('ep-name').value = item.Medicine_Name;
    document.getElementById('ep-category').value = item.Category;
    document.getElementById('ep-manufacturer').value = item.Manufacturer;
    document.getElementById('ep-mfg-date').value = item.Manufacturing_Date;
    document.getElementById('ep-qty').value = item.Quantity_In_Stock;
    document.getElementById('ep-reorder').value = item.Reorder_Level;
    document.getElementById('ep-cost').value = (item.Cost_Price_USD * (SYSTEM_SETTINGS.exchange_rate || 1.0)).toFixed(2);
    document.getElementById('ep-price').value = (item.Selling_Price_USD * (SYSTEM_SETTINGS.exchange_rate || 1.0)).toFixed(2);
    document.getElementById('ep-expiry-date').value = item.Expiry_Date;
    document.getElementById('ep-sales').value = item.Sales_Last_30_Days || 0;

    openEditProductModal();
}

async function saveEditedProduct() {
    const batchId = document.getElementById('ep-batch-id').value;
    const name     = document.getElementById('ep-name').value.trim();
    const category = document.getElementById('ep-category').value;
    const mfr      = document.getElementById('ep-manufacturer').value.trim();
    const mfgDate  = document.getElementById('ep-mfg-date').value;
    const qty      = parseInt(document.getElementById('ep-qty').value);
    const reorder  = parseInt(document.getElementById('ep-reorder').value);
    const cost     = parseFloat(document.getElementById('ep-cost').value);
    const price    = parseFloat(document.getElementById('ep-price').value);
    const expiryDate = document.getElementById('ep-expiry-date').value;
    const sales    = parseInt(document.getElementById('ep-sales').value) || 0;

    const errEl = document.getElementById('ep-error');

    // Calculate days to expiry from picked date
    let daysExp = 0;
    if (expiryDate) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const expiry = new Date(expiryDate);
        daysExp = Math.round((expiry - today) / (1000 * 60 * 60 * 24));
    }

    if (!name || !mfr || !mfgDate || isNaN(qty) || isNaN(reorder) || isNaN(cost) || isNaN(price) || !expiryDate || daysExp < 1) {
        errEl.textContent = !expiryDate || daysExp < 1
            ? 'Expiry date must be at least 1 day in the future.'
            : 'Please fill in all required fields.';
        errEl.style.display = 'block';
        return;
    }

    const payload = { batchId, name, category, manufacturer: mfr, manufacturing_date: mfgDate, qty, reorder, cost, price, days_to_expiry: daysExp, expiry_date: expiryDate, sales_last_30: sales };

    errEl.style.display = 'none';

    const saveBtn = document.querySelector('#edit-product-modal .btn[onclick="saveEditedProduct()"]');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...'; }

    try {
        const res = await fetch(`${API_URL}/inventory/${batchId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            closeEditProductModal();
            loadInventory(); // Refresh the table
        } else {
            errEl.textContent = data.message || 'Failed to update product. Try again.';
            errEl.style.display = 'block';
        }
    } catch (e) {
        errEl.textContent = 'Network error. Please check connection.';
        errEl.style.display = 'block';
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes'; }
    }
}

async function deleteProduct(batchId) {
    if (!confirm(`Are you sure you want to delete product with Batch ID: ${batchId}? This action cannot be undone.`)) {
        return;
    }

    try {
        const res = await fetch(`${API_URL}/inventory/${batchId}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
            loadInventory(); // Refresh the table
        } else {
            alert(data.message || 'Failed to delete product.');
        }
    } catch (e) {
        alert('Network error. Please check connection.');
    }
}

// ---------------- DASHBOARD ----------------

async function loadDashboardData() {
    const data = await fetchAPI('/dashboard');
    if (!data) return;
    
    // Populate KPI Cards
    document.getElementById('kpi-total').textContent = data.totalItems.toLocaleString();
    
    // Revenue Display
    const revenueEl = document.getElementById('kpi-revenue-today');
    if (revenueEl) {
        revenueEl.textContent = (SYSTEM_SETTINGS?.currency || 'GH₵') + ' ' + (data.todayRevenue || 0).toLocaleString(undefined, {minimumFractionDigits: 2});
    }

    // Correctly map Stock Value
    const stockValueGHS = (data.totalStockValue || 0) * (SYSTEM_SETTINGS?.exchange_rate || 1.0);
    document.getElementById('kpi-value').textContent = (SYSTEM_SETTINGS?.currency || 'GH₵') + ' ' + stockValueGHS.toLocaleString(undefined, {minimumFractionDigits: 2});
    
    document.getElementById('kpi-low-stock').textContent = data.lowStockCount.toLocaleString();
    document.getElementById('kpi-expiry').textContent = data.expiredOrNearExpiryCount.toLocaleString();

    // POPULATE DASHBOARD AUDIT FEED
    const auditBody = document.getElementById('dashboard-audit-body');
    if (auditBody) {
        const logs = await fetchAPI('/admin/audit');
        if (logs) {
            auditBody.innerHTML = logs.slice(0, 5).map(l => `
                <tr>
                    <td><small>${new Date(l.timestamp).toLocaleTimeString()}</small></td>
                    <td><strong>${l.username}</strong></td>
                    <td>${l.event}: ${l.details || l.role || ''}</td>
                </tr>
            `).join('');
        }
    }
}

// ---------------- PHARMACIST PERSONAL DASHBOARD ----------------
// Each pharmacist sees ONLY their own data — not other staff's actions.

async function loadPharmacistPersonalDashboard() {
    const myUsername = localStorage.getItem('medai_username');
    if (!myUsername) return;

    // KPI: My Today's Revenue (filtered to this user only)
    const salesEl = document.getElementById('pharm-sales-today');
    const txnEl   = document.getElementById('pharm-txn-count');
    
    try {
        const res = await fetch(`${API_URL}/sales/today?pharmacist=${encodeURIComponent(myUsername)}`);
        const data = await res.json();
        if (salesEl) salesEl.textContent = 'GH\u20b5 ' + data.total_revenue_ghs.toLocaleString(undefined, {minimumFractionDigits: 2});
        if (txnEl)   txnEl.textContent   = data.transaction_count + ' Transaction(s) Today';
    } catch(e) {
        if (salesEl) salesEl.textContent = 'GH\u20b5 0.00';
    }

    // Personal Transaction History Table
    const historyBody = document.getElementById('my-sales-body');
    if (!historyBody) return;

    historyBody.innerHTML = '<tr><td colspan="4" class="loading-td"><div class="spinner"></div> Loading your transactions...</td></tr>';

    try {
        const res2 = await fetch(`${API_URL}/my/sales?pharmacist=${encodeURIComponent(myUsername)}`);
        const mySales = await res2.json();
        
        if (!mySales || mySales.length === 0) {
            historyBody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:2rem; color:var(--text-muted);"><i class="fa-solid fa-receipt" style="font-size:2rem; margin-bottom:0.5rem; display:block;"></i>No transactions recorded for your account yet.</td></tr>';
            return;
        }
        
        historyBody.innerHTML = mySales.map(s => `
            <tr>
                <td><small>${new Date(s.timestamp).toLocaleString()}</small></td>
                <td><span title="${s.details || 'N/A'}">${s.items} item(s) <i class="fa-solid fa-circle-info" style="color:var(--primary); font-size:0.7rem;"></i></span></td>
                <td><strong style="color:var(--success);">GH\u20b5 ${s.total_ghs.toFixed(2)}</strong></td>
                <td><span class="badge low"><i class="fa-solid fa-circle-check"></i> Dispensed</span></td>
            </tr>
        `).join('');
    } catch(e) {
        historyBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Could not load your transactions.</td></tr>';
    }
}

async function loadRecommendations() {
    const items = await fetchAPI('/recommendations');
    const listEl = document.getElementById('ai-list');
    
    if (!items || items.length === 0) {
        listEl.innerHTML = '<li>No high-risk items requiring immediate action.</li>';
        return;
    }

    listEl.innerHTML = items.map(item => {
        const raw_exhaust = item.ML_Predicted_Days_To_Exhaust;
        const exhaust = (raw_exhaust === "Unlimited" || !raw_exhaust) ? "Unlimited" : parseFloat(raw_exhaust).toFixed(1);
        const consume = parseFloat(item.ML_Predicted_Consumption || 0).toFixed(2);
        
        return `
        <li class="rec-item">
            <div class="rec-item-title">
                ${item.Medicine_Name} 
                <span class="badge danger">${item.Expiry_Risk_Level}</span>
            </div>
            <div class="rec-item-desc">
                <strong>Batch:</strong> ${item.Batch_ID} | <strong>Expires in:</strong> ${item.Days_to_Expiry} days
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
                <div class="rec-item-desc" style="color: var(--text-main); font-weight: 500;">
                    <i class="fa-solid fa-triangle-exclamation"></i> Must be reprioritized.
                </div>
                <button class="btn-small" style="background:rgba(14, 165, 233, 0.1); color:var(--primary);" onclick="openXAIModal('${item.Medicine_Name}', '${item.Batch_ID}', '${exhaust}', ${item.Days_to_Expiry}, ${consume}, '${item.Expiry_Risk_Level}')">
                    <i class="fa-solid fa-brain"></i> View Insight
                </button>
            </div>
        </li>
        `;
    }).join('');
}

async function loadCharts() {
    const ctx = document.getElementById('categoryChart');
    if (!ctx) return;

    const riskData = await fetchAPI('/charts/risk');
    if (!riskData) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: riskData.map(d => d.name),
            datasets: [{
                data: riskData.map(d => d.stock),
                backgroundColor: [
                    'rgba(14, 165, 233, 0.8)',
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(239, 68, 68, 0.8)',
                    'rgba(99, 102, 241, 0.8)'
                ],
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'right' }
            },
            cutout: '75%'
        }
    });
}

// ---------------- INVENTORY ----------------

async function loadInventory(searchQuery = '') {
    const tbody = document.getElementById('inventory-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="12" class="loading-td"><div class="spinner"></div> Loading inventory...</td></tr>';
    
    const query = searchQuery ? `?search=${encodeURIComponent(searchQuery)}` : '';
    const items = await fetchAPI(`/inventory${query}`);
    
    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;">No items found.</td></tr>';
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td><strong>${item.Batch_ID}</strong></td>
            <td>${item.Medicine_Name}</td>
            <td>${item.Category}</td>
            <td>${item.Quantity_In_Stock} <small style="color:var(--text-muted)">/ ${item.Reorder_Level} (min)</small></td>
            <td>
                <span style="color:var(--text-muted); font-size: 0.9rem;">
                    ${SYSTEM_SETTINGS.currency} ${((item.Unit_Cost_USD || 0) * (SYSTEM_SETTINGS.exchange_rate || 1.0)).toFixed(2)}
                </span>
            </td>
            <td>
                <span style="font-weight:600;color:var(--primary);">
                    ${SYSTEM_SETTINGS.currency} ${((item.Selling_Price_USD || 0) * (SYSTEM_SETTINGS.exchange_rate || 1.0)).toFixed(2)}
                </span>
            </td>
            <td>
                <span style="font-weight:600;color:var(--success);">
                    ${SYSTEM_SETTINGS.currency} ${((item.Quantity_In_Stock || 0) * (item.Selling_Price_USD || 0) * (SYSTEM_SETTINGS.exchange_rate || 1.0)).toFixed(2)}
                </span>
            </td>
            <td>
                ${(() => {
                    let d = new Date();
                    d.setDate(d.getDate() + item.Days_to_Expiry);
                    return d.toLocaleDateString();
                })()}
                <br>
                <small style="color:${item.Days_to_Expiry <= 30 ? 'var(--danger)' : 'var(--text-muted)'}">
                    ${item.Days_to_Expiry} days left
                </small>
            </td>
            <td><span class="badge ${getRiskClass(item.Expiry_Risk_Level)}">${item.Expiry_Risk_Level}</span></td>
            <td><small>${item.AI_Recommendation}</small></td>
            <td><svg id="barcode-${item.Batch_ID}"></svg></td>
            <td class="actions-col">
                <button class="btn btn-sm" onclick="editProduct('${item.Batch_ID}')" style="background:var(--warning);color:white;margin-right:5px;"><i class="fa-solid fa-edit"></i> Edit</button>
                <button class="btn btn-sm" onclick="deleteProduct('${item.Batch_ID}')" style="background:var(--danger);color:white;"><i class="fa-solid fa-trash"></i> Delete</button>
            </td>
        </tr>
    `).join('');
    
    // Generate barcodes for all items
    items.forEach(item => {
        try {
            JsBarcode(`#barcode-${item.Batch_ID}`, item.Batch_ID, {
                format: "CODE128",
                width: 1,
                height: 30,
                displayValue: false
            });
        } catch(e) {}
    });
}

// ---------------- FORECASTING ----------------

async function loadForecasting(searchQuery = '') {
    const tbody = document.getElementById('forecast-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="loading-td"><div class="spinner"></div> Forecasting demand...</td></tr>';
    
    const query = searchQuery ? `?search=${encodeURIComponent(searchQuery)}` : '';
    const items = await fetchAPI(`/forecast${query}`);
    
    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">No items found.</td></tr>';
        return;
    }

    tbody.innerHTML = items.map(item => {
        let isUnlimited = item.Days_to_Exhaust_Stock === 'Unlimited' || item.Days_to_Exhaust_Stock === null || item.Days_to_Exhaust_Stock === 'Infinity';
        let daysValue = isUnlimited ? Infinity : item.Days_to_Exhaust_Stock;
        
        let riskSpan = '';
        if (daysValue <= 30) riskSpan = '<span class="badge danger">High Exhaust Risk</span>';
        else if (daysValue <= 90) riskSpan = '<span class="badge medium">Moderate Risk</span>';
        else riskSpan = '<span class="badge low">Low Risk</span>';

        return `
        <tr>
            <td><strong>${item.Batch_ID}</strong></td>
            <td>${item.Medicine_Name}</td>
            <td>${item.Quantity_In_Stock}</td>
            <td>${parseFloat(item.Daily_Consumption_Rate).toFixed(2)} units/day</td>
            <td style="font-weight:600; color: ${daysValue <= 30 ? 'var(--danger)' : 'inherit'}">${isUnlimited ? 'Unlimited' : daysValue}</td>
            <td>${isUnlimited ? 'N/A' : new Date(item.Predicted_Stockout_Date).toLocaleDateString()}</td>
            <td>${riskSpan}</td>
        </tr>
    `;
    }).join('');
}

// ---------------- ADMIN ONLY PAGES ----------------

// Cache for loaded users (avoids embedding large base64 data in onclick attrs)
let _usersCache = [];

async function loadUsers() {
    const tbody = document.getElementById('users-body');
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="4" class="loading-td"><div class="spinner"></div> Updating staff registry...</td></tr>';
    
    const users = await fetchAPI('/users');
    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:2rem; color:var(--text-muted);">No staff members found.</td></tr>';
        return;
    }
    
    // Store in cache so onclick handlers can look up profile_pic safely
    _usersCache = users;
    
    tbody.innerHTML = users.map(u => {
        const avatarUrl = getLocalAvatarUrl(u.username, 'random');
        const imgSrc = (u.profile_pic && u.profile_pic !== 'null') ? u.profile_pic : avatarUrl;
        const roleBadge = u.role.toLowerCase() === 'admin' ? 'low' : 'medium';
        const roleLabel = u.role.charAt(0).toUpperCase() + u.role.slice(1);
        return `
        <tr>
            <td>
                <div style="display:flex; align-items:center; gap:10px;">
                    <img src="${imgSrc}" style="width:30px; height:30px; border-radius:50%; object-fit:cover;" onerror="this.src='${avatarUrl}'">
                    <strong>${u.username}</strong>
                </div>
            </td>
            <td><span class="badge ${roleBadge}">${roleLabel}</span></td>
            <td><span style="color:var(--success); font-size:0.85rem;"><i class="fa-solid fa-circle-check"></i> Active</span></td>
            <td>
                <button class="btn-small btn-secondary" onclick="openUserModal('${u.username}')"><i class="fa-solid fa-user-pen"></i> Edit</button>
                <button class="btn-small" style="background:var(--danger); color:white;" onclick="removeUser('${u.username}')"><i class="fa-solid fa-user-minus"></i> Remove</button>
            </td>
        </tr>`;
    }).join('');
}

// Staff Management Logic
let currentEditUser = null;

function openUserModal(username = null) {
    const modal = document.getElementById('user-modal');
    const title = document.getElementById('modal-title');
    const usernameInput = document.getElementById('staff-username');
    const roleInput = document.getElementById('staff-role');
    const passwordInput = document.getElementById('staff-password');
    const errorDiv = document.getElementById('modal-error');
    
    if (!modal) return;
    
    errorDiv.style.display = 'none';
    currentEditUser = username;
    
    if (username) {
        // Look up user data from cache (avoids passing huge base64 data via onclick)
        const userData = _usersCache.find(u => u.username === username);
        const role = userData ? userData.role : 'pharmacist';
        const profilePic = userData ? userData.profile_pic : '';

        title.innerText = 'Edit Staff Member';
        usernameInput.value = username;
        usernameInput.disabled = true;
        roleInput.value = role.toLowerCase();
        passwordInput.value = '';
        passwordInput.placeholder = '(Leave blank to keep current)';

        // Populate image preview from cache
        const preview = document.getElementById('image-preview');
        if (preview) {
            if (profilePic && profilePic !== 'null' && profilePic !== '') {
                preview.innerHTML = `<img src="${profilePic}" style="width:100%; height:100%; object-fit:cover;">`;
            } else {
                preview.innerHTML = '<i class="fa-solid fa-user"></i>';
            }
        }
    } else {
        title.innerText = 'Add New Staff';
        usernameInput.value = '';
        usernameInput.disabled = false;
        roleInput.value = 'pharmacist';
        passwordInput.value = '';
        passwordInput.placeholder = 'Set secure password...';

        const preview = document.getElementById('image-preview');
        if (preview) preview.innerHTML = '<i class="fa-solid fa-user"></i>';
    }
    
    modal.style.display = 'flex';

    const fileInput = document.getElementById('staff-image');
    if (fileInput) {
        fileInput.value = '';
        const preview = document.getElementById('image-preview');
        fileInput.onchange = (e) => {
            const [file] = e.target.files;
            if (file && preview) {
                preview.innerHTML = `<img src="${URL.createObjectURL(file)}" style="width:100%; height:100%; object-fit:cover;">`;
            }
        };
    }
}

function closeUserModal() {
    const modal = document.getElementById('user-modal');
    if (modal) modal.style.display = 'none';
}

// Helper: compress an image File to a small JPEG blob using Canvas
function compressImage(file, maxSize = 300, quality = 0.75) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const scale = Math.min(maxSize / img.width, maxSize / img.height, 1);
                canvas.width  = Math.round(img.width  * scale);
                canvas.height = Math.round(img.height * scale);
                canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
                canvas.toBlob((blob) => resolve(blob), 'image/jpeg', quality);
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

async function saveUser() {
    const username  = document.getElementById('staff-username').value;
    const role      = document.getElementById('staff-role').value;
    const password  = document.getElementById('staff-password').value;
    const errorDiv  = document.getElementById('modal-error');
    const saveBtn   = document.getElementById('modal-save-btn');

    if (!username || (!currentEditUser && !password)) {
        errorDiv.innerText = 'Please fill all required fields.';
        errorDiv.style.display = 'block';
        return;
    }

    // Show loading state
    errorDiv.style.display = 'none';
    if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...'; }

    try {
        const action    = currentEditUser ? 'edit' : 'add';
        const fileInput = document.getElementById('staff-image');

        const formData = new FormData();
        formData.append('username', username);
        formData.append('role', role);
        formData.append('password', password);
        formData.append('action', action);

        // Compress image before uploading (prevents large-file server errors)
        if (fileInput.files[0]) {
            const compressed = await compressImage(fileInput.files[0], 300, 0.75);
            formData.append('profile_pic', compressed, 'avatar.jpg');
        }

        const res    = await fetch(`${API_URL}/admin/users`, { method: 'POST', body: formData });
        const result = await res.json();

        if (result.success) {
            closeUserModal();
            loadUsers();
        } else {
            errorDiv.innerText = result.message || 'Error saving user.';
            errorDiv.style.display = 'block';
        }
    } catch (err) {
        console.error('saveUser error:', err);
        errorDiv.innerText = 'Network error — please check your connection and try again.';
        errorDiv.style.display = 'block';
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = 'Confirm &amp; Save'; }
    }
}

async function removeUser(username) {
    const currentUser = localStorage.getItem('medai_username');
    if (username === currentUser) return alert('You cannot remove your own account.');
    if (!confirm(`Are you sure you want to remove staff member "${username}"? This action is permanent.`)) return;
    
    const res = await fetch(`${API_URL}/admin/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, action: 'delete' })
    });
    
    const result = await res.json();
    if (result.success) {
        loadUsers();
    } else {
        alert(result.message || 'Error deleting user.');
    }
}

async function loadAuditLogs() {
    const container = document.getElementById('session-container');
    if (!container) return;
    
    container.innerHTML = '<div style="text-align:center; padding: 40px; color:var(--text-muted);"><div class="spinner" style="margin: 0 auto 15px;"></div>Reconstructing system sessions...</div>';
    
    const [logs, users] = await Promise.all([
        fetchAPI('/admin/audit'),
        fetchAPI('/users')
    ]);

    if (!logs || logs.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding: 40px; color:var(--text-muted);">No system activity recorded yet.</div>';
        return;
    }

    // Create a lookup for profile pictures
    const userMap = {};
    if (users) {
        users.forEach(u => userMap[u.username] = u.profile_pic);
    }

    // GROUP LOGS BY SESSION
    // A session starts with a Login and ends with matching Logout or next user Login
    const sessions = [];
    let currentSession = null;

    // Logs are newest first, but grouping is easier oldest first
    const sortedLogs = [...logs].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    sortedLogs.forEach(log => {
        if (log.event === 'Login') {
            // Start a new session
            currentSession = {
                id: Math.random().toString(36).substr(2, 9),
                username: log.username,
                role: log.metadata?.role || 'Staff',
                loginTime: log.timestamp,
                logoutTime: null,
                status: 'Active Session',
                actions: [],
                totalRevenue: 0,
                transactions: 0
            };
            sessions.push(currentSession);
        } else if (log.event === 'Logout') {
            // Find the most recent active session for this user
            const session = [...sessions].reverse().find(s => s.username === log.username && s.status === 'Active Session');
            if (session) {
                session.logoutTime = log.timestamp;
                session.status = 'Closed';
            }
        } else {
            // It's a general action - find or create a session
            let session = [...sessions].reverse().find(s => s.username === log.username && s.status === 'Active Session');
            
            if (!session) {
                // Orphaned action - Create a "Recovered/Ongoing" session
                session = {
                    id: Math.random().toString(36).substr(2, 9),
                    username: log.username,
                    role: 'Staff',
                    loginTime: log.timestamp,
                    logoutTime: null,
                    status: 'Ongoing Activity',
                    actions: [],
                    totalRevenue: 0,
                    transactions: 0
                };
                sessions.push(session);
            }
            
            session.actions.push(log);
            if (log.event === 'Dispensed Medicine' || log.event === 'Pharmacy Sale') {
                session.transactions++;
                // Handle total from metadata (ensure it's treated as a number)
                const amt = parseFloat(log.metadata?.total || 0);
                session.totalRevenue += amt;
            }
        }
    });

    // Render Sessions in Reverse Chronological Order
    container.innerHTML = sessions.reverse().map((s, idx) => {
        const icon = s.username === 'admin' ? 'fa-user-tie' : 'fa-user-nurse';
        const color = s.username === 'admin' ? '#0D8ABC' : '#10b981';
        
        const sessionPic = userMap[s.username];
        const avatarUrl = sessionPic ? sessionPic : getLocalAvatarUrl(s.username, color);

        return `
        <div class="session-card">
            <div class="session-header">
                <div class="session-user-info">
                    <img src="${avatarUrl}" style="width:50px; height:50px; border-radius:12px; object-fit:cover; border:2px solid ${color}; padding:2px; background:rgba(255,255,255,0.1);">
                    <div>
                        <h3>${s.username} <small style="font-weight:400; color:var(--text-muted);"> - ${s.role}</small></h3>
                        <p><i class="fa-solid fa-calendar-day"></i> ${new Date(s.loginTime).toLocaleString()}</p>
                        <div class="session-status ${s.status === 'Active Session' ? 'status-active' : 'status-closed'}">
                            <i class="fa-solid ${s.status === 'Active Session' ? 'fa-circle-dot' : 'fa-clock-rotate-left'}"></i>
                            ${s.status} ${s.logoutTime ? ' - Out: ' + new Date(s.logoutTime).toLocaleTimeString() : ''}
                        </div>
                    </div>
                </div>
                <div class="session-meta">
                    <div class="session-revenue">${SYSTEM_SETTINGS.currency} ${s.totalRevenue.toFixed(2)}</div>
                    <div class="session-tx-count">${s.transactions} activity logs</div>
                </div>
            </div>

            <button class="details-toggle" onclick="toggleAuditDetails(this)">
                <span><i class="fa-solid fa-list-check"></i> View Session Logs (${s.actions.length} items)</span>
                <i class="fa-solid fa-chevron-down" style="transition: transform 0.3s ease;"></i>
            </button>
            <div class="details-content">
                <table class="audit-detail-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Action</th>
                            <th>Quantity</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${s.actions.map(a => {
                            const isDispense = a.event === 'Dispensed Medicine' || a.event === 'Pharmacy Sale';
                            const cartItems = a.metadata?.cart || [];
                            
                            // If it's a sale with items, list them
                            if (isDispense && cartItems.length > 0) {
                                return cartItems.map(item => `
                                    <tr>
                                        <td><small>${new Date(a.timestamp).toLocaleTimeString()}</small></td>
                                        <td><strong>${item.name}</strong><br><small style="color:var(--text-muted)">Dispensed</small></td>
                                        <td>${item.qty} units</td>
                                        <td><strong>${SYSTEM_SETTINGS.currency} ${(item.qty * (item.price || 0)).toFixed(2)}</strong></td>
                                    </tr>
                                `).join('');
                            }
                            
                            // Fallback for general logs (Login, Logout, etc.)
                            return `
                                <tr>
                                    <td><small>${new Date(a.timestamp).toLocaleTimeString()}</small></td>
                                    <td><strong>${a.event}</strong><br><small style="color:var(--text-muted)">${a.details || ''}</small></td>
                                    <td>${a.metadata?.items_count || '-'}</td>
                                    <td><strong>${a.metadata?.total ? `${SYSTEM_SETTINGS.currency} ${parseFloat(a.metadata.total).toFixed(2)}` : '-'}</strong></td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        </div>
        `;
    }).join('');
}

function toggleAuditDetails(btn) {
    const card = btn.closest('.session-card');
    const content = card.querySelector('.details-content');
    const chevron = btn.querySelector('i');
    
    content.classList.toggle('active');
    if (content.classList.contains('active')) {
        chevron.style.transform = 'rotate(180deg)';
    } else {
        chevron.style.transform = 'rotate(0deg)';
    }
}

// ---------------- FORECASTING ----------------

// Store forecast data globally so toggle can access item details
let _forecastData = [];

async function loadForecasting(searchTerm = '') {
    const body = document.getElementById('forecast-body');
    if (!body) return;

    const data = await fetchAPI(`/forecast${searchTerm ? '?search=' + encodeURIComponent(searchTerm) : ''}`);
    if (!data) return;
    _forecastData = data;

    if (data.length === 0) {
        body.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:2rem; color:var(--text-muted);">No matching forecasting data found.</td></tr>';
        return;
    }

    body.innerHTML = data.map((item, idx) => {
        const riskLevel = item.Expiry_Risk_Level || 'Low Risk';
        let badgeClass = 'badge-success';
        if (riskLevel === 'Medium Risk') badgeClass = 'badge-warning';
        if (riskLevel === 'High Risk')   badgeClass = 'badge-danger';

        const stockoutStr = item.Predicted_Stockout_Date
            ? new Date(item.Predicted_Stockout_Date).toLocaleDateString(undefined, {month:'short', day:'numeric'})
            : '<span style="color:var(--text-muted);font-size:0.8rem;">365+ days</span>';

        const arrivalStr = item.Manufacturing_Date
            ? new Date(item.Manufacturing_Date).toLocaleDateString(undefined, {month:'short', day:'numeric', year:'numeric'})
            : 'N/A';

        const expiryStr = item.Expiry_Date
            ? new Date(item.Expiry_Date).toLocaleDateString(undefined, {month:'short', day:'numeric', year:'numeric'})
            : 'N/A';

        const isHighRisk = riskLevel === 'High Risk';
        const safeId = (item.Batch_ID || '').replace(/[^a-zA-Z0-9]/g, '_');

        return `
            <tr class="forecast-summary-row" onclick="toggleForecastDetail('${safeId}', ${idx})">
                <td style="text-align:center;padding:0.75rem 0.5rem;">
                    <button class="expand-btn" id="btn-${safeId}" title="View AI Analysis">
                        <i class="fa-solid fa-chevron-down"></i>
                    </button>
                </td>
                <td>
                    <strong>${item.Batch_ID}</strong><br>
                    <small style="color:var(--text-muted);">${item.Manufacturer || '—'}</small>
                </td>
                <td>
                    <strong>${item.Medicine_Name}</strong><br>
                    <small style="color:var(--primary);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.5px;">${item.Category || 'General'}</small>
                </td>
                <td><small>${arrivalStr}</small></td>
                <td><strong>${item.Quantity_In_Stock}</strong> <small>units</small></td>
                <td>${(item.Daily_Consumption_Rate || 0).toFixed(1)}/day</td>
                <td><span style="font-weight:600;color:var(--primary);">${stockoutStr}</span></td>
                <td style="color:${isHighRisk ? 'var(--danger)' : 'inherit'};font-weight:${isHighRisk ? '600' : 'normal'};">
                    <small>${expiryStr}</small>
                </td>
                <td><span class="badge ${badgeClass}">${riskLevel}</span></td>
            </tr>
            <tr class="forecast-detail-row" id="detail-row-${safeId}">
                <td colspan="9" style="padding:0!important;">
                    <div class="detail-panel" id="detail-panel-${safeId}"></div>
                </td>
            </tr>
        `;
    }).join('');
}

function toggleForecastDetail(safeId, idx) {
    const panel = document.getElementById('detail-panel-' + safeId);
    const btn   = document.getElementById('btn-' + safeId);
    if (!panel) return;

    const isOpen = panel.classList.contains('open');

    // Close all open panels first
    document.querySelectorAll('.detail-panel.open').forEach(p => p.classList.remove('open'));
    document.querySelectorAll('.expand-btn.open').forEach(b => b.classList.remove('open'));

    if (!isOpen) {
        const item = _forecastData[idx];
        if (!item) return;

        const riskLevel = item.Expiry_Risk_Level || 'Low Risk';
        const riskClass = riskLevel === 'High Risk' ? 'high' : riskLevel === 'Medium Risk' ? 'medium' : 'low';

        // Stock gauge
        const reorder  = item.Reorder_Level || 50;
        const stock    = item.Quantity_In_Stock || 0;
        const maxStock = Math.max(reorder * 5, stock, 500);
        const stockPct = Math.min(100, Math.round((stock / maxStock) * 100));
        const stockColor = stockPct > 50 ? 'green' : stockPct > 20 ? 'yellow' : 'red';

        // Days-to-exhaust gauge
        const days     = item.Days_to_Exhaust_Stock;
        const daysPct  = (days === null || days === undefined) ? 100 : Math.min(100, Math.round((days / 365) * 100));
        const daysColor = daysPct > 50 ? 'green' : daysPct > 15 ? 'yellow' : 'red';
        const daysLabel = (days === null || days === undefined) ? '365+ days' : `${days} days`;

        const expiryFull = item.Expiry_Date
            ? new Date(item.Expiry_Date).toLocaleDateString(undefined, {weekday:'short', year:'numeric', month:'long', day:'numeric'})
            : 'N/A';

        const rec = item.AI_Recommendation || 'No immediate action required.';

        panel.innerHTML = `
            <div class="detail-panel-inner">
                <div>
                    <div class="detail-metric">
                        <h5>&#x1F4E6; Stock Survival</h5>
                        <div class="metric-val">${stock} <span style="font-size:0.85rem;font-weight:400;">units on hand</span></div>
                        <div class="metric-sub">Reorder threshold: ${reorder} units</div>
                        <div class="gauge-wrap">
                            <div class="gauge-label"><span>Empty</span><span>Full</span></div>
                            <div class="gauge-track"><div class="gauge-fill ${stockColor}" style="width:${stockPct}%"></div></div>
                        </div>
                    </div>
                    <div class="detail-metric" style="margin-top:1.25rem;">
                        <h5>&#x23F3; Time to Exhaustion</h5>
                        <div class="metric-val">${daysLabel}</div>
                        <div class="metric-sub">At ${(item.Daily_Consumption_Rate || 0).toFixed(1)} units/day</div>
                        <div class="gauge-wrap">
                            <div class="gauge-label"><span>0 days</span><span>1 year</span></div>
                            <div class="gauge-track"><div class="gauge-fill ${daysColor}" style="width:${daysPct}%"></div></div>
                        </div>
                    </div>
                </div>
                <div>
                    <div class="detail-metric">
                        <h5>&#x1F3ED; Manufacturer</h5>
                        <div class="metric-val">${item.Manufacturer || '—'}</div>
                        <div class="metric-sub">${item.Category || 'General'} Division</div>
                    </div>
                    <div class="detail-metric" style="margin-top:1.25rem;">
                        <h5>&#x1F4C5; Manufacturing / Arrival</h5>
                        <div class="metric-val" style="font-size:0.95rem;">${item.Manufacturing_Date || 'N/A'}</div>
                    </div>
                    <div class="detail-metric" style="margin-top:1.25rem;">
                        <h5>&#x26A0;&#xFE0F; Shelf Expiry Date</h5>
                        <div class="metric-val" style="font-size:0.9rem;color:${riskClass === 'high' ? 'var(--danger)' : 'inherit'}">${expiryFull}</div>
                        <div class="metric-sub">Risk Level: <strong>${riskLevel}</strong></div>
                    </div>
                </div>
                <div>
                    <div class="ai-rec-card ${riskClass}">
                        <div class="rec-label">&#x1F916; AI Clinical Recommendation</div>
                        <div class="rec-text">${rec}</div>
                        <div class="rec-meta">
                            Based on ${(item.Daily_Consumption_Rate || 0).toFixed(1)} units/day usage &nbsp;|&nbsp;
                            Expiry Risk: <strong>${riskLevel}</strong>
                        </div>
                    </div>
                </div>
            </div>
        `;

        panel.classList.add('open');
        btn.classList.add('open');
    }
}


// ---------------- REPORTS ----------------

async function switchReport(period, btn) {
    // UI Update
    document.querySelectorAll('.report-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    // Load Data
    loadReports(period);
}

async function loadReports(period = 'today') {
    const reportBody = document.getElementById('report-body');
    const historyBody = document.getElementById('sales-history-body');
    const titleEl = document.getElementById('report-facility-title');
    
    // UI Feedbacks
    if (reportBody) reportBody.innerHTML = '<tr><td colspan="2" class="loading-td"><div class="spinner"></div> Updating metrics...</td></tr>';
    
    // Fetch aggregated report data
    const data = await fetchAPI(`/admin/reports?period=${period}`);
    const dashData = await fetchAPI('/dashboard'); // for inventory stats
    
    if (!data || !dashData) return;

    // 1. Update Facility Title
    if (titleEl) {
        const hospitalName = SYSTEM_SETTINGS.hospital_name || "Ghana National Hospital";
        const periodText = period === 'today' ? "Today's Performance" : (period === 'month' ? "Monthly Performance" : "Annual Performance");
        titleEl.textContent = `${hospitalName} - ${periodText} Overview`;
    }

    // 2. Update Summary Cards
    document.getElementById('sum-revenue').textContent = `${SYSTEM_SETTINGS.currency} ${data.total_revenue.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    document.getElementById('sum-txn').textContent = data.transaction_count.toLocaleString();
    document.getElementById('sum-items').textContent = data.items_sold.toLocaleString();

    // 3. Update Inventory Metrics (Static context)
    if (reportBody) {
        reportBody.innerHTML = `
            <tr>
                <td>Total Inventory Valuation</td>
                <td><strong>GH₵ ${parseFloat(dashData.totalStockValue).toLocaleString(undefined, {minimumFractionDigits: 2})}</strong></td>
            </tr>
            <tr>
                <td>Total Registered Medicines</td>
                <td>${dashData.totalItems} Items</td>
            </tr>
            <tr>
                <td>Critical Stock Alerts</td>
                <td style="color:red;">${dashData.lowStockCount} Items</td>
            </tr>
            <tr>
                <td>Upcoming Expirations (< 30 days)</td>
                <td style="color:red;">${dashData.expiredOrNearExpiryCount} Items</td>
            </tr>
        `;
    }

    // 4. Update Sales History table for the period
    // If the section doesn't exist, create it (legacy logic support)
    let historyTableBody = document.getElementById('sales-history-body');
    if (!historyTableBody) {
        const salesTableCont = document.querySelector('.table-section');
        const historySection = document.createElement('section');
        historySection.className = 'table-section glass';
        historySection.style.marginTop = '2rem';
        historySection.innerHTML = `
            <h3 style="margin-bottom: 1rem;">Transaction History for selected period</h3>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Date & Time</th>
                            <th>Staff Member</th>
                            <th>Customer</th>
                            <th>Items Sold</th>
                            <th>Total (GH₵)</th>
                        </tr>
                    </thead>
                    <tbody id="sales-history-body"></tbody>
                </table>
            </div>
        `;
        salesTableCont.parentNode.appendChild(historySection);
        historyTableBody = document.getElementById('sales-history-body');
    }

    if (historyTableBody && data.sales) {
        if (data.sales.length === 0) {
            historyTableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:2rem; color:var(--text-muted);">No transactions recorded for this period.</td></tr>';
        } else {
            historyTableBody.innerHTML = data.sales.map(s => `
                <tr>
                    <td><small>${new Date(s.timestamp).toLocaleString()}</small></td>
                    <td><strong>${s.pharmacist}</strong></td>
                    <td>${s.customer_name || 'Walk-in'}</td>
                    <td><span title="${s.details || 'N/A'}">${s.items} Items <i class="fa-solid fa-circle-info" style="color:var(--primary); font-size:0.7rem;"></i></span></td>
                    <td><strong>${SYSTEM_SETTINGS.currency} ${s.total_ghs.toFixed(2)}</strong></td>
                </tr>
            `).join('');
        }
    }
}

// ---------------- POS SYSTEM ----------------
let posCart = [];
let allPosInventory = [];

async function initPOS() {
    allPosInventory = await fetchAPI('/inventory');
    loadPOSSearch();
}

function loadPOSSearch() {
    const term = document.getElementById('pos-search')?.value.toLowerCase() || '';
    const list = document.getElementById('pos-inventory-list');
    if (!list || !allPosInventory) return;
    
    const filtered = allPosInventory.filter(i => 
        i.Medicine_Name.toLowerCase().includes(term) || 
        i.Batch_ID.toLowerCase().includes(term)
    );
    
    list.innerHTML = filtered.slice(0, 50).map(item => {
        const priceGHS = ((item.Selling_Price_USD || 0) * (SYSTEM_SETTINGS.exchange_rate || 1.0)).toFixed(2);
        return `
        <div class="pos-item">
            <div>
                <strong>${item.Medicine_Name}</strong> <small style="color:var(--text-muted)">(${item.Batch_ID})</small><br>
                <small>Stock: ${item.Quantity_In_Stock} | GH₵ ${priceGHS}</small>
            </div>
            <button class="btn" style="padding: 5px 15px;" onclick="addToCart('${item.Batch_ID}', '${item.Medicine_Name}', ${priceGHS}, ${item.Quantity_In_Stock})">Add</button>
        </div>
    `;
    }).join('');
}

function addToCart(batch, name, price, stock) {
    if (stock <= 0) return alert('Out of stock!');
    const existing = posCart.find(i => i.Batch_ID === batch);
    if (existing) {
        if (existing.qty >= stock) return alert('Cannot exceed inventory stock!');
        existing.qty++;
    } else {
        posCart.push({ Batch_ID: batch, name, price, qty: 1, max: stock });
    }
    renderCart();
}

function updateCartQty(batch, delta) {
    const item = posCart.find(i => i.Batch_ID === batch);
    if (!item) return;
    item.qty += delta;
    if (item.qty > item.max) {
        item.qty = item.max;
        alert('Max stock reached');
    }
    if (item.qty <= 0) posCart = posCart.filter(i => i.Batch_ID !== batch);
    renderCart();
}

function renderCart() {
    const cartEl = document.getElementById('pos-cart-list');
    const totalEl = document.getElementById('pos-total');
    if (!cartEl) return;
    
    if (posCart.length === 0) {
        cartEl.innerHTML = '<p style="color:var(--text-muted);">Cart is empty</p>';
        totalEl.textContent = `${SYSTEM_SETTINGS.currency} 0.00`;
        return;
    }
    
    let total = 0;
    cartEl.innerHTML = posCart.map(i => {
        total += i.qty * i.price;
        return `
        <div class="cart-row">
            <div style="flex:2">
                <strong>${i.name}</strong><br>
                <small style="opacity:0.8;">Unit: ${SYSTEM_SETTINGS.currency} ${i.price.toFixed(2)}</small>
            </div>
            <div style="flex:1; text-align:center;">
                <button style="cursor:pointer; background:none; border:none; color:white;" onclick="updateCartQty('${i.Batch_ID}', -1)"><i class="fa-solid fa-minus"></i></button>
                <span style="margin: 0 10px; font-weight:600;">${i.qty}</span>
                <button style="cursor:pointer; background:none; border:none; color:white;" onclick="updateCartQty('${i.Batch_ID}', 1)"><i class="fa-solid fa-plus"></i></button>
            </div>
            <div style="flex:1; text-align:right;">
                <small style="display:block; font-size:0.7rem; opacity:0.7; margin-bottom:2px;">Subtotal</small>
                <span style="font-weight:600;">${SYSTEM_SETTINGS.currency} ${(i.qty * i.price).toFixed(2)}</span>
            </div>
        </div>
        `;
    }).join('');
    
    totalEl.textContent = SYSTEM_SETTINGS.currency + ' ' + total.toFixed(2);
}

async function checkoutPOS() {
    if (posCart.length === 0) return alert('Cart is empty.');
    
    try {
        const customerName = document.getElementById('customer-name')?.value || '';
        const res = await fetch(`${API_URL}/checkout`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                cart: posCart,
                staff_name: localStorage.getItem('medai_username') || 'Pharmacist',
                customer_name: customerName
            })
        });
        const data = await res.json();
        if (data.success) {
            // 1. Generate Receipt and Trigger Print FIRST (No blocking alert yet)
            const finalCart = [...posCart];
            const finalTotal = data.total;
            printReceipt(finalCart, finalTotal, customerName);
            
            // 2. Clear Cart and Refresh UI immediately
            if (document.getElementById('customer-name')) document.getElementById('customer-name').value = '';
            posCart = [];
            renderCart();
            initPOS(); 

            // 3. Show Success Alert AFTER triggering print (non-blocking for print engine)
            setTimeout(() => {
                alert(`Dispense Processed! Total: ${SYSTEM_SETTINGS.currency} ${data.total}`);
            }, 1000);
        } else {
            alert('Failed: ' + data.error);
        }
    } catch(err) {
        alert('Checkout error');
    }
}

function handleBarcodeScan(code) {
    if (!allPosInventory || allPosInventory.length === 0) {
        alert('Inventory data is still loading. Please wait a moment.');
        return;
    }
    
    // Case-insensitive matching for Batch ID
    const searchCode = code.trim().toLowerCase();
    const item = allPosInventory.find(i => i.Batch_ID.toLowerCase() === searchCode);
    
    if (!item) {
        alert('Barcode not found: ' + code);
        return;
    }
    const priceGHS = ((item.Selling_Price_USD || 0) * (SYSTEM_SETTINGS.exchange_rate || 1.0));
    addToCart(item.Batch_ID, item.Medicine_Name, priceGHS, item.Quantity_In_Stock);
}

function printReceipt(cart, total, customerName = '') {
    const listBody = document.getElementById('receipt-items');
    const totalEl = document.getElementById('receipt-grand-total');
    const dateEl = document.getElementById('receipt-date');
    const idEl = document.getElementById('receipt-id');
    const customerEl = document.createElement('p');

    // DYNAMIC HEADER UPDATE
    const h2Receipt = document.querySelector('#receipt-container h2');
    const pNHIS = document.createElement('p');
    if (h2Receipt) h2Receipt.textContent = SYSTEM_SETTINGS.hospital_name;
    
    // Clear previous NHIS if any
    const existingNHIS = document.getElementById('receipt-nhis');
    if (existingNHIS) existingNHIS.remove();

    pNHIS.id = 'receipt-nhis';
    pNHIS.textContent = 'NHIS ID: ' + SYSTEM_SETTINGS.nhis_id;
    pNHIS.style.fontSize = '0.75rem';
    if (h2Receipt) h2Receipt.parentNode.insertBefore(pNHIS, h2Receipt.nextSibling);
    
    if (!listBody) return;
    
    dateEl.textContent = 'Date: ' + new Date().toLocaleString();
    idEl.textContent = 'Transaction: TXN' + Math.random().toString(36).substr(2, 9).toUpperCase();
    
    // Clear previous customer name if any
    const existingCust = document.getElementById('receipt-customer');
    if (existingCust) existingCust.remove();

    if (customerName) {
        customerEl.id = 'receipt-customer';
        customerEl.innerHTML = `<strong>Customer: ${customerName}</strong>`;
        idEl.parentNode.insertBefore(customerEl, idEl.nextSibling);
    }
    
    listBody.innerHTML = cart.map(i => `
        <tr>
            <td>${i.name}</td>
            <td>${i.qty}</td>
            <td>${SYSTEM_SETTINGS.currency} ${(i.qty * i.price).toFixed(2)}</td>
        </tr>
    `).join('');
    
    totalEl.innerHTML = `Grand Total: ${SYSTEM_SETTINGS.currency} ${total.toFixed(2)}`;
    
    // Generate barcode for transaction
    JsBarcode("#receipt-barcode", idEl.textContent.split(': ')[1], {
        format: "CODE128",
        width: 1.5,
        height: 40,
        displayValue: true
    });
    
    // Trigger Print
    setTimeout(() => {
        document.body.classList.add('receipt-mode');
        window.print();
        setTimeout(() => document.body.classList.remove('receipt-mode'), 500);
    }, 500);
}

// ---------------- PHARMACIST DASHBOARD ----------------
async function loadPharmacistDashboard() {
    const res = await fetchAPI('/sales/today');
    const salesVal = res ? res.total_revenue_ghs : 0;
    
    const ui = document.getElementById('pharm-sales-today');
    if (ui) {
        ui.textContent = SYSTEM_SETTINGS.currency + ' ' + parseFloat(salesVal).toLocaleString(undefined, {minimumFractionDigits: 2});
    }
}

// Utility
function getRiskClass(risk) {
    if (!risk) return 'low';
    const r = risk.toLowerCase();
    if (r.includes('high')) return 'high';
    if (r.includes('medium')) return 'medium';
    return 'low';
}

// PROFESSIONAL CSV EXPORT
async function exportToCSV() {
    const res = await fetch(`${API_URL}/admin/sales`);
    const data = await res.json();
    if (!data || data.length === 0) return alert('No sales data to export.');

    const headers = ["Timestamp", "Pharmacist", "Customer", "Items", "Total (" + SYSTEM_SETTINGS.currency + ")", "Details"];
    const rows = data.map(s => [
        s.timestamp,
        s.pharmacist,
        s.customer_name || 'Walk-in',
        s.items,
        s.total_ghs.toFixed(2),
        `"${s.details.replace(/"/g, '""')}"`
    ]);

    const csvContent = [headers, ...rows].map(e => e.join(",")).join("\n");
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", `MedAI_GH_Sales_Report_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
function getRiskClass(level) {
    if(level === 'High Risk') return 'danger';
    if(level === 'Medium Risk') return 'medium';
    return 'low';
}

// --- AWARD WINNING ENHANCEMENTS ---

function openXAIModal(name, batch, exhaust, expiryDays, consume, risk) {
    const modal = document.getElementById('xai-modal');
    const body = document.getElementById('xai-body');
    if (!modal || !body) return;
    
    let explanation = `The MedAI Engine classified <strong>${name} (Batch: ${batch})</strong> as <span class="badge danger">${risk}</span> based on the Utilization Probability Formula:<br><br>`;
    
    explanation += `<div style="background:rgba(0,0,0,0.05); padding:10px; border-radius:8px; font-family:monospace; margin:10px 0; border-left:3px solid var(--primary);">`;
    explanation += `Risk = (Current_Stock / Avg_Daily_Sales) > Days_to_Expiry<br>`;
    explanation += `Threshold: ${exhaust} days to sell > ${expiryDays} days left`;
    explanation += `</div>`;
    
    if (exhaust === 'Unlimited') {
        explanation += `<p><strong>Analysis:</strong> The model predicts a daily consumption rate of ~${consume} units/day. Due to insufficient sales velocity, the system cannot mathematically guarantee the stock will be exhausted before expiration.</p>`;
    } else {
        explanation += `<p><strong>Analysis:</strong> Based on the predicted consumption rate of <strong>${consume} units/day</strong>, it will take <strong>${exhaust} days</strong> to logically exhaust this batch.</p>`;
        explanation += `<p>Because the predicted time to exhaust (${exhaust} days) physically exceeds the actual time remaining on the shelf (${expiryDays} days), the AI has proactively alerted this batch to prevent financial leak via medical waste.</p>`;
    }
    
    body.innerHTML = explanation;
    modal.style.display = 'flex';
}

function simulateSMSBroadcast() {
    const modal = document.getElementById('sms-modal');
    if (modal) {
        document.getElementById('sms-phone').value = localStorage.getItem('sms_target_phone') || '';
        document.getElementById('sms-apikey').value = localStorage.getItem('sms_api_key') || '';
        modal.style.display = 'flex';
    }
}

async function confirmSMSBroadcast() {
    const phoneInput = document.getElementById('sms-phone').value.trim().replace(/\+/g, '');
    const apikey = document.getElementById('sms-apikey').value.trim();
    
    if (!phoneInput) {
        alert("Please enter a Target Phone Number to send the alerts.");
        return;
    }
    
    // Save to localstorage for convenience
    localStorage.setItem('sms_target_phone', document.getElementById('sms-phone').value.trim());
    localStorage.setItem('sms_api_key', apikey);

    const modal = document.getElementById('sms-modal');
    if (modal) modal.style.display = 'none';
    
    showToast(`Pinging WhatsApp Gateway for ${document.getElementById('sms-phone').value}...`, "info");
    
    const textMsg = encodeURIComponent("🚨 *MedAI Alert*\n\nHigh risk items detected in inventory! AI predicts they will not exhaust before expiry.\n\nPlease check Dashboard immediately.");

    try {
        if (apikey) {
            // Offline Mode Enforced: The following external API call is disabled.
            // const fetchUrl = `https://api.callmebot.com/whatsapp.php?phone=+${phoneInput}&text=${textMsg}&apikey=${apikey}`;
            // await fetch(fetchUrl, { mode: 'no-cors' }); 
            showToast(`Offline Mode: WhatsApp integration is disabled. Alert simulated.`, "success");
        } else {
            // Presentation Simulation Mode
            showToast(`Alerts transmitted to WhatsApp Gateway for delivery to +${phoneInput}.`, "success");
        }
        
        // Update the broadcast button text globally
        const btnTags = document.getElementsByTagName("button");
        for (let btn of btnTags) {
            if (btn.innerHTML.includes("Broadcast Alerts")) {
                btn.innerHTML = '<i class="fa-brands fa-whatsapp"></i> Alerts Dispatched';
                btn.style.background = "var(--text-muted)";
            }
        }
    } catch(err) {
        showToast(`Failed to establish connection to the WhatsApp Gateway.`, "danger");
    }
}

function showToast(message, type="info") {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.style.background = type === 'success' ? '#10b981' : 'var(--primary)';
    toast.style.color = 'white';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 10px 25px rgba(0,0,0,0.2)';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.gap = '10px';
    toast.style.animation = 'modalIn 0.3s ease-out';
    toast.style.backdropFilter = 'blur(10px)';
    
    toast.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${message}`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function printReport() {
    window.print();
}
