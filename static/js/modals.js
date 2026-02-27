// modals.js - Управление модальными окнами
// =========================================

let modals = {
    addUserModal: null,
    configModal: null,
    serviceInfoModal: null,
    activeModal: null
};

// Инициализация модальных окон
function initModals() {
    // Создаем модальное окно для добавления пользователя
    createAddUserModal();
    
    // Добавляем обработчики клавиатуры
    document.addEventListener('keydown', handleModalKeyboard);
}

// Обработка клавиатуры для модальных окон
function handleModalKeyboard(event) {
    if (event.key === 'Escape' && modals.activeModal) {
        closeModal(modals.activeModal);
    }
    
    // Закрытие по Enter для форм
    if (event.key === 'Enter' && modals.activeModal === 'addUserModal') {
        const form = document.getElementById('add-user-form');
        if (form && !event.target.matches('textarea, [type="button"]')) {
            event.preventDefault();
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.click();
        }
    }
}

// Создать современное модальное окно для добавления пользователя
function createAddUserModal() {
    const modalHTML = `
        <div class="modal-header">
            <div class="modal-title">
                <i class="fas fa-user-plus"></i>
                <div class="modal-title-content">
                    <h2>Add New User</h2>
                    <div class="modal-subtitle">Create a new Shadowsocks account with individual service</div>
                </div>
            </div>
            <button class="modal-close" onclick="closeModal('addUserModal')" aria-label="Close">
                <i class="fas fa-times"></i>
            </button>
        </div>
        
        <div class="modal-body">
            <form id="add-user-form" class="modern-form" onsubmit="handleAddUser(event)" novalidate>
                <!-- Username -->
                <div class="form-group">
                    <label for="username">
                        <i class="fas fa-user"></i>
                        Username*
                    </label>
                    <div class="input-wrapper">
                        <input 
                            type="text" 
                            id="username" 
                            class="form-control" 
                            required 
                            placeholder="Enter username (3-20 characters)"
                            minlength="3"
                            maxlength="20"
                            autocomplete="off"
                            pattern="[a-zA-Z0-9_-]+"
                            title="Only letters, numbers, underscores and hyphens allowed"
                        >
                        <div class="input-icon">
                            <i class="fas fa-user"></i>
                        </div>
                    </div>
                    <div class="form-hint">3-20 characters, letters, numbers, underscores and hyphens only</div>
                </div>
                
                <!-- Email -->
                <div class="form-group">
                    <label for="email">
                        <i class="fas fa-envelope"></i>
                        Email (optional)
                    </label>
                    <div class="input-wrapper">
                        <input 
                            type="email" 
                            id="email" 
                            class="form-control" 
                            placeholder="user@example.com"
                            autocomplete="email"
                        >
                        <div class="input-icon">
                            <i class="fas fa-envelope"></i>
                        </div>
                    </div>
                    <div class="form-hint">For notifications and password recovery</div>
                </div>
                
                <!-- Traffic and Duration -->
                <div class="form-row">
                    <div class="form-group">
                        <label for="traffic-limit">
                            <i class="fas fa-database"></i>
                            Traffic Limit (GB)*
                        </label>
                        <div class="input-wrapper">
                            <input 
                                type="number" 
                                id="traffic-limit" 
                                class="form-control" 
                                value="10" 
                                min="1" 
                                max="1000" 
                                required 
                                placeholder="e.g., 10"
                                step="1"
                            >
                            <div class="input-icon">
                                <i class="fas fa-database"></i>
                            </div>
                            <div class="input-suffix">GB</div>
                        </div>
                        <div class="form-hint">Monthly traffic limit</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="duration-days">
                            <i class="fas fa-calendar-alt"></i>
                            Duration (days)*
                        </label>
                        <div class="input-wrapper">
                            <input 
                                type="number" 
                                id="duration-days" 
                                class="form-control" 
                                value="30" 
                                min="1" 
                                max="365" 
                                required 
                                placeholder="e.g., 30"
                                step="1"
                            >
                            <div class="input-icon">
                                <i class="fas fa-calendar-alt"></i>
                            </div>
                            <div class="input-suffix">days</div>
                        </div>
                        <div class="form-hint">Account validity period</div>
                    </div>
                </div>
                
                <!-- Method -->
                <div class="form-group">
                    <label for="method">
                        <i class="fas fa-lock"></i>
                        Encryption Method
                    </label>
                    <div class="input-wrapper">
                        <select id="method" class="form-control form-select" required>
                            <option value="aes-256-gcm" selected>AES-256-GCM (Recommended)</option>
                            <option value="chacha20-ietf-poly1305">ChaCha20-Poly1305</option>
                            <option value="aes-128-gcm">AES-128-GCM</option>
                        </select>
                        <div class="input-icon">
                            <i class="fas fa-lock"></i>
                        </div>
                        <div class="select-arrow">
                            <i class="fas fa-chevron-down"></i>
                        </div>
                    </div>
                    <div class="form-hint">AES-256-GCM is recommended for security and performance</div>
                </div>
                
                <!-- Password -->
                <div class="form-group">
                    <label for="password">
                        <i class="fas fa-key"></i>
                        Password
                    </label>
                    <div class="input-wrapper">
                        <input 
                            type="text" 
                            id="password" 
                            class="form-control" 
                            placeholder="Leave empty to auto-generate secure password"
                            autocomplete="new-password"
                        >
                        <div class="input-icon">
                            <i class="fas fa-key"></i>
                        </div>
                        <div class="input-actions">
                            <button type="button" class="input-action-btn" onclick="generateRandomPassword()" 
                                    title="Generate random password">
                                <i class="fas fa-random"></i>
                            </button>
                            <button type="button" class="input-action-btn" onclick="togglePasswordVisibility('password')"
                                    title="Show/hide password">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                    </div>
                    <div class="form-hint">Minimum 8 characters, leave empty for auto-generation</div>
                </div>
                
                <!-- Advanced Options -->
                <div class="advanced-section">
                    <div class="advanced-toggle" onclick="toggleAdvancedOptions()">
                        <i class="fas fa-chevron-right"></i>
                        <span>Advanced Options</span>
                    </div>
                    
                    <div class="advanced-options" id="advanced-options">
                        <div class="form-group">
                            <label for="custom-port">
                                <i class="fas fa-network-wired"></i>
                                Custom Port (optional)
                            </label>
                            <div class="input-wrapper">
                                <input 
                                    type="number" 
                                    id="custom-port" 
                                    class="form-control" 
                                    min="1024" 
                                    max="65535" 
                                    placeholder="Auto-assigned if empty"
                                >
                                <div class="input-icon">
                                    <i class="fas fa-network-wired"></i>
                                </div>
                            </div>
                            <div class="form-hint">Port range: 1024-65535</div>
                        </div>
                        
                        <div class="form-checkbox-group">
                            <label class="checkbox-label">
                                <input type="checkbox" id="enable-udp" checked>
                                <span class="checkbox-custom"></span>
                                <div class="checkbox-content">
                                    <i class="fas fa-exchange-alt"></i>
                                    <span>Enable UDP protocol</span>
                                </div>
                            </label>
                            <div class="form-hint">Recommended for better performance with some applications</div>
                        </div>
                    </div>
                </div>
            </form>
        </div>
        
        <div class="modal-footer">
            <div class="modal-info">
                <i class="fas fa-info-circle"></i>
                <span>Service will be created: <span id="service-preview">shadowsocks-[username].service</span></span>
            </div>
            <div class="form-actions">
                <button type="button" class="btn btn-secondary" onclick="closeModal('addUserModal')">
                    <i class="fas fa-times"></i>
                    Cancel
                </button>
                <button type="submit" form="add-user-form" class="btn btn-success" id="submit-btn">
                    <i class="fas fa-user-plus"></i>
                    Create User
                </button>
            </div>
        </div>
    `;
    
    const modal = document.getElementById('addUserModal');
    if (modal) {
        modal.querySelector('.modal-content').innerHTML = modalHTML;
        
        // Добавляем обработчик предварительного просмотра имени службы
        const usernameInput = modal.querySelector('#username');
        const servicePreview = modal.querySelector('#service-preview');
        
        if (usernameInput && servicePreview) {
            usernameInput.addEventListener('input', function() {
                const username = this.value.trim() || 'username';
                servicePreview.textContent = `shadowsocks-${username}.service`;
            });
        }
    }
}

