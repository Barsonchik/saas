// app.js - Основная логика приложения Shadowsocks Manager

// ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================
let eventSource = null;
let trafficChart = null;
let historyChart = null;
let liveTrafficData = [];
let usersData = []; // Глобальные данные пользователей

// Базовый URL API
const API_BASE = window.location.origin;

// Правильные эндпоинты API
const API_ENDPOINTS = {
    // GET запросы
    health: '/api/health',
    stats: '/api/stats',
    users: '/api/users',
    'services.status': '/api/services/status',
    'traffic.history': '/api/traffic/history',
    'notifications.history': '/api/notifications/history',
    
    // POST запросы
    'admin.initialize': '/api/admin/initialize',
    'services.sync': '/api/services/sync',
    'services.restart-all': '/api/services/restart-all',
    'services.reload-all': '/api/services/reload-all',
    'notifications.check': '/api/notifications/check',
    'user.add': '/api/users',
    
    // SSE поток
    'traffic.stream': '/api/traffic-stream',
    
    // Service control
    'service.control': '/api/service/control'
};

// Вспомогательная функция для получения полного URL
function getApiUrl(endpointKey, id = null) {
    let endpoint = API_ENDPOINTS[endpointKey];
    if (!endpoint) {
        console.error('Unknown endpoint:', endpointKey);
        return '';
    }
    
    // Для динамических эндпоинтов с ID
    if (id && endpoint.includes('{id}')) {
        endpoint = endpoint.replace('{id}', id);
    }
    
    return API_BASE + endpoint;
}

// Функция для получения URL конфигурации пользователя
function getUserConfigUrl(userId) {
    return `${API_BASE}/api/users/${userId}/config`;
}

// Функция для получения URL скачивания конфигурации
function getUserDownloadUrl(userId) {
    return `${API_BASE}/api/users/${userId}/download`;
}

// Функция для получения URL сброса трафика
function getResetTrafficUrl(userId) {
    return `${API_BASE}/api/users/${userId}/reset-traffic`;
}

// Функция для получения URL продления пользователя
function getExtendUserUrl(userId) {
    return `${API_BASE}/api/users/${userId}/extend`;
}

// Функция для получения URL удаления пользователя
function getDeleteUserUrl(userId) {
    return `${API_BASE}/api/users/${userId}`;
}

// Функция для получения URL переключения службы
function getToggleServiceUrl(userId) {
    return `${API_BASE}/api/users/${userId}/service/toggle`;
}

// Функция для получения URL перезапуска службы
function getRestartServiceUrl(userId) {
    return `${API_BASE}/api/users/${userId}/service/restart`;
}

const UPDATE_INTERVALS = {
    stats: 30000,      // 30 секунд
    services: 60000,   // 1 минута
    notifications: 300000 // 5 минут
};

// ==================== ИНИЦИАЛИЗАЦИЯ ====================

document.addEventListener('DOMContentLoaded', function() {
    initApp();
});

function initApp() {
    // Проверяем соединение с API
    checkConnection().then(connected => {
        if (connected) {
            // Загружаем начальные данные
            loadDashboard();
            startTrafficStream();
            loadActivityLog();
            loadTrafficHistory();
            checkNotifications();
            
            // Настраиваем периодическое обновление
            setupAutoRefresh();
            
            // Настраиваем обработчики событий
            setupEventListeners();
            
            // Загружаем настройки экспорта
            loadExportSettings();
            
            // Инициализируем вкладку по умолчанию
            switchTab('dashboard');
        } else {
            showToast('Cannot connect to API server. Please check if the server is running.', 'error');
            setServerStatusOffline();
        }
    });
}

async function checkConnection() {
    try {
        const response = await fetch(getApiUrl('health'));
        return response.ok;
    } catch (error) {
        return false;
    }
}

function setupAutoRefresh() {
    // Обновляем статистику каждые 30 секунд
    setInterval(loadStats, UPDATE_INTERVALS.stats);
    
    // Обновляем обзор служб каждую минуту
    setInterval(loadServicesOverview, UPDATE_INTERVALS.services);
    
    // Проверяем уведомления каждые 5 минут
    setInterval(checkNotifications, UPDATE_INTERVALS.notifications);
    
    // Проверяем здоровье сервера каждую минуту
    setInterval(checkServerHealth, 60000);
}

