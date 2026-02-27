// notifications.js - Управление уведомлениями

let notifications = [];

// Загрузить уведомления
async function loadNotifications() {
    try {
        const response = await fetch(getApiUrl('notifications.check'), {
            method: 'POST'
        });
        
        if (!response.ok) {
            return;
        }
        
        const data = await response.json();
        
        if (data.success) {
            notifications = data.notifications || [];
            updateNotificationsDisplay();
        }
    } catch (error) {
        console.error('Error loading notifications:', error);
    }
}

// Обновить отображение уведомлений
function updateNotificationsDisplay() {
    const list = document.getElementById('notifications-list');
    const countBadge = document.getElementById('notification-count');
    const panel = document.getElementById('notifications-panel');
    
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
        // Сортируем по типу и времени
        notifications.sort((a, b) => {
            const typeOrder = { 'expired': 0, 'expire_soon': 1, 'traffic_high': 2, 'info': 3 };
            const aOrder = typeOrder[a.type] || 4;
            const bOrder = typeOrder[b.type] || 4;
            
            if (aOrder !== bOrder) return aOrder - bOrder;
            
            // По времени (новые первыми)
            const aTime = a.timestamp ? new Date(a.timestamp).getTime() : 0;
            const bTime = b.timestamp ? new Date(b.timestamp).getTime() : 0;
            return bTime - aTime;
        });
        
        list.innerHTML = notifications.map(notif => createNotificationItem(notif)).join('');
        
        if (countBadge) {
            countBadge.textContent = notifications.length;
            countBadge.style.display = 'inline-block';
        }
    }
    
    // Если панель открыта, показать ее
    if (panel && panel.style.display === 'block') {
        panel.style.display = 'block';
    }
}

// Создать элемент уведомления
function createNotificationItem(notification) {
    const types = {
        'expired': {
            icon: 'fas fa-exclamation-triangle',
            color: '#dc3545',
            title: 'Account Expired'
        },
        'expire_soon': {
            icon: 'fas fa-clock',
            color: '#ffc107',
            title: 'Expiring Soon'
        },
        'traffic_high': {
            icon: 'fas fa-chart-line',
            color: '#fd7e14',
            title: 'High Traffic Usage'
        },
        'info': {
            icon: 'fas fa-info-circle',
            color: '#17a2b8',
            title: 'Information'
        }
    };
    
    const typeInfo = types[notification.type] || types.info;
    const time = notification.timestamp ? new Date(notification.timestamp).toLocaleTimeString() : 'Just now';
    const userInfo = notification.username ? `<div class="notification-user">User: ${notification.username}</div>` : '';
    const daysLeft = notification.days_left ? `<div class="notification-days">${notification.days_left} days left</div>` : '';
    const usagePercent = notification.usage_percent ? `<div class="notification-usage">${notification.usage_percent}% used</div>` : '';
    
    return `
        <div class="notification-item" style="border-left-color: ${typeInfo.color}">
            <div class="notification-header">
                <div class="notification-title">
                    <i class="${typeInfo.icon}" style="color: ${typeInfo.color}"></i>
                    <strong>${typeInfo.title}</strong>
                </div>
                <span class="notification-time">${time}</span>
            </div>
            <div class="notification-content">
                ${notification.message || 'No message'}
            </div>
            ${userInfo}
            ${daysLeft}
            ${usagePercent}
            <div class="notification-actions">
                <button class="btn btn-xs" onclick="handleNotificationAction('${notification.type}', '${notification.user_id}')">
                    <i class="fas fa-cog"></i> Manage
                </button>
                <button class="btn btn-xs btn-secondary" onclick="dismissNotification('${notification.type}', '${notification.user_id}')">
                    <i class="fas fa-check"></i> Dismiss
                </button>
            </div>
        </div>
    `;
}

// Обработать действие уведомления
function handleNotificationAction(type, userId) {
    switch(type) {
        case 'expired':
        case 'expire_soon':
            // Показать модальное окно продления
            if (window.extendUser) {
                window.extendUser(userId);
            }
            break;
        case 'traffic_high':
            // Показать модальное окно сброса трафика
            if (window.resetUserTraffic) {
                window.resetUserTraffic(userId);
            }
            break;
        default:
            // Для других типов показать информацию о пользователе
            if (window.showUserConfig) {
                window.showUserConfig(userId);
            }
    }
    
    // Закрыть панель уведомлений
    closeNotifications();
}

// Отклонить уведомление
async function dismissNotification(type, userId) {
    try {
        // Здесь можно добавить логику отметки уведомления как прочитанного
        // Временное решение: фильтруем из текущего списка
        notifications = notifications.filter(notif => 
            !(notif.type === type && notif.user_id === userId)
        );
        
        updateNotificationsDisplay();
        showToast('Notification dismissed', 'success');
    } catch (error) {
        console.error('Error dismissing notification:', error);
    }
}

// Открыть панель уведомлений
function openNotifications() {
    const panel = document.getElementById('notifications-panel');
    const button = document.getElementById('notifications-btn');
    
    if (panel && button) {
        const isVisible = panel.style.display === 'block';
        panel.style.display = isVisible ? 'none' : 'block';
        
        if (!isVisible) {
            // Загрузить уведомления при открытии
            loadNotifications();
        }
    }
}

// Закрыть панель уведомлений
function closeNotifications() {
    const panel = document.getElementById('notifications-panel');
    if (panel) {
        panel.style.display = 'none';
    }
}

// Очистить все уведомления
function clearNotifications() {
    if (!confirm('Clear all notifications?')) {
        return;
    }
    
    notifications = [];
    updateNotificationsDisplay();
    showToast('All notifications cleared', 'success');
}

// Проверить уведомления
function checkNotifications() {
    showToast('Checking for new notifications...', 'info');
    loadNotifications();
}

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    // Проверить уведомления при загрузке
    loadNotifications();
    
    // Автоматическая проверка каждые 5 минут
    setInterval(loadNotifications, 300000);
    
    // Обработчик клика вне панели уведомлений
    document.addEventListener('click', function(event) {
        const panel = document.getElementById('notifications-panel');
        const button = document.getElementById('notifications-btn');
        
        if (panel && panel.style.display === 'block' && 
            !panel.contains(event.target) && 
            !button.contains(event.target)) {
            closeNotifications();
        }
    });
});

// Сделать функции глобальными
window.openNotifications = openNotifications;
window.closeNotifications = closeNotifications;
window.clearNotifications = clearNotifications;
window.checkNotifications = checkNotifications;
window.loadNotifications = loadNotifications;