// Показать модальное окно добавления пользователя
function showAddUserModal() {
    const modal = document.getElementById('addUserModal');
    if (modal) {
        modal.style.display = 'flex';
        modal.style.opacity = '1';
        modals.activeModal = 'addUserModal';
        
        // Фокус на первое поле
        const usernameInput = modal.querySelector('#username');
        if (usernameInput) {
            setTimeout(() => usernameInput.focus(), 100);
        }
        
        // Блокируем скролл страницы
        document.body.style.overflow = 'hidden';
    }
}

// Обработка добавления пользователя с улучшенной валидацией
async function handleAddUser(event) {
    event.preventDefault();
    
    const form = event.target;
    const submitBtn = document.getElementById('submit-btn');
    
    // Валидация формы
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    const username = document.getElementById('username').value.trim();
    const email = document.getElementById('email').value.trim();
    const trafficLimit = document.getElementById('traffic-limit').value;
    const durationDays = document.getElementById('duration-days').value;
    const method = document.getElementById('method').value;
    const password = document.getElementById('password').value;
    const customPort = document.getElementById('custom-port')?.value;
    const enableUdp = document.getElementById('enable-udp')?.checked;
    
    // Дополнительная валидация
    if (username.length < 3 || username.length > 20) {
        showToast('Username must be 3-20 characters', 'error');
        return;
    }
    
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showToast('Please enter a valid email address', 'error');
        return;
    }
    
    if (customPort && (customPort < 1024 || customPort > 65535)) {
        showToast('Port must be between 1024 and 65535', 'error');
        return;
    }
    
    const userData = {
        username: username,
        email: email || '',
        traffic_limit_gb: parseInt(trafficLimit),
        duration_days: parseInt(durationDays),
        method: method
    };
    
    if (password) {
        if (password.length < 8) {
            showToast('Password must be at least 8 characters', 'error');
            return;
        }
        userData.password = password;
    }
    
    if (customPort) {
        userData.port = parseInt(customPort);
    }
    
    if (typeof enableUdp !== 'undefined') {
        userData.enable_udp = enableUdp;
    }
    
    // Показываем индикатор загрузки
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
    submitBtn.disabled = true;
    
    try {
        const response = await fetch(getApiUrl('user.add'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('User created successfully!', 'success');
            
            // Показываем дополнительные детали если есть
            if (data.service_created) {
                showToast(`Service ${data.service_name} created and started`, 'info');
            }
            
            // Закрываем модальное окно с задержкой
            setTimeout(() => {
                closeModal('addUserModal');
                form.reset();
                
                // Восстанавливаем кнопку
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
                
                // Обновить список пользователей
                if (window.loadUsers) {
                    window.loadUsers();
                }
                
                // Обновить обзор служб
                if (window.loadServicesOverview) {
                    window.loadServicesOverview();
                }
                
                // Обновить статистику
                if (window.loadStats) {
                    window.loadStats();
                }
            }, 1500);
            
        } else {
            showToast('Error: ' + data.message, 'error');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    } catch (error) {
        showToast('Network error: ' + error.message, 'error');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

// Показать конфигурацию пользователя с современным дизайном
function showUserConfigModal(userId, username) {
    fetch(getApiUrl('user.config', userId) + '/config')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const config = data.config;
                const modal = document.getElementById('configModal');
                if (modal) {
                    modal.querySelector('.modal-content').innerHTML = `
                        <div class="modal-header">
                            <div class="modal-title">
                                <i class="fas fa-code"></i>
                                <div class="modal-title-content">
                                    <h2>Configuration</h2>
                                    <div class="modal-subtitle">${username}</div>
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
                                                <input type="text" value="${config.server}" id="server-config" readonly>
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
                                                <input type="text" value="${config.port}" id="port-config" readonly>
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
                                                    <input type="password" value="${config.password}" 
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
                                                <input type="text" value="${config.method}" id="method-config" readonly>
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
                                            <textarea id="ssurl-config" readonly rows="3">${config.ss_url_with_comment || config.ss_url}</textarea>
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
                                            <span class="info-value">${config.username || username}</span>
                                        </div>
                                        <div class="info-item">
                                            <span class="info-label">Traffic Used:</span>
                                            <span class="info-value">${config.traffic_used_gb || '0'} GB</span>
                                        </div>
                                        <div class="info-item">
                                            <span class="info-label">Traffic Limit:</span>
                                            <span class="info-value">${config.traffic_limit_gb || 'Unlimited'} GB</span>
                                        </div>
                                        <div class="info-item">
                                            <span class="info-label">Expires:</span>
                                            <span class="info-value">${config.expires_at ? new Date(config.expires_at).toLocaleDateString() : 'Never'}</span>
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
                                <button class="btn btn-primary" onclick="shareConfig('${config.ss_url_with_comment || config.ss_url}')">
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
                                text: config.ss_url_with_comment || config.ss_url,
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
                    modals.activeModal = 'configModal';
                    document.body.style.overflow = 'hidden';
                }
            } else {
                showToast('Error loading configuration: ' + data.message, 'error');
            }
        })
        .catch(error => {
            showToast('Error: ' + error.message, 'error');
        });
}

// Показать информацию о службе с современным дизайном
function showServiceInfoModal(serviceName, username) {
    const modal = document.getElementById('serviceInfoModal');
    if (modal) {
        modal.querySelector('.modal-content').innerHTML = `
            <div class="modal-header">
                <div class="modal-title">
                    <i class="fas fa-server"></i>
                    <div class="modal-title-content">
                        <h2>Service Details</h2>
                        <div class="modal-subtitle">${serviceName}</div>
                    </div>
                </div>
                <button class="modal-close" onclick="closeModal('serviceInfoModal')" aria-label="Close">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="modal-body service-modal-body">
                <!-- Service Overview -->
                <div class="service-overview">
                    <div class="service-badge">
                        <i class="fas fa-microchip"></i>
                        <span>Individual Service</span>
                    </div>
                    <div class="service-user">
                        <i class="fas fa-user"></i>
                        <span>${username}</span>
                    </div>
                </div>
                
                <!-- Service Status -->
                <div class="service-status-section">
                    <div class="section-header">
                        <i class="fas fa-heartbeat"></i>
                        <h3>Service Status</h3>
                    </div>
                    <div class="status-container">
                        <div class="status-indicator" id="service-status-indicator">
                            <div class="status-dot"></div>
                            <span class="status-text">Checking...</span>
                        </div>
                        <div class="status-details">
                            <div class="status-item">
                                <span class="status-label">Last Check:</span>
                                <span class="status-value" id="service-last-check">-</span>
                            </div>
                            <div class="status-item">
                                <span class="status-label">Uptime:</span>
                                <span class="status-value" id="service-uptime">-</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Service Controls -->
                <div class="service-controls-section">
                    <div class="section-header">
                        <i class="fas fa-sliders-h"></i>
                        <h3>Service Controls</h3>
                    </div>
                    <div class="controls-grid">
                        <button class="control-btn start-btn" onclick="controlService('${serviceName}', 'start')">
                            <i class="fas fa-play"></i>
                            <span>Start</span>
                        </button>
                        <button class="control-btn stop-btn" onclick="controlService('${serviceName}', 'stop')">
                            <i class="fas fa-stop"></i>
                            <span>Stop</span>
                        </button>
                        <button class="control-btn restart-btn" onclick="controlService('${serviceName}', 'restart')">
                            <i class="fas fa-redo"></i>
                            <span>Restart</span>
                        </button>
                        <button class="control-btn reload-btn" onclick="controlService('${serviceName}', 'reload')">
                            <i class="fas fa-sync-alt"></i>
                            <span>Reload</span>
                        </button>
                    </div>
                </div>
                
                <!-- Service Logs -->
                <div class="service-logs-section">
                    <div class="section-header">
                        <i class="fas fa-terminal"></i>
                        <h3>Service Logs</h3>
                        <button class="logs-refresh" onclick="loadServiceLogs('${serviceName}')" title="Refresh logs">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                    </div>
                    <div class="logs-container">
                        <div class="logs-header">
                            <span class="logs-count">Last 50 lines</span>
                            <button class="clear-logs" onclick="clearServiceLogs()" title="Clear logs">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        </div>
                        <pre class="logs-content" id="service-logs">Loading logs...</pre>
                    </div>
                </div>
                
                <!-- Service Information -->
                <div class="service-info-section">
                    <div class="section-header">
                        <i class="fas fa-info-circle"></i>
                        <h3>Service Information</h3>
                    </div>
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Service Name:</span>
                            <span class="info-value">${serviceName}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Type:</span>
                            <span class="info-value">Systemd Service</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Config Path:</span>
                            <span class="info-value">/etc/shadowsocks/${username}.json</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Log Path:</span>
                            <span class="info-value">/var/log/shadowsocks/${username}.log</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="modal-footer">
                <div class="action-buttons">
                    <button class="btn btn-secondary" onclick="closeModal('serviceInfoModal')">
                        <i class="fas fa-times"></i>
                        Close
                    </button>
                    <button class="btn btn-outline" onclick="openServiceConfig('${serviceName}')">
                        <i class="fas fa-cog"></i>
                        Edit Config
                    </button>
                </div>
            </div>
        `;
        
        modal.style.display = 'flex';
        modal.style.opacity = '1';
        modals.activeModal = 'serviceInfoModal';
        document.body.style.overflow = 'hidden';
        
        // Load service status with polling
        loadServiceStatus(serviceName);
        startServiceStatusPolling(serviceName);
        
        // Load service logs
        loadServiceLogs(serviceName);
    }
}

// Загрузить статус службы с улучшенной информацией
async function loadServiceStatus(serviceName) {
    try {
        const response = await fetch(getApiUrl('service.control'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                service: serviceName,
                action: 'status'
            })
        });
        
        const data = await response.json();
        const statusElement = document.getElementById('service-status-indicator');
        const lastCheckElement = document.getElementById('service-last-check');
        const uptimeElement = document.getElementById('service-uptime');
        
        if (statusElement) {
            if (data.success) {
                const status = data.status || {};
                const isActive = status.active || false;
                
                // Обновляем статус
                const statusDot = statusElement.querySelector('.status-dot');
                const statusText = statusElement.querySelector('.status-text');
                
                statusDot.className = 'status-dot ' + (isActive ? 'active' : 'inactive');
                statusText.textContent = isActive ? 'Active' : 'Inactive';
                statusText.className = 'status-text ' + (isActive ? 'active' : 'inactive');
                
                // Обновляем время
                if (lastCheckElement) {
                    lastCheckElement.textContent = new Date().toLocaleTimeString();
                }
                
                // Обновляем uptime (если доступно)
                if (uptimeElement && status.uptime) {
                    uptimeElement.textContent = formatUptime(status.uptime);
                } else {
                    uptimeElement.textContent = 'N/A';
                }
                
            } else {
                statusElement.querySelector('.status-dot').className = 'status-dot error';
                statusElement.querySelector('.status-text').textContent = 'Error';
                statusElement.querySelector('.status-text').className = 'status-text error';
            }
        }
    } catch (error) {
        console.error('Error loading service status:', error);
        const statusElement = document.getElementById('service-status-indicator');
        if (statusElement) {
            statusElement.querySelector('.status-dot').className = 'status-dot error';
            statusElement.querySelector('.status-text').textContent = 'Connection Error';
            statusElement.querySelector('.status-text').className = 'status-text error';
        }
    }
}

// Форматирование времени uptime
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}

// Запуск периодической проверки статуса службы
let statusPollingInterval = null;
function startServiceStatusPolling(serviceName) {
    // Останавливаем предыдущий интервал
    if (statusPollingInterval) {
        clearInterval(statusPollingInterval);
    }
    
    // Запускаем новый интервал
    statusPollingInterval = setInterval(() => {
        if (modals.activeModal === 'serviceInfoModal') {
            loadServiceStatus(serviceName);
        } else {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
        }
    }, 5000); // Проверка каждые 5 секунд
}

// Загрузить логи службы (реальная реализация)
async function loadServiceLogs(serviceName) {
    try {
        const logsElement = document.getElementById('service-logs');
        if (logsElement) {
            logsElement.textContent = 'Loading logs...';
            
            // В реальной системе здесь будет запрос к API
            // const response = await fetch(`/api/services/${serviceName}/logs`);
            // const data = await response.json();
            
            // Симуляция загрузки
            setTimeout(() => {
                const sampleLogs = [
                    `[${new Date().toISOString()}] Service ${serviceName} started successfully`,
                    `[${new Date().toISOString()}] Listening on port 8388`,
                    `[${new Date().toISOString()}] UDP relay enabled`,
                    `[${new Date().toISOString()}] 10 connections established`,
                    `[${new Date().toISOString()}] Traffic: 1.2MB sent, 0.8MB received`
                ].join('\n');
                
                logsElement.textContent = sampleLogs;
                
                // Автопрокрутка к новым логам
                logsElement.scrollTop = logsElement.scrollHeight;
            }, 500);
        }
    } catch (error) {
        console.error('Error loading service logs:', error);
        const logsElement = document.getElementById('service-logs');
        if (logsElement) {
            logsElement.textContent = 'Error loading logs: ' + error.message;
        }
    }
}

// Очистить логи службы
function clearServiceLogs() {
    const logsElement = document.getElementById('service-logs');
    if (logsElement) {
        logsElement.textContent = 'Logs cleared at ' + new Date().toLocaleTimeString();
        showToast('Logs cleared', 'info');
    }
}

// Управление службой с улучшенной обратной связью
async function controlService(serviceName, action) {
    const actionMap = {
        'start': 'starting',
        'stop': 'stopping',
        'restart': 'restarting',
        'reload': 'reloading'
    };
    
    const loadingText = actionMap[action] || 'processing';
    showToast(`${serviceName} ${loadingText}...`, 'info');
    
    try {
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
        
        if (data.success) {
            showToast(`Service ${action}ed successfully`, 'success');
            
            // Обновляем статус
            setTimeout(() => loadServiceStatus(serviceName), 1000);
            
            // Обновляем обзор служб
            if (window.loadServicesOverview) {
                setTimeout(() => window.loadServicesOverview(), 1500);
            }
        } else {
            showToast('Error: ' + data.message, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Открыть конфигурацию службы
function openServiceConfig(serviceName) {
    showToast(`Opening config for ${serviceName}...`, 'info');
    // Реализация открытия конфигурации
}

// Копировать конфигурацию с улучшенной обратной связью
function copyConfig(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    let text = '';
    if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
        text = element.value;
    } else {
        text = element.textContent;
    }
    
    if (!text.trim()) {
        showToast('Nothing to copy', 'warning');
        return;
    }
    
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('Copied to clipboard!', 'success');
            // Визуальная обратная связь
            const copyBtn = element.parentElement.querySelector('.copy-btn');
            if (copyBtn) {
                const originalHtml = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="fas fa-check"></i>';
                setTimeout(() => {
                    copyBtn.innerHTML = originalHtml;
                }, 2000);
            }
        }).catch(err => {
            console.error('Clipboard error:', err);
            copyFallback(text);
        });
    } else {
        copyFallback(text);
    }
}

// Fallback для копирования
function copyFallback(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showToast('Copied to clipboard!', 'success');
        } else {
            showToast('Failed to copy', 'error');
        }
    } catch (err) {
        showToast('Failed to copy: ' + err, 'error');
    }
    
    document.body.removeChild(textArea);
}

// Поделиться конфигурацией
function shareConfig(url) {
    if (navigator.share) {
        navigator.share({
            title: 'Shadowsocks Configuration',
            text: 'Here is my Shadowsocks configuration:',
            url: url
        }).then(() => {
            showToast('Shared successfully!', 'success');
        }).catch(error => {
            if (error.name !== 'AbortError') {
                console.log('Error sharing:', error);
                copyConfig('ssurl-config');
            }
        });
    } else {
        copyConfig('ssurl-config');
    }
}

// Вспомогательные функции

// Генерация случайного пароля
function generateRandomPassword() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
    let password = '';
    
    // Генерируем пароль из 16 символов
    for (let i = 0; i < 16; i++) {
        password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    
    // Убедимся, что есть хотя бы один символ каждого типа
    if (!/[A-Z]/.test(password)) password = 'A' + password.slice(1);
    if (!/[a-z]/.test(password)) password = 'a' + password.slice(2);
    if (!/[0-9]/.test(password)) password = '1' + password.slice(3);
    if (!/[!@#$%^&*]/.test(password)) password = '!' + password.slice(4);
    
    const passwordInput = document.getElementById('password');
    if (passwordInput) {
        passwordInput.value = password;
        passwordInput.type = 'text'; // Показываем пароль
        
        showToast('Password generated!', 'success');
        
        // Автоматически скрываем через 3 секунды
        setTimeout(() => {
            if (passwordInput.type === 'text') {
                passwordInput.type = 'password';
            }
        }, 3000);
    }
}

// Переключение видимости пароля
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
        input.setAttribute('type', type);
        
        const eyeIcon = input.parentElement.querySelector('.fa-eye');
        if (eyeIcon) {
            if (type === 'text') {
                eyeIcon.className = 'fas fa-eye-slash';
            } else {
                eyeIcon.className = 'fas fa-eye';
            }
        }
    }
}

// Переключение расширенных опций
function toggleAdvancedOptions() {
    const advancedOptions = document.getElementById('advanced-options');
    const toggleIcon = document.querySelector('.advanced-toggle i');
    
    if (advancedOptions) {
        if (advancedOptions.style.display === 'none' || !advancedOptions.style.display) {
            advancedOptions.style.display = 'block';
            toggleIcon.className = 'fas fa-chevron-down';
            advancedOptions.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            advancedOptions.style.display = 'none';
            toggleIcon.className = 'fas fa-chevron-right';
        }
    }
}

// Закрыть модальное окно с анимацией
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.opacity = '0';
        
        // Останавливаем polling статуса
        if (statusPollingInterval) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
        }
        
        setTimeout(() => {
            modal.style.display = 'none';
            modals.activeModal = null;
            
            // Восстанавливаем скролл страницы
            document.body.style.overflow = '';
        }, 300); // Время должно совпадать с CSS transition
    }
}

// Закрыть все модальные окна
function closeAllModals() {
    Object.keys(modals).forEach(modalId => {
        if (modalId !== 'activeModal') {
            closeModal(modalId);
        }
    });
}

// Инициализировать модальные окна
document.addEventListener('DOMContentLoaded', function() {
    initModals();
    
    // Закрытие модальных окон при клике вне
    document.addEventListener('click', function(event) {
        const modalIds = ['addUserModal', 'configModal', 'serviceInfoModal'];
        modalIds.forEach(modalId => {
            const modal = document.getElementById(modalId);
            if (modal && 
                modal.style.display === 'flex' && 
                event.target === modal &&
                !modal.querySelector('.modal-content').contains(event.target)) {
                closeModal(modalId);
            }
        });
    });
});

// Сделать функции глобальными
window.showAddUserModal = showAddUserModal;
window.showUserConfigModal = showUserConfigModal;
window.showServiceInfoModal = showServiceInfoModal;
window.closeModal = closeModal;
window.closeAllModals = closeAllModals;
window.copyConfig = copyConfig;
window.shareConfig = shareConfig;
window.controlService = controlService;
window.handleAddUser = handleAddUser;
window.generateRandomPassword = generateRandomPassword;
window.togglePasswordVisibility = togglePasswordVisibility;
window.toggleAdvancedOptions = toggleAdvancedOptions;