function setupEventListeners() {
    // Закрытие панели уведомлений при клике вне её
    document.addEventListener('click', function(event) {
        const panel = document.getElementById('notifications-panel');
        const button = document.getElementById('notifications-btn');
        
        if (panel && panel.style.display === 'block' && 
            button && !panel.contains(event.target) && 
            !button.contains(event.target)) {
            panel.style.display = 'none';
        }
    });
    
    // Закрытие модальных окон с Escape
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeAllModals();
        }
    });
}

function closeAllModals() {
    const modals = ['notifications-panel', 'addUserModal', 'configModal', 'serviceInfoModal'];
    modals.forEach(modalId => {
        const modal = document.getElementById(modalId);
        if (modal) modal.style.display = 'none';
    });
}

function setServerStatusOffline() {
    const statusEl = document.getElementById('server-status');
    if (statusEl) {
        statusEl.className = 'server-status status-offline';
        statusEl.innerHTML = '<i class="fas fa-circle"></i> Offline';
    }
    
    const liveIndicator = document.getElementById('live-indicator');
    const liveStatus = document.getElementById('live-status');
    if (liveIndicator) liveIndicator.style.background = '#dc3545';
    if (liveStatus) liveStatus.textContent = 'Real-time: Disconnected';
}

async function checkServerHealth() {
    try {
        const response = await fetch(getApiUrl('health'));
        if (response.ok) {
            const data = await response.json();
            if (data.status === 'healthy') {
                // Сервер онлайн
                const statusEl = document.getElementById('server-status');
                if (statusEl) {
                    statusEl.className = 'server-status status-online';
                    statusEl.innerHTML = '<i class="fas fa-circle"></i> Online';
                }
            }
        }
    } catch (error) {
        setServerStatusOffline();
    }
}

// ==================== ДАШБОРД ====================

