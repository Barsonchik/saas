// config.js - Конфигурация приложения
const CONFIG = {
    API_URL: window.location.origin, // Используем текущий origin
    UPDATE_INTERVALS: {
        stats: 30000,      // 30 секунд
        services: 60000,   // 1 минута
        notifications: 300000 // 5 минут
    },
    API_ENDPOINTS: {
        health: '/api/health',
        stats: '/api/stats',
        users: '/api/users',
        'services.status': '/api/services/status',
        'services.restart-all': '/api/services/restart-all',
        'services.reload-all': '/api/services/reload-all',
        'services.sync': '/api/services/sync',
        'traffic.stream': '/api/traffic-stream',
        'traffic.history': '/api/traffic/history',
        'notifications.check': '/api/notifications/check',
        'notifications.history': '/api/notifications/history',
        'admin.initialize': '/api/admin/initialize',
        'user.add': '/api/users',
        'user.delete': '/api/users/',
        'user.config': '/api/users/',
        'user.reset-traffic': '/api/users/',
        'user.extend': '/api/users/',
        'user.service.toggle': '/api/users/',
        'user.service.restart': '/api/users/',
        'service.control': '/api/service/control'
    }
};

// Функции для работы с API
function getApiUrl(endpoint, id = '') {
    // Получаем базовый URL из маппинга
    let baseUrl = CONFIG.API_ENDPOINTS[endpoint];
    
    // Если не нашли в маппинге, используем сам endpoint как URL
    if (!baseUrl) {
        console.warn(`Endpoint '${endpoint}' not found in CONFIG.API_ENDPOINTS, using as is`);
        baseUrl = endpoint;
    }
    
    // Если есть ID, добавляем его к URL
    if (id) {
        // Убираем возможный trailing slash из baseUrl и добавляем ID
        baseUrl = baseUrl.replace(/\/$/, '') + '/' + id;
    }
    
    const fullUrl = `${CONFIG.API_URL}${baseUrl}`;
    console.log(`getApiUrl(${endpoint}, ${id}) -> ${fullUrl}`); // Для отладки
    return fullUrl;
}

function getFullApiUrl(endpoint) {
    return `${CONFIG.API_URL}${endpoint}`;
}

// Для обратной совместимости с существующим кодом
window.getApiUrl = getApiUrl;
window.getFullApiUrl = getFullApiUrl;