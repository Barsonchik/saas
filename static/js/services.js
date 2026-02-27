// services.js - Управление службами Shadowsocks
// =============================================

let servicesData = [];
let servicesPollingInterval = null;
let lastUpdateTime = null;
let isUpdating = false; // Флаг для предотвращения множественных обновлений

// Инициализация управления службами
function initServicesManager() {
    console.log('Initializing Services Manager...');
    loadServicesStatus();
    
    // Запуск автоматического обновления
    startServicesPolling();
    
    // Инициализация обработчиков событий
    setupServiceEventHandlers();
}

// Настройка обработчиков событий
function setupServiceEventHandlers() {
    // Обработчик для кнопки обновления
    const refreshBtn = document.getElementById('refresh-services-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadServicesStatus(true);
        });
    }
    
    // Обработчик для массового выбора
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('select-all-services')) {
            selectAllServices();
        } else if (e.target.classList.contains('deselect-all-services')) {
            deselectAllServices();
        }
    });
}

// Загрузить статус всех служб
async function loadServicesStatus(forceRefresh = false) {
    // Предотвращаем множественные вызовы
    if (isUpdating && !forceRefresh) {
        console.log('Already updating services, skipping...');
        return;
    }
    
    console.log('Loading services status...');
    isUpdating = true;
    
    try {
        // Показать индикатор загрузки
        showServicesLoading(true);
        
        const url = getApiUrl('services.status');
        console.log('Fetching from:', url);
        
        const response = await fetch(url);
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Received data:', data);
        
        if (data.success) {
            // Данные приходят в поле user_services
            if (data.user_services && Array.isArray(data.user_services)) {
                servicesData = data.user_services;
                window.servicesData = servicesData; // Сохраняем глобально
                console.log('Services data from user_services:', servicesData);
            } else {
                servicesData = [];
                window.servicesData = [];
                console.log('No user_services array found');
            }
            
            lastUpdateTime = new Date();
            
            // Обновляем отображение в зависимости от текущей вкладки
            updateServicesDisplayBasedOnTab();
            
            // Сохранить в localStorage для офлайн-доступа
            saveServicesToLocalStorage();
            
            // Обновить время последнего обновления
            updateLastUpdateTime();
            
            // Проверяем соответствие пользователей и служб
            checkUserServiceMatch();
        } else {
            console.error('Failed to load services:', data.message);
            showToast('Failed to load services: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error loading services status:', error);
        
        // Попробовать загрузить из localStorage при ошибке сети
        const cachedServices = getServicesFromLocalStorage();
        if (cachedServices && cachedServices.length > 0) {
            servicesData = cachedServices;
            window.servicesData = cachedServices;
            updateServicesDisplayBasedOnTab();
            showToast('Using cached services data (offline mode)', 'warning');
        } else {
            showToast('Error loading services: ' + error.message, 'error');
        }
    } finally {
        showServicesLoading(false);
        isUpdating = false;
    }
}

// Проверка соответствия пользователей и служб
function checkUserServiceMatch() {
    console.log('Checking user-service match...');
    console.log('window.usersData:', window.usersData);
    console.log('window.servicesData:', window.servicesData);
    
    if (window.usersData && window.usersData.length > 0 && 
        window.servicesData && window.servicesData.length > 0) {
        
        console.log('=== User-Service Mapping ===');
        window.usersData.forEach(user => {
            const service = window.servicesData.find(s => 
                s.username === user.username || 
                (s.service_name && s.service_name.includes(user.username))
            );
            console.log(`User ${user.username} (port ${user.port}) -> ${service ? service.service_name : 'NO SERVICE'}`);
        });
    } else {
        console.log('Waiting for data to load...');
    }
}

// Обновить отображение в зависимости от текущей вкладки
function updateServicesDisplayBasedOnTab() {
    // Определяем, какая вкладка активна
    const activeTab = document.querySelector('.tab-content.active');
    
    if (activeTab) {
        if (activeTab.id === 'services-tab') {
            // Мы на вкладке Services - показываем полный список
            updateServicesStatusDisplay();
        } else if (activeTab.id === 'dashboard-tab') {
            // Мы на Dashboard - показываем обзор
            updateServicesOverview(servicesData);
        }
    }
}

// Показать/скрыть индикатор загрузки
function showServicesLoading(show) {
    // Проверяем, на какой вкладке мы находимся
    const servicesContainer = document.getElementById('services-status');
    const overviewContainer = document.getElementById('services-overview');
    const activeTab = document.querySelector('.tab-content.active');
    
    if (show) {
        // Показываем индикатор загрузки в соответствующем контейнере
        if (activeTab?.id === 'services-tab' && servicesContainer) {
            servicesContainer.innerHTML = `
                <div class="services-loading">
                    <div class="loading-spinner"></div>
                    <p>Loading services status...</p>
                </div>
            `;
        } else if (activeTab?.id === 'dashboard-tab' && overviewContainer) {
            overviewContainer.innerHTML = `
                <div class="services-loading">
                    <div class="loading-spinner"></div>
                    <p>Loading services overview...</p>
                </div>
            `;
        }
    }
}

// Обновить отображение статуса служб (для вкладки Services)
function updateServicesStatusDisplay() {
    const container = document.getElementById('services-status');
    if (!container) return;
    
    if (!servicesData || servicesData.length === 0) {
        container.innerHTML = `
            <div class="no-services">
                <div class="no-services-icon">
                    <i class="fas fa-server fa-3x"></i>
                </div>
                <h3>No Services Found</h3>
                <p>No services are currently configured. You can:</p>
                <div class="no-services-actions">
                    <button class="btn btn-primary" onclick="syncServices()">
                        <i class="fas fa-sync"></i> Sync Services
                    </button>
                    <button class="btn btn-outline" onclick="initializeAdmin()">
                        <i class="fas fa-user-shield"></i> Initialize Admin
                    </button>
                </div>
            </div>
        `;
        return;
    }
    
    let html = '';
    let runningCount = 0;
    let stoppedCount = 0;
    
    servicesData.forEach((service, index) => {
        // Статус берем из поля active
        const isActive = service.active === true;
        const isEnabled = service.enabled === true;
        
        // Username уже есть в данных
        const username = service.username || 'Unknown';
        let port = 'N/A';
        let method = 'N/A';
        
        // Пытаемся найти порт из данных пользователя
        if (service.port) {
            port = service.port;
        } else if (window.usersData && window.usersData.length > 0) {
            // Ищем пользователя по username
            const user = window.usersData.find(u => u.username === username);
            if (user && user.port) {
                port = user.port;
            }
            if (user && user.method) {
                method = user.method;
            }
        }
        
        if (isActive) runningCount++;
        else stoppedCount++;
        
        html += `
            <div class="service-item ${isActive ? 'service-running' : 'service-stopped'}" 
                 data-service="${service.service_name}" 
                 data-username="${username}">
                <div class="service-item-header">
                    <div class="service-name">
                        <div class="service-name-main">
                            <strong>${service.service_name}</strong>
                            <span class="service-badge ${isActive ? 'badge-success' : 'badge-danger'}">
                                <i class="fas fa-circle"></i>
                                ${isActive ? 'RUNNING' : 'STOPPED'}
                            </span>
                        </div>
                        <div class="service-name-sub">
                            <span class="user-info">
                                <i class="fas fa-user"></i>
                                ${username}
                            </span>
                            <span class="port-info">
                                <i class="fas fa-plug"></i>
                                Port: ${port}
                            </span>
                            <span class="method-info">
                                <i class="fas fa-lock"></i>
                                ${method}
                            </span>
                        </div>
                    </div>
                    
                    <div class="service-actions">
                        <button class="btn btn-icon ${isActive ? 'btn-warning' : 'btn-success'}" 
                                onclick="controlService('${service.service_name}', '${isActive ? 'stop' : 'start'}')"
                                title="${isActive ? 'Stop Service' : 'Start Service'}">
                            <i class="fas ${isActive ? 'fa-stop' : 'fa-play'}"></i>
                        </button>
                        <button class="btn btn-icon btn-info" 
                                onclick="controlService('${service.service_name}', 'restart')"
                                title="Restart Service">
                            <i class="fas fa-redo"></i>
                        </button>
                        <button class="btn btn-icon" 
                                onclick="showServiceDetails('${service.service_name}', '${username}')"
                                title="Service Details">
                            <i class="fas fa-info-circle"></i>
                        </button>
                        <button class="btn btn-icon btn-outline" 
                                onclick="viewServiceLogs('${service.service_name}')"
                                title="View Logs">
                            <i class="fas fa-terminal"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// Функция для обновления обзора служб на Dashboard
function updateServicesOverview(services) {
    const container = document.getElementById('services-overview');
    if (!container) {
        console.log('Services overview container not found');
        return;
    }
    
    // Проверяем, не обновляем ли мы уже
    if (container.hasAttribute('data-updating')) {
        console.log('Already updating overview, skipping...');
        return;
    }
    
    console.log('Updating services overview with:', services);
    container.setAttribute('data-updating', 'true');
    
    if (!services || services.length === 0) {
        container.innerHTML = `
            <div class="no-data">
                <i class="fas fa-server"></i>
                <p>No services found. Add a user to create a service.</p>
            </div>
        `;
        container.removeAttribute('data-updating');
        return;
    }
    
    let html = '<div class="services-grid">';
    
    services.forEach(service => {
        // Статус из поля active
        const isActive = service.active === true;
        const isEnabled = service.enabled === true;
        
        // Username из данных
        const username = service.username || 'Unknown';
        let port = 'N/A';
        
        // Пытаемся найти порт из данных пользователя
        if (service.port) {
            port = service.port;
        } else if (window.usersData && window.usersData.length > 0) {
            // Сначала ищем точное совпадение по username
            let user = window.usersData.find(u => u.username === username);
            
            // Если не нашли, пробуем извлечь username из имени службы
            if (!user) {
                const serviceName = service.service_name || '';
                const extractedName = serviceName
                    .replace('shadowsocks-', '')
                    .replace('.service', '');
                user = window.usersData.find(u => u.username === extractedName);
            }
            
            if (user && user.port) {
                port = user.port;
            }
        }
        
        html += `
            <div class="service-card">
                <div class="service-card-header">
                    <div class="service-card-title">${service.service_name}</div>
                    <div class="service-status ${isActive ? 'service-running' : 'service-stopped'}">
                        <i class="fas fa-circle"></i>
                        ${isActive ? 'Running' : 'Stopped'}
                    </div>
                </div>
                <div class="service-card-body">
                    <div class="service-info-item">
                        <span class="service-info-label">Username:</span>
                        <span class="service-info-value">${username}</span>
                    </div>
                    <div class="service-info-item">
                        <span class="service-info-label">Port:</span>
                        <span class="service-info-value">${port}</span>
                    </div>
                    <div class="service-info-item">
                        <span class="service-info-label">Enabled:</span>
                        <span class="service-info-value ${isEnabled ? 'status-active' : 'status-inactive'}">
                            <i class="fas fa-circle"></i>
                            ${isEnabled ? 'Yes' : 'No'}
                        </span>
                    </div>
                </div>
                <div class="service-card-actions">
                    <button class="btn btn-xs" onclick="showServiceDetails('${service.service_name}', '${username}')">
                        <i class="fas fa-info-circle"></i> Details
                    </button>
                    <button class="btn btn-xs btn-info" onclick="restartServiceByName('${service.service_name}')">
                        <i class="fas fa-redo"></i> Restart
                    </button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
    container.removeAttribute('data-updating');
}

// Обновить сводку служб (только для вкладки Services)
function updateServicesSummary() {
    const summaryEl = document.getElementById('services-summary');
    if (!summaryEl) return;
    
    const runningCount = servicesData.filter(s => s.active === true).length;
    const stoppedCount = servicesData.length - runningCount;
    
    summaryEl.innerHTML = `
        <div class="summary-card running">
            <div class="summary-icon">
                <i class="fas fa-play-circle"></i>
            </div>
            <div class="summary-content">
                <div class="summary-count">${runningCount}</div>
                <div class="summary-label">Running Services</div>
            </div>
        </div>
        <div class="summary-card stopped">
            <div class="summary-icon">
                <i class="fas fa-stop-circle"></i>
            </div>
            <div class="summary-content">
                <div class="summary-count">${stoppedCount}</div>
                <div class="summary-label">Stopped Services</div>
            </div>
        </div>
        <div class="summary-card total">
            <div class="summary-icon">
                <i class="fas fa-server"></i>
            </div>
            <div class="summary-content">
                <div class="summary-count">${servicesData.length}</div>
                <div class="summary-label">Total Services</div>
            </div>
        </div>
        <div class="summary-card health">
            <div class="summary-icon">
                <i class="fas fa-heartbeat"></i>
            </div>
            <div class="summary-content">
                <div class="summary-count">${servicesData.length > 0 ? Math.round((runningCount / servicesData.length) * 100) : 0}%</div>
                <div class="summary-label">Health Score</div>
            </div>
        </div>
    `;
}

// Обновить время последнего обновления
function updateLastUpdateTime() {
    const updateEl = document.getElementById('last-update-time');
    if (updateEl && lastUpdateTime) {
        updateEl.textContent = formatTime(lastUpdateTime);
        updateEl.title = lastUpdateTime.toLocaleString();
    }
}

// Форматирование времени
function formatTime(date) {
    if (!date) return 'N/A';
    
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    
    return date.toLocaleDateString();
}

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Копирование в буфер обмена
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const text = element.textContent;
        navigator.clipboard.writeText(text).then(() => {
            showToast('Copied to clipboard', 'success');
        }).catch(() => {
            showToast('Failed to copy', 'error');
        });
    }
}

// Управление выборами служб
function selectAllServices() {
    const checkboxes = document.querySelectorAll('.service-select');
    checkboxes.forEach(cb => cb.checked = true);
    updateSelectionCount();
    showToast('All services selected', 'info');
}

function deselectAllServices() {
    const checkboxes = document.querySelectorAll('.service-select');
    checkboxes.forEach(cb => cb.checked = false);
    updateSelectionCount();
    showToast('All services deselected', 'info');
}

function updateSelectionCount() {
    const selectedCount = document.querySelectorAll('.service-select:checked').length;
    const countEl = document.getElementById('selected-count');
    if (countEl) {
        countEl.textContent = selectedCount;
        countEl.style.display = selectedCount > 0 ? 'inline' : 'none';
    }
}

function getSelectedServices() {
    const selected = [];
    document.querySelectorAll('.service-select:checked').forEach(checkbox => {
        const serviceItem = checkbox.closest('.service-item');
        if (serviceItem) {
            selected.push({
                name: serviceItem.dataset.service,
                username: serviceItem.dataset.username
            });
        }
    });
    return selected;
}

// Массовые операции с выбранными службами
async function startSelectedServices() {
    const selected = getSelectedServices();
    if (selected.length === 0) {
        showToast('No services selected', 'warning');
        return;
    }
    
    if (!confirm(`Start ${selected.length} selected service(s)?`)) return;
    
    try {
        showToast(`Starting ${selected.length} service(s)...`, 'info');
        
        for (const service of selected) {
            await controlService(service.name, 'start');
        }
        
        showToast(`Successfully started ${selected.length} service(s)`, 'success');
        deselectAllServices();
    } catch (error) {
        showToast('Error starting services: ' + error.message, 'error');
    }
}

async function stopSelectedServices() {
    const selected = getSelectedServices();
    if (selected.length === 0) {
        showToast('No services selected', 'warning');
        return;
    }
    
    if (!confirm(`Stop ${selected.length} selected service(s)?`)) return;
    
    try {
        showToast(`Stopping ${selected.length} service(s)...`, 'info');
        
        for (const service of selected) {
            await controlService(service.name, 'stop');
        }
        
        showToast(`Successfully stopped ${selected.length} service(s)`, 'success');
        deselectAllServices();
    } catch (error) {
        showToast('Error stopping services: ' + error.message, 'error');
    }
}

async function restartSelectedServices() {
    const selected = getSelectedServices();
    if (selected.length === 0) {
        showToast('No services selected', 'warning');
        return;
    }
    
    if (!confirm(`Restart ${selected.length} selected service(s)?`)) return;
    
    try {
        showToast(`Restarting ${selected.length} service(s)...`, 'info');
        
        for (const service of selected) {
            await controlService(service.name, 'restart');
        }
        
        showToast(`Successfully restarted ${selected.length} service(s)`, 'success');
        deselectAllServices();
    } catch (error) {
        showToast('Error restarting services: ' + error.message, 'error');
    }
}

// Перезапустить службу по имени
async function restartServiceByName(serviceName) {
    try {
        showToast(`Restarting ${serviceName}...`, 'info');
        
        const response = await fetch(getApiUrl('service.control'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                service: serviceName,
                action: 'restart'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`Service ${serviceName} restarted`, 'success');
            loadServicesStatus();
        } else {
            showToast('Error: ' + (data.message || data.error), 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Управление службой
async function controlService(serviceName, action) {
    console.log(`Controlling service: ${serviceName}, action: ${action}`);
    
    try {
        showToast(`${action} service ${serviceName}...`, 'info');
        
        const response = await fetch(getApiUrl('service.control'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                service: serviceName,
                action: action
            })
        });
        
        const data = await response.json();
        console.log('Control response:', data);
        
        if (data.success) {
            showToast(`Service ${action}ed successfully`, 'success');
            
            // Обновляем статус в UI
            await loadServicesStatus();
            
            // Если есть функция обновления пользователей, вызываем её
            if (typeof window.loadUsers === 'function') {
                window.loadUsers();
            }
        } else {
            showToast('Error: ' + (data.message || data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Control error:', error);
        showToast('Error: ' + error.message, 'error');
    }
}

// Показать детали службы
function showServiceDetails(serviceName, username) {
    // Находим службу
    const service = servicesData.find(s => s.service_name === serviceName);
    
    if (!service) {
        showToast('Service not found', 'error');
        return;
    }
    
    // Находим пользователя если есть данные
    let user = null;
    if (window.usersData && window.usersData.length > 0) {
        user = window.usersData.find(u => u.username === username);
    }
    
    const isActive = service.active === true;
    const isEnabled = service.enabled === true;
    const port = service.port || (user ? user.port : 'N/A');
    const method = service.method || (user ? user.method : 'aes-256-gcm');
    const trafficUsed = user ? `${user.traffic_used_gb} / ${user.traffic_limit_gb} GB` : 'N/A';
    const trafficPercent = user ? user.traffic_percent || 0 : 0;
    
    const modalContent = `
        <div class="service-details-modal">
            <div class="service-header">
                <h3>${serviceName}</h3>
                <span class="service-status-badge ${isActive ? 'badge-success' : 'badge-danger'}">
                    <i class="fas fa-circle"></i>
                    ${isActive ? 'Running' : 'Stopped'}
                </span>
            </div>
            
            <div class="service-info-grid">
                <div class="info-row">
                    <div class="info-label">
                        <i class="fas fa-user"></i> Username:
                    </div>
                    <div class="info-value">${username}</div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">
                        <i class="fas fa-plug"></i> Port:
                    </div>
                    <div class="info-value">${port}</div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">
                        <i class="fas fa-lock"></i> Method:
                    </div>
                    <div class="info-value">${method}</div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">
                        <i class="fas fa-toggle-on"></i> Enabled at boot:
                    </div>
                    <div class="info-value ${isEnabled ? 'text-success' : 'text-danger'}">
                        <i class="fas fa-${isEnabled ? 'check-circle' : 'times-circle'}"></i>
                        ${isEnabled ? 'Yes' : 'No'}
                    </div>
                </div>
                
                ${user ? `
                <div class="info-row">
                    <div class="info-label">
                        <i class="fas fa-database"></i> Traffic:
                    </div>
                    <div class="info-value">
                        <div class="traffic-mini-bar">
                            <div class="traffic-mini-fill" style="width: ${trafficPercent}%"></div>
                        </div>
                        ${trafficUsed}
                    </div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">
                        <i class="fas fa-calendar-alt"></i> Expires:
                    </div>
                    <div class="info-value">
                        ${user.expires_at ? new Date(user.expires_at).toLocaleDateString() : 'Never'}
                        ${user.days_remaining !== undefined ? `(${user.days_remaining} days left)` : ''}
                    </div>
                </div>
                ` : ''}
            </div>
            
            <div class="service-actions-group">
                <h4>Service Controls</h4>
                <div class="action-buttons">
                    <button class="btn ${isActive ? 'btn-warning' : 'btn-success'}" 
                            onclick="controlService('${serviceName}', '${isActive ? 'stop' : 'start'}')">
                        <i class="fas ${isActive ? 'fa-stop' : 'fa-play'}"></i>
                        ${isActive ? 'Stop' : 'Start'}
                    </button>
                    
                    <button class="btn btn-info" onclick="controlService('${serviceName}', 'restart')">
                        <i class="fas fa-redo"></i>
                        Restart
                    </button>
                    
                    <button class="btn btn-primary" onclick="controlService('${serviceName}', 'reload')">
                        <i class="fas fa-sync-alt"></i>
                        Reload
                    </button>
                    
                    <button class="btn btn-secondary" onclick="viewServiceLogs('${serviceName}')">
                        <i class="fas fa-terminal"></i>
                        View Logs
                    </button>
                </div>
            </div>
            
            ${user ? `
            <div class="user-actions-group">
                <h4>User Management</h4>
                <div class="action-buttons">
                    <button class="btn btn-outline" onclick="showUserConfig('${user._id}', '${username}')">
                        <i class="fas fa-code"></i>
                        View Config
                    </button>
                    
                    <button class="btn btn-outline" onclick="downloadUserConfig('${user._id}')">
                        <i class="fas fa-download"></i>
                        Download Config
                    </button>
                    
                    <button class="btn btn-outline" onclick="resetUserTraffic('${user._id}')">
                        <i class="fas fa-redo-alt"></i>
                        Reset Traffic
                    </button>
                </div>
            </div>
            ` : ''}
        </div>
    `;
    
    // Показываем модальное окно
    const modal = document.getElementById('serviceInfoModal');
    if (modal) {
        const modalContentDiv = modal.querySelector('.modal-content');
        modalContentDiv.innerHTML = `
            <div class="modal-header">
                <h2><i class="fas fa-server"></i> Service Details</h2>
                <button class="modal-close" onclick="closeModal('serviceInfoModal')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                ${modalContent}
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeModal('serviceInfoModal')">
                    Close
                </button>
            </div>
        `;
        
        modal.style.display = 'flex';
        modal.style.opacity = '1';
        document.body.style.overflow = 'hidden';
    }
}

// Просмотр логов службы
async function viewServiceLogs(serviceName) {
    console.log(`Fetching logs for service: ${serviceName}`);
    
    try {
        showToast(`Fetching logs for ${serviceName}...`, 'info');
        
        // Используем эндпоинт для логов
        const response = await fetch(`/api/services/${serviceName}/logs?lines=100`);
        const data = await response.json();
        
        console.log('Logs response:', data);
        
        if (data.success) {
            const logs = data.logs || 'No logs available';
            showServiceLogsModal(serviceName, logs);
        } else {
            // Если эндпоинт не сработал, показываем заглушку с информацией
            showServiceLogsModal(serviceName, 
                `Logs for ${serviceName}\n` +
                `Status: Service is ${getServiceStatus(serviceName)}\n` +
                `To view full logs, run: journalctl -u ${serviceName} -n 100\n` +
                `\nCurrent time: ${new Date().toLocaleString()}`
            );
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
        
        // В случае ошибки показываем модальное окно с заглушкой
        showServiceLogsModal(serviceName, 
            `Error fetching logs: ${error.message}\n\n` +
            `Service: ${serviceName}\n` +
            `Time: ${new Date().toLocaleString()}`
        );
    }
}

// Получить статус службы (вспомогательная функция)
function getServiceStatus(serviceName) {
    const service = servicesData.find(s => s.service_name === serviceName);
    return service ? (service.active ? 'running' : 'stopped') : 'unknown';
}

// Показать модальное окно с логами
function showServiceLogsModal(serviceName, logs) {
    const modalId = 'serviceLogsModal';
    let modal = document.getElementById(modalId);
    
    if (!modal) {
        modal = document.createElement('div');
        modal.id = modalId;
        modal.className = 'modal';
        document.body.appendChild(modal);
    }
    
    modal.innerHTML = `
        <div class="modal-content modal-lg">
            <div class="modal-header">
                <h2><i class="fas fa-terminal"></i> Service Logs: ${serviceName}</h2>
                <button class="modal-close" onclick="closeModal('${modalId}')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="logs-controls">
                    <button class="btn btn-sm" onclick="refreshServiceLogs('${serviceName}')">
                        <i class="fas fa-sync"></i> Refresh
                    </button>
                    <button class="btn btn-sm" onclick="copyToClipboard('logs-content')">
                        <i class="fas fa-copy"></i> Copy
                    </button>
                    <span class="logs-info">
                        Showing last 100 lines
                    </span>
                </div>
                <pre id="logs-content" class="logs-content">${escapeHtml(logs)}</pre>
            </div>
        </div>
    `;
    
    modal.style.display = 'block';
}

// Обновить логи
async function refreshServiceLogs(serviceName) {
    closeModal('serviceLogsModal');
    await viewServiceLogs(serviceName);
}

// Инициализировать админ службу
async function initializeAdmin() {
    if (!confirm('Initialize admin service? This will create the main Shadowsocks service.')) {
        return;
    }
    
    try {
        showToast('Initializing admin service...', 'info');
        
        const response = await fetch(getApiUrl('admin.initialize'), {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Admin service initialized successfully!', 'success');
            loadServicesStatus();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Синхронизировать службы
async function syncServices() {
    if (!confirm('Sync services? This will create services for all users.')) {
        return;
    }
    
    try {
        showToast('Syncing services...', 'info');
        
        const response = await fetch(getApiUrl('services.sync'), {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`Services synced successfully! Created ${data.services_created || 0} services`, 'success');
            loadServicesStatus();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Перезапустить все службы
async function restartAllServices() {
    if (!confirm('Restart all services? This will cause brief connectivity interruption for all users.')) {
        return;
    }
    
    try {
        showToast('Restarting all services...', 'info');
        
        const response = await fetch(getApiUrl('services.restart-all'), {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`All services restarted! ${data.services_restarted || 0} services affected`, 'success');
            loadServicesStatus();
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Управление polling
function startServicesPolling() {
    if (servicesPollingInterval) {
        clearInterval(servicesPollingInterval);
    }
    
    // Обновлять каждые 30 секунд
    servicesPollingInterval = setInterval(() => {
        if (document.visibilityState === 'visible') {
            loadServicesStatus();
        }
    }, 30000);
}

function stopServicesPolling() {
    if (servicesPollingInterval) {
        clearInterval(servicesPollingInterval);
        servicesPollingInterval = null;
    }
}

// LocalStorage функции
function saveServicesToLocalStorage() {
    try {
        localStorage.setItem('shadowsocks-services', JSON.stringify({
            data: servicesData,
            timestamp: new Date().toISOString()
        }));
    } catch (e) {
        console.warn('Failed to save services to localStorage:', e);
    }
}

function getServicesFromLocalStorage() {
    try {
        const saved = localStorage.getItem('shadowsocks-services');
        if (saved) {
            const parsed = JSON.parse(saved);
            // Проверяем, что данные не старше 1 часа
            const age = new Date() - new Date(parsed.timestamp);
            if (age < 3600000) { // 1 час
                return parsed.data;
            }
        }
    } catch (e) {
        console.warn('Failed to load services from localStorage:', e);
    }
    return null;
}

// Просмотр конфигурации службы
async function viewServiceConfig(serviceName) {
    try {
        const username = serviceName.replace('shadowsocks-', '').replace('.service', '');
        
        const usersResponse = await fetch(getApiUrl('users'));
        const usersData = await usersResponse.json();
        
        if (!usersData.success) {
            throw new Error('Failed to fetch users');
        }
        
        const user = usersData.users.find(u => u.username === username);
        
        if (!user) {
            throw new Error(`User ${username} not found`);
        }
        
        // Показываем конфигурацию пользователя
        if (typeof window.showUserConfig === 'function') {
            window.showUserConfig(user._id, username);
        } else {
            showToast('Config view function not available', 'warning');
        }
    } catch (error) {
        console.error('Error viewing config:', error);
        showToast('Error: ' + error.message, 'error');
    }
}

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    initServicesManager();
    
    // Обработчик для остановки polling при уходе со страницы
    window.addEventListener('beforeunload', stopServicesPolling);
    
    // Обработчик видимости страницы
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            // При возвращении на страницу обновляем статус
            loadServicesStatus();
        }
    });
});

// Глобальные функции
window.loadServicesStatus = loadServicesStatus;
window.updateServicesOverview = updateServicesOverview;
window.initializeAdmin = initializeAdmin;
window.syncServices = syncServices;
window.restartAllServices = restartAllServices;
window.controlService = controlService;
window.selectAllServices = selectAllServices;
window.deselectAllServices = deselectAllServices;
window.startSelectedServices = startSelectedServices;
window.stopSelectedServices = stopSelectedServices;
window.restartSelectedServices = restartSelectedServices;
window.viewServiceConfig = viewServiceConfig;
window.viewServiceLogs = viewServiceLogs;
window.refreshServiceLogs = refreshServiceLogs;
window.showServiceDetails = showServiceDetails;
window.restartServiceByName = restartServiceByName;
window.initServicesManager = initServicesManager;
window.servicesData = servicesData; // Экспортируем глобально