async function loadDashboard() {
    try {
        await Promise.all([
            loadStats(),
            loadUsers(),
            loadServicesOverview()
        ]);
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

async function loadStats() {
    try {
        const response = await fetch(getApiUrl('stats'));
        if (!response.ok) throw new Error('Failed to fetch stats');
        
        const data = await response.json();
        
        if (data.success) {
            updateStatsDisplay(data.stats);
        } else {
            throw new Error(data.message || 'Failed to load stats');
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function updateStatsDisplay(stats) {
    try {
        // Обновляем серверный IP
        const serverIpEl = document.getElementById('server-ip');
        if (serverIpEl && stats.server) {
            serverIpEl.textContent = stats.server.ip || 'Unknown';
        }
        
        // Обновляем статистику пользователей
        const activeUsersEl = document.getElementById('active-users');
        const totalUsersEl = document.getElementById('total-users');
        if (activeUsersEl && totalUsersEl && stats.users) {
            activeUsersEl.textContent = stats.users.active || 0;
            totalUsersEl.textContent = `Total: ${stats.users.total || 0}`;
        }
        
        // Обновляем статистику служб
        const runningServicesEl = document.getElementById('running-services');
        const totalServicesEl = document.getElementById('total-services');
        if (runningServicesEl && totalServicesEl && stats.services) {
            runningServicesEl.textContent = stats.services.active_services || 0;
            totalServicesEl.textContent = `Total: ${stats.services.total_services || 0}`;
        }
        
        // Обновляем системные метрики
        const cpuUsageEl = document.getElementById('cpu-usage');
        const memoryUsageEl = document.getElementById('memory-usage');
        if (cpuUsageEl && memoryUsageEl && stats.system) {
            cpuUsageEl.textContent = `${stats.system.cpu_usage || 0}%`;
            memoryUsageEl.textContent = `Memory: ${stats.system.memory_usage || 0}%`;
        }
        
        // Обновляем статус сервера
        const statusEl = document.getElementById('server-status');
        if (statusEl && stats.server) {
            if (stats.server.db_status === 'connected' && stats.server.manager_status === 'connected') {
                statusEl.className = 'server-status status-online';
                statusEl.innerHTML = '<i class="fas fa-circle"></i> Online';
                
                // Обновляем индикатор реального времени
                const liveIndicator = document.getElementById('live-indicator');
                const liveStatus = document.getElementById('live-status');
                if (liveIndicator) liveIndicator.style.background = '#28a745';
                if (liveStatus) liveStatus.textContent = 'Real-time: Connected';
            } else {
                statusEl.className = 'server-status status-warning';
                statusEl.innerHTML = '<i class="fas fa-circle"></i> Partial';
            }
        }
        
        // Обновляем сетку статистики
        const statsGrid = document.getElementById('stats');
        if (statsGrid) {
            const totalTraffic = stats.traffic ? `${stats.traffic.total_used_gb || 0} / ${stats.traffic.total_limit_gb || 0} GB` : '0 GB';
            const trafficPercent = stats.traffic && stats.traffic.total_limit_gb > 0 ? 
                (stats.traffic.total_used_gb / stats.traffic.total_limit_gb * 100).toFixed(1) : 0;
            
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-users"></i>
                    </div>
                    <div class="stat-content">
                        <div class="stat-value">${stats.users?.total || 0}</div>
                        <div class="stat-label">Total Users</div>
                        <div class="stat-sub">${stats.users?.active || 0} active</div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <div class="stat-content">
                        <div class="stat-value">${totalTraffic}</div>
                        <div class="stat-label">Total Traffic</div>
                        <div class="stat-sub">${trafficPercent}% used</div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-server"></i>
                    </div>
                    <div class="stat-content">
                        <div class="stat-value">${stats.services?.total_services || 0}</div>
                        <div class="stat-label">Total Services</div>
                        <div class="stat-sub">${stats.services?.active_services || 0} running</div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-microchip"></i>
                    </div>
                    <div class="stat-content">
                        <div class="stat-value">${stats.system?.cpu_usage || 0}%</div>
                        <div class="stat-label">CPU Usage</div>
                        <div class="stat-sub">Memory: ${stats.system?.memory_usage || 0}%</div>
                    </div>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Error updating stats display:', error);
    }
}

async function loadUsers() {
    try {
        const response = await fetch(getApiUrl('users'));
        if (!response.ok) throw new Error('Failed to fetch users');
        
        const data = await response.json();
        console.log('Users data loaded:', data);
        
        if (data.success) {
            usersData = data.users || []; // Сохраняем локально
            window.usersData = usersData; // Сохраняем глобально для доступа из других скриптов
            console.log('window.usersData set to:', window.usersData);
            updateUsersDisplay(usersData);
        }
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

function updateUsersDisplay(users) {
    const tbody = document.getElementById('users-body');
    if (!tbody) return;
    
    if (!users || users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="no-data">
                    <i class="fas fa-users"></i>
                    <p>No users found. Click "Add User" to create your first user.</p>
                </td>
            </tr>
        `;
    } else {
        tbody.innerHTML = users.map(user => createUserRow(user)).join('');
    }
}

function createUserRow(user) {
    const trafficPercent = Math.min(user.traffic_percent || 0, 100);
    const trafficColor = trafficPercent > 80 ? '#dc3545' : '#666';
    const daysRemaining = user.days_remaining || 0;
    const daysColor = daysRemaining < 7 ? '#dc3545' : '#28a745';
    const isAdmin = user.role === 'admin';
    
    return `
        <tr>
            <td>
                <strong>${user.username}</strong>
                ${user.email ? `<br><small class="user-email">${user.email}</small>` : ''}
                ${isAdmin ? '<br><span class="service-status service-running">Admin</span>' : ''}
            </td>
            <td><strong>${user.port}</strong></td>
            <td>
                <div class="service-status ${user.enable ? 'service-running' : 'service-stopped'}">
                    <i class="fas fa-circle"></i>
                    ${user.service_name || 'N/A'}
                </div>
            </td>
            <td>
                <div class="traffic-usage">
                    <strong>${user.traffic_used_gb} / ${user.traffic_limit_gb} GB</strong>
                    <div class="traffic-bar">
                        <div class="traffic-fill" style="width: ${trafficPercent}%"></div>
                    </div>
                    <small style="color: ${trafficColor}">
                        ${trafficPercent}% used
                    </small>
                </div>
            </td>
            <td>
                ${user.expires_at ? new Date(user.expires_at).toLocaleDateString() : 'Never'}
                ${user.days_remaining !== undefined ? `
                    <br><small style="color: ${daysColor}">
                        ${daysRemaining} days left
                    </small>
                ` : ''}
            </td>
            <td class="${user.enable ? 'status-active' : 'status-inactive'}">
                <i class="fas fa-circle"></i>
                ${user.enable ? 'Active' : 'Inactive'}
            </td>
            <td>
                <div class="actions">
                    <button class="btn btn-sm" onclick="showUserConfig('${user._id}', '${user.username}')" title="Show Configuration">
                        <i class="fas fa-code"></i>
                    </button>
                    <button class="btn btn-sm" onclick="downloadUserConfig('${user._id}')" title="Download Config">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="btn btn-sm btn-success" onclick="resetUserTraffic('${user._id}')" title="Reset Traffic">
                        <i class="fas fa-redo"></i>
                    </button>
                    ${!isAdmin ? `
                        <button class="btn btn-sm ${user.enable ? 'btn-warning' : 'btn-success'}" 
                            onclick="toggleUserService('${user._id}', ${!user.enable})" 
                            title="${user.enable ? 'Stop Service' : 'Start Service'}">
                            <i class="fas fa-power-off"></i>
                        </button>
                        <button class="btn btn-sm btn-info" onclick="extendUser('${user._id}')" title="Extend">
                            <i class="fas fa-calendar-plus"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteUser('${user._id}')" title="Delete User">
                            <i class="fas fa-trash"></i>
                        </button>
                    ` : ''}
                </div>
            </td>
        </tr>
    `;
}

// ==================== УПРАВЛЕНИЕ СЛУЖБАМИ ====================

async function loadServicesOverview() {
    try {
        const response = await fetch(getApiUrl('services.status'));
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.success) {
            // Вызываем функцию из services.js для обновления отображения
            if (typeof window.updateServicesOverview === 'function') {
                window.updateServicesOverview(data.user_services || []);
            }
        }
    } catch (error) {
        console.error('Error loading services overview:', error);
    }
}

// ==================== МОНИТОРИНГ ====================

function startTrafficStream() {
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource(getApiUrl('traffic.stream'));
    
    eventSource.onopen = function() {
        const indicator = document.getElementById('live-indicator');
        const status = document.getElementById('live-status');
        if (indicator) indicator.style.background = '#28a745';
        if (status) status.textContent = 'Real-time: Connected';
    };
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'traffic_update') {
                liveTrafficData = data.data.history || [];
                updateTrafficChart();
                updateLiveTrafficDisplay(data.data.users || []);
            }
        } catch (error) {
            console.error('Error processing traffic stream:', error);
        }
    };
    
    eventSource.onerror = function() {
        const indicator = document.getElementById('live-indicator');
        const status = document.getElementById('live-status');
        if (indicator) indicator.style.background = '#dc3545';
        if (status) status.textContent = 'Real-time: Disconnected';
        
        // Попробуем переподключиться через 5 секунд
        setTimeout(() => {
            if (eventSource && eventSource.readyState === EventSource.CLOSED) {
                startTrafficStream();
            }
        }, 5000);
    };
}

function updateTrafficChart() {
    const ctx = document.getElementById('trafficChart');
    if (!ctx) return;
    
    const chartCtx = ctx.getContext('2d');
    
    if (trafficChart) {
        trafficChart.destroy();
    }
    
    if (!liveTrafficData || liveTrafficData.length === 0) {
        // Показываем пустой график
        trafficChart = new Chart(chartCtx, {
            type: 'line',
            data: {
                labels: ['No data'],
                datasets: [{
                    label: 'Traffic Usage (GB)',
                    data: [0],
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'GB'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    }
                }
            }
        });
        return;
    }
    
    const labels = liveTrafficData.map(item => {
        try {
            const date = new Date(item.timestamp);
            return `${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`;
        } catch (e) {
            return 'Unknown';
        }
    });
    
    const data = liveTrafficData.map(item => item.total_used_gb || 0);
    
    trafficChart = new Chart(chartCtx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Traffic Usage (GB)',
                data: data,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'GB'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    }
                }
            }
        }
    });
}

function updateLiveTrafficDisplay(users) {
    const container = document.getElementById('live-traffic');
    if (!container) return;
    
    if (!users || users.length === 0) {
        container.innerHTML = '<div class="no-data">No traffic data</div>';
        return;
    }
    
    const html = users.map(user => `
        <div class="live-traffic-item">
            <div class="live-traffic-info">
                <strong>${user.username || 'Unknown'}</strong>
                <div class="live-traffic-detail">Port: ${user.port || 'N/A'}</div>
            </div>
            <div class="live-traffic-stats">
                <div class="traffic-amount">${user.traffic_used_gb || 0} GB</div>
                <div class="traffic-limit">${user.traffic_limit_gb || 0} GB limit</div>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = html;
}

async function loadTrafficHistory() {
    try {
        const response = await fetch(getApiUrl('traffic.history') + '?days=7');
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.success && data.history && data.history.length > 0) {
            updateHistoryChart(data.history);
        }
    } catch (error) {
        console.error('Error loading traffic history:', error);
    }
}

function updateHistoryChart(history) {
    const ctx = document.getElementById('historyChart');
    if (!ctx) return;
    
    const chartCtx = ctx.getContext('2d');
    
    if (historyChart) {
        historyChart.destroy();
    }
    
    const labels = history.map(item => item.date || 'Unknown');
    const data = history.map(item => item.total_used_gb || 0);
    
    historyChart = new Chart(chartCtx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Daily Traffic (GB)',
                data: data,
                backgroundColor: '#667eea',
                borderColor: '#764ba2',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'GB'
                    }
                }
            }
        }
    });
}

// ==================== АКТИВНОСТЬ ====================

async function loadActivityLog() {
    try {
        const response = await fetch(getApiUrl('notifications.history') + '?limit=10');
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.success) {
            updateActivityLog(data.notifications || []);
        }
    } catch (error) {
        console.error('Error loading activity log:', error);
    }
}

function updateActivityLog(notifications) {
    const tbody = document.getElementById('activity-log');
    if (!tbody) return;
    
    if (!notifications || notifications.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" class="no-data">
                    No recent activity
                </td>
            </tr>
        `;
    } else {
        tbody.innerHTML = notifications.map(notif => `
            <tr>
                <td>${notif.timestamp ? new Date(notif.timestamp).toLocaleTimeString() : 'Unknown'}</td>
                <td>${notif.username || 'System'}</td>
                <td>${notif.notification_type || notif.type || 'info'}</td>
                <td>${notif.message || 'No message'}</td>
            </tr>
        `).join('');
    }
}

// ==================== УВЕДОМЛЕНИЯ ====================

function openNotifications() {
    const panel = document.getElementById('notifications-panel');
    if (panel) {
        panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
        checkNotifications();
    }
}

async function checkNotifications() {
    try {
        const response = await fetch(getApiUrl('notifications.check'), {
            method: 'POST'
        });
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.success) {
            updateNotificationsDisplay(data.notifications || []);
        }
    } catch (error) {
        console.error('Error checking notifications:', error);
    }
}

function updateNotificationsDisplay(notifications) {
    const list = document.getElementById('notifications-list');
    const countBadge = document.getElementById('notification-count');
    
    if (!list) return;
    
    if (!notifications || notifications.length === 0) {
        list.innerHTML = `
            <div class="no-notifications">
                <i class="fas fa-bell-slash"></i>
                <p>No notifications</p>
            </div>
        `;
        if (countBadge) {
            countBadge.style.display = 'none';
        }
    } else {
        list.innerHTML = notifications.map(notif => `
            <div class="notification-item ${notif.type}">
                <div class="notification-header">
                    <span class="notification-type">${notif.type}</span>
                    <span class="notification-time">${new Date().toLocaleTimeString()}</span>
                </div>
                <div class="notification-content">
                    ${notif.message || 'No message'}
                </div>
                ${notif.username ? `<div class="notification-user">User: ${notif.username}</div>` : ''}
            </div>
        `).join('');
        
        if (countBadge) {
            countBadge.textContent = notifications.length;
            countBadge.style.display = 'inline-block';
        }
    }
}

function clearNotifications() {
    const list = document.getElementById('notifications-list');
    const countBadge = document.getElementById('notification-count');
    
    if (list) {
        list.innerHTML = `
            <div class="no-notifications">
                <i class="fas fa-bell-slash"></i>
                <p>No notifications</p>
            </div>
        `;
    }
    
    if (countBadge) {
        countBadge.style.display = 'none';
    }
}

// ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

function switchTab(tabName) {
    // Скрываем все вкладки
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Показываем выбранную вкладку
    const tabContent = document.getElementById(tabName + '-tab');
    const tabElement = document.querySelector(`.tab[data-tab="${tabName}"]`);
    
    if (tabContent) tabContent.classList.add('active');
    if (tabElement) tabElement.classList.add('active');
    
    // Обновляем данные если нужно
    switch (tabName) {
        case 'monitoring':
            updateTrafficChart();
            break;
        case 'services':
            if (typeof window.loadServicesStatus === 'function') {
                window.loadServicesStatus();
            }
            break;
        case 'export':
            loadExportSettings();
            break;
    }
}

// ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================

async function showUserConfig(userId, username) {
    try {
        console.log('Fetching config for user:', userId);
        
        const response = await fetch(getUserConfigUrl(userId));
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            console.log('Config received:', data.config);
            
            const modal = document.getElementById('configModal');
            if (modal) {
                modal.querySelector('.modal-content').innerHTML = `
                    <div class="modal-header">
                        <div class="modal-title">
                            <i class="fas fa-code"></i>
                            <div class="modal-title-content">
                                <h2>Configuration</h2>
                                <div class="modal-subtitle">${username || 'User'}</div>
                            </div>
                        </div>
                        <button class="modal-close" onclick="closeModal('configModal')" aria-label="Close">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    
                    <div class="modal-body config-modal-body">
                        <div class="config-sections">
                            <!-- Connection Details -->
                            <div class="config-section">
                                <div class="section-header">
                                    <i class="fas fa-network-wired"></i>
                                    <h3>Connection Details</h3>
                                </div>
                                <div class="config-grid">
                                    <div class="config-item">
                                        <div class="config-label">
                                            <i class="fas fa-server"></i>
                                            <span>Server</span>
                                        </div>
                                        <div class="config-value">
                                            <input type="text" value="${data.config.server}" id="server-config" readonly>
                                            <button class="copy-btn" onclick="copyConfig('server-config')" 
                                                    title="Copy to clipboard">
                                                <i class="fas fa-copy"></i>
                                            </button>
                                        </div>
                                    </div>
                                    <div class="config-item">
                                        <div class="config-label">
                                            <i class="fas fa-plug"></i>
                                            <span>Port</span>
                                        </div>
                                        <div class="config-value">
                                            <input type="text" value="${data.config.port}" id="port-config" readonly>
                                            <button class="copy-btn" onclick="copyConfig('port-config')"
                                                    title="Copy to clipboard">
                                                <i class="fas fa-copy"></i>
                                            </button>
                                        </div>
                                    </div>
                                    <div class="config-item">
                                        <div class="config-label">
                                            <i class="fas fa-key"></i>
                                            <span>Password</span>
                                        </div>
                                        <div class="config-value">
                                            <div class="password-wrapper">
                                                <input type="password" value="${data.config.password}" 
                                                       id="password-config" readonly>
                                                <button class="copy-btn" onclick="copyConfig('password-config')"
                                                        title="Copy to clipboard">
                                                    <i class="fas fa-copy"></i>
                                                </button>
                                                <button class="show-btn" onclick="togglePasswordVisibility('password-config')"
                                                        title="Show password">
                                                    <i class="fas fa-eye"></i>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="config-item">
                                        <div class="config-label">
                                            <i class="fas fa-lock"></i>
                                            <span>Method</span>
                                        </div>
                                        <div class="config-value">
                                            <input type="text" value="${data.config.method}" id="method-config" readonly>
                                            <button class="copy-btn" onclick="copyConfig('method-config')"
                                                    title="Copy to clipboard">
                                                <i class="fas fa-copy"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Shadowsocks URL -->
                            <div class="config-section">
                                <div class="section-header">
                                    <i class="fas fa-link"></i>
                                    <h3>Quick Import</h3>
                                </div>
                                <div class="ss-url-section">
                                    <div class="ss-url-input">
                                        <textarea id="ssurl-config" readonly rows="3">${data.config.ss_url_with_comment || data.config.ss_url}</textarea>
                                        <button class="copy-btn-lg" onclick="copyConfig('ssurl-config')">
                                            <i class="fas fa-copy"></i>
                                            Copy URL
                                        </button>
                                    </div>
                                    
                                    <div class="qrcode-section">
                                        <div class="qrcode-header">
                                            <i class="fas fa-qrcode"></i>
                                            <span>QR Code</span>
                                        </div>
                                        <div class="qrcode-container">
                                            <div id="qrcode"></div>
                                            <div class="qrcode-note">Scan to import configuration</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Account Info -->
                            <div class="config-section">
                                <div class="section-header">
                                    <i class="fas fa-user-circle"></i>
                                    <h3>Account Information</h3>
                                </div>
                                <div class="account-info">
                                    <div class="info-item">
                                        <span class="info-label">Username:</span>
                                        <span class="info-value">${data.config.username || username || 'Unknown'}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">Traffic Used:</span>
                                        <span class="info-value">${data.config.traffic_used_gb || '0'} GB</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">Traffic Limit:</span>
                                        <span class="info-value">${data.config.traffic_limit_gb || 'Unlimited'} GB</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">Expires:</span>
                                        <span class="info-value">${data.config.expires_at ? new Date(data.config.expires_at).toLocaleDateString() : 'Never'}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="modal-footer">
                        <div class="action-buttons">
                            <button class="btn btn-outline" onclick="downloadUserConfig('${userId}')">
                                <i class="fas fa-download"></i>
                                Download Config
                            </button>
                            <button class="btn btn-secondary" onclick="closeModal('configModal')">
                                <i class="fas fa-times"></i>
                                Close
                            </button>
                            <button class="btn btn-primary" onclick="shareConfig('${data.config.ss_url_with_comment || data.config.ss_url}')">
                                <i class="fas fa-share-alt"></i>
                                Share
                            </button>
                        </div>
                    </div>
                `;
                
                // Generate QR code
                if (typeof QRCode !== 'undefined') {
                    const qrcodeElement = document.getElementById('qrcode');
                    if (qrcodeElement) {
                        qrcodeElement.innerHTML = '';
                        new QRCode(qrcodeElement, {
                            text: data.config.ss_url_with_comment || data.config.ss_url,
                            width: 180,
                            height: 180,
                            colorDark: '#2d3748',
                            colorLight: '#ffffff',
                            correctLevel: QRCode.CorrectLevel.H
                        });
                    }
                }
                
                modal.style.display = 'flex';
                modal.style.opacity = '1';
                document.body.style.overflow = 'hidden';
                
                console.log('Modal displayed');
            }
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error loading configuration:', error);
        showToast('Error loading configuration: ' + error.message, 'error');
    }
}

function downloadUserConfig(userId) {
    window.open(getUserDownloadUrl(userId), '_blank');
}

function resetUserTraffic(userId) {
    if (!confirm('Are you sure you want to reset traffic for this user?')) return;
    
    fetch(getResetTrafficUrl(userId), {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Traffic reset successfully', 'success');
            loadUsers();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        showToast('Error: ' + error.message, 'error');
    });
}

function toggleUserService(userId, enable) {
    fetch(getToggleServiceUrl(userId), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ enable: enable })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`Service ${enable ? 'started' : 'stopped'} successfully`, 'success');
            loadUsers();
            loadServicesOverview();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        showToast('Error: ' + error.message, 'error');
    });
}

function extendUser(userId) {
    const days = prompt('Enter number of days to extend:', '30');
    if (!days || isNaN(days)) return;
    
    fetch(getExtendUserUrl(userId), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ additional_days: parseInt(days) })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`User extended by ${days} days`, 'success');
            loadUsers();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        showToast('Error: ' + error.message, 'error');
    });
}

function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) return;
    
    fetch(getDeleteUserUrl(userId), {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('User deleted successfully', 'success');
            loadUsers();
            loadServicesOverview();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        showToast('Error: ' + error.message, 'error');
    });
}

// ==================== УПРАВЛЕНИЕ СЛУЖБАМИ (АДМИН) ====================

function initializeAdmin() {
    if (!confirm('Initialize admin service? This will create admin user and service.')) return;
    
    fetch(getApiUrl('admin.initialize'), {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Admin initialized successfully', 'success');
            loadServicesOverview();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        showToast('Error: ' + error.message, 'error');
    });
}

function syncServices() {
    if (!confirm('Sync all services with users? This will create services for users without them.')) return;
    
    fetch(getApiUrl('services.sync'), {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Services synced successfully', 'success');
            loadServicesOverview();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        showToast('Error: ' + error.message, 'error');
    });
}

function restartAllServices() {
    if (!confirm('Restart all services? This may cause brief connectivity interruption.')) return;
    
    fetch(getApiUrl('services.restart-all'), {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('All services restarted successfully', 'success');
            loadServicesOverview();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        showToast('Error: ' + error.message, 'error');
    });
}

function reloadAllServices() {
    if (!confirm('Reload all services? This will reload configuration without restarting.')) return;
    
    fetch(getApiUrl('services.reload-all'), {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('All services reloaded successfully', 'success');
            loadServicesOverview();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        showToast('Error: ' + error.message, 'error');
    });
}

function checkAllServices() {
    showToast('Checking services status...', 'info');
    loadServicesOverview();
}

// ==================== ЭКСПОРТ ====================

function loadExportSettings() {
    try {
        const autoBackup = localStorage.getItem('autoBackup') === 'true';
        const autoReport = localStorage.getItem('autoReport') === 'true';
        
        const autoBackupCheckbox = document.getElementById('auto-backup');
        const autoReportCheckbox = document.getElementById('auto-report');
        
        if (autoBackupCheckbox) autoBackupCheckbox.checked = autoBackup;
        if (autoReportCheckbox) autoReportCheckbox.checked = autoReport;
    } catch (error) {
        console.error('Error loading export settings:', error);
    }
}

function toggleAutoBackup() {
    const checkbox = document.getElementById('auto-backup');
    if (checkbox) {
        localStorage.setItem('autoBackup', checkbox.checked.toString());
        showToast(`Auto backup ${checkbox.checked ? 'enabled' : 'disabled'}`, 'info');
    }
}

function toggleAutoReport() {
    const checkbox = document.getElementById('auto-report');
    if (checkbox) {
        localStorage.setItem('autoReport', checkbox.checked.toString());
        showToast(`Auto reports ${checkbox.checked ? 'enabled' : 'disabled'}`, 'info');
    }
}

function exportAllConfigs() {
    showToast('Exporting all configurations...', 'info');
    // Здесь будет логика экспорта
}

function exportUsersCSV() {
    showToast('Exporting users as CSV...', 'info');
    // Здесь будет логика экспорта CSV
}

function exportTrafficReport() {
    showToast('Generating traffic report...', 'info');
    // Здесь будет логика генерации отчета
}

function backupDatabase() {
    showToast('Creating database backup...', 'info');
    // Здесь будет логика бэкапа
}

// ==================== УТИЛИТЫ ====================

function copyTextToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Failed to copy to clipboard', 'error');
    });
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.style.display = 'block';
    
    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

// ==================== ФУНКЦИИ ДЛЯ HTML ====================

// Делаем функции глобальными для использования в HTML
window.switchTab = switchTab;
window.loadDashboard = loadDashboard;
window.openNotifications = openNotifications;
window.checkNotifications = checkNotifications;
window.clearNotifications = clearNotifications;
window.initializeAdmin = initializeAdmin;
window.syncServices = syncServices;
window.restartAllServices = restartAllServices;
window.reloadAllServices = reloadAllServices;
window.checkAllServices = checkAllServices;
window.showUserConfig = showUserConfig;
window.downloadUserConfig = downloadUserConfig;
window.resetUserTraffic = resetUserTraffic;
window.toggleUserService = toggleUserService;
window.extendUser = extendUser;
window.deleteUser = deleteUser;
window.exportAllConfigs = exportAllConfigs;
window.exportUsersCSV = exportUsersCSV;
window.exportTrafficReport = exportTrafficReport;
window.backupDatabase = backupDatabase;
window.toggleAutoBackup = toggleAutoBackup;
window.toggleAutoReport = toggleAutoReport;
window.copyTextToClipboard = copyTextToClipboard;
window.getApiUrl = getApiUrl;
window.usersData = usersData; // Экспортируем глобально