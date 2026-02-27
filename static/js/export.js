// export.js - Функции экспорта данных

// Экспортировать все конфигурации
async function exportAllConfigs() {
    try {
        showToast('Preparing all configurations for export...', 'info');
        
        // Получить всех пользователей
        const response = await fetch(getApiUrl('users'));
        if (!response.ok) {
            throw new Error('Failed to fetch users');
        }
        
        const data = await response.json();
        
        if (!data.success || !data.users) {
            throw new Error('No users found');
        }
        
        // Создать ZIP архив со всеми конфигурациями
        const zip = new JSZip();
        
        // Добавить README файл
        zip.file("README.txt", 
            `Shadowsocks Configurations Export
Generated: ${new Date().toISOString()}
Total Users: ${data.users.length}

Instructions:
1. Each .conf file can be imported into Shadowsocks clients
2. QR codes are available in the web interface
3. For bulk import, use the shadowsocks-urls.txt file

--- Server Information ---
Server: ${window.serverIP || 'Not specified'}
Export Date: ${new Date().toLocaleDateString()}
=============================================`
        );
        
        // Добавить файл со всеми URL
        let urlsContent = "# Shadowsocks URLs for all users\n\n";
        
        // Для каждого пользователя получить конфигурацию и добавить в архив
        for (const user of data.users) {
            try {
                const configResponse = await fetch(getApiUrl('user.config', user._id) + '/config');
                if (configResponse.ok) {
                    const configData = await configResponse.json();
                    
                    if (configData.success) {
                        const config = configData.config;
                        
                        // Создать файл конфигурации
                        const configContent = `# Shadowsocks Configuration for ${user.username}
# Generated: ${new Date().toISOString()}
# Expires: ${user.expires_at || 'Never'}
# Traffic: ${user.traffic_used_gb} / ${user.traffic_limit_gb} GB (${user.traffic_percent}%)

server=${config.server}
server_port=${config.port}
password=${config.password}
method=${config.method}
timeout=300
mode=tcp_and_udp

# Quick import URL: ${config.ss_url_with_comment || config.ss_url}

# For Shadowsocks clients supporting SIP008:
# {
#   "version": 1,
#   "servers": [
#     {
#       "id": "${user._id}",
#       "remarks": "${user.username}",
#       "server": "${config.server}",
#       "server_port": ${config.port},
#       "password": "${config.password}",
#       "method": "${config.method}"
#     }
#   ]
# }`;
                        
                        // Добавить файл конфигурации
                        zip.file(`${user.username}.conf`, configContent);
                        
                        // Добавить URL в общий файл
                        urlsContent += `${user.username}: ${config.ss_url_with_comment || config.ss_url}\n`;
                    }
                }
            } catch (error) {
                console.error(`Error processing user ${user.username}:`, error);
            }
        }
        
        // Добавить файл с URL
        zip.file("shadowsocks-urls.txt", urlsContent);
        
        // Создать и скачать ZIP
        const zipBlob = await zip.generateAsync({type: "blob"});
        const downloadUrl = URL.createObjectURL(zipBlob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `shadowsocks-configs-${new Date().toISOString().slice(0, 10)}.zip`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(downloadUrl);
        
        showToast('All configurations exported successfully!', 'success');
        
    } catch (error) {
        console.error('Error exporting configurations:', error);
        showToast('Error exporting: ' + error.message, 'error');
    }
}

// Экспортировать пользователей в CSV
async function exportUsersCSV() {
    try {
        showToast('Exporting users to CSV...', 'info');
        
        const response = await fetch(getApiUrl('users'));
        if (!response.ok) {
            throw new Error('Failed to fetch users');
        }
        
        const data = await response.json();
        
        if (!data.success || !data.users) {
            throw new Error('No users found');
        }
        
        // Создать CSV заголовок
        let csvContent = "Username,Email,Port,Service Name,Traffic Used (GB),Traffic Limit (GB),Traffic %,Days Remaining,Expires At,Status\n";
        
        // Добавить данные пользователей
        data.users.forEach(user => {
            const row = [
                `"${user.username}"`,
                `"${user.email || ''}"`,
                user.port || '',
                `"${user.service_name || ''}"`,
                user.traffic_used_gb || 0,
                user.traffic_limit_gb || 0,
                user.traffic_percent || 0,
                user.days_remaining || '',
                `"${user.expires_at || ''}"`,
                user.enable ? 'Active' : 'Inactive'
            ].join(',');
            
            csvContent += row + '\n';
        });
        
        // Создать и скачать CSV файл
        const blob = new Blob([csvContent], {type: 'text/csv;charset=utf-8;'});
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `shadowsocks-users-${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(downloadUrl);
        
        showToast('Users exported to CSV successfully!', 'success');
        
    } catch (error) {
        console.error('Error exporting users CSV:', error);
        showToast('Error exporting: ' + error.message, 'error');
    }
}

// Экспортировать отчет по трафику
async function exportTrafficReport() {
    try {
        showToast('Generating traffic report...', 'info');
        
        // Получить статистику
        const statsResponse = await fetch(getApiUrl('stats'));
        if (!statsResponse.ok) {
            throw new Error('Failed to fetch stats');
        }
        
        const statsData = await statsResponse.json();
        
        if (!statsData.success) {
            throw new Error('Failed to get statistics');
        }
        
        // Получить историю трафика
        const historyResponse = await fetch(getApiUrl('traffic.history') + '?days=30');
        const historyData = await historyResponse.ok ? await historyResponse.json() : {history: []};
        
        // Создать HTML отчет
        const reportHTML = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Shadowsocks Traffic Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { text-align: center; margin-bottom: 30px; }
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { border: 1px solid #ddd; padding: 20px; border-radius: 8px; }
        .stat-value { font-size: 24px; font-weight: bold; margin: 10px 0; }
        .table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .table th, .table td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        .table th { background-color: #f5f5f5; }
        .footer { margin-top: 40px; text-align: center; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Shadowsocks Traffic Report</h1>
        <p>Generated: ${new Date().toLocaleString()}</p>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <h3>Total Users</h3>
            <div class="stat-value">${statsData.stats?.users?.total || 0}</div>
            <div class="stat-label">${statsData.stats?.users?.active || 0} active</div>
        </div>
        
        <div class="stat-card">
            <h3>Total Traffic</h3>
            <div class="stat-value">${statsData.stats?.traffic?.total_used_gb || 0} GB</div>
            <div class="stat-label">of ${statsData.stats?.traffic?.total_limit_gb || 0} GB limit</div>
        </div>
        
        <div class="stat-card">
            <h3>Services</h3>
            <div class="stat-value">${statsData.stats?.services?.total_services || 0}</div>
            <div class="stat-label">${statsData.stats?.services?.active_services || 0} running</div>
        </div>
        
        <div class="stat-card">
            <h3>System</h3>
            <div class="stat-value">CPU: ${statsData.stats?.system?.cpu_usage || 0}%</div>
            <div class="stat-label">Memory: ${statsData.stats?.system?.memory_usage || 0}%</div>
        </div>
    </div>
    
    ${historyData.history && historyData.history.length > 0 ? `
    <h2>Traffic History (Last 30 Days)</h2>
    <table class="table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Traffic Used (GB)</th>
                <th>Average Usage</th>
                <th>User Count</th>
            </tr>
        </thead>
        <tbody>
            ${historyData.history.map(day => `
                <tr>
                    <td>${day.date}</td>
                    <td>${day.total_used_gb}</td>
                    <td>${day.average_usage}%</td>
                    <td>${day.user_count}</td>
                </tr>
            `).join('')}
        </tbody>
    </table>
    ` : ''}
    
    <div class="footer">
        <p>Report generated by Shadowsocks Manager</p>
        <p>Server: ${statsData.stats?.server?.ip || 'Unknown'}</p>
    </div>
</body>
</html>`;
        
        // Создать и скачать PDF/HTML
        const blob = new Blob([reportHTML], {type: 'text/html'});
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `traffic-report-${new Date().toISOString().slice(0, 10)}.html`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(downloadUrl);
        
        showToast('Traffic report generated successfully!', 'success');
        
    } catch (error) {
        console.error('Error generating traffic report:', error);
        showToast('Error generating report: ' + error.message, 'error');
    }
}

// Создать резервную копию базы данных
async function backupDatabase() {
    try {
        showToast('Creating database backup...', 'info');
        
        // Получить всех пользователей
        const usersResponse = await fetch(getApiUrl('users'));
        if (!usersResponse.ok) {
            throw new Error('Failed to fetch users');
        }
        
        const usersData = await usersResponse.json();
        
        // Получить логи
        const logsResponse = await fetch(getApiUrl('notifications.history') + '?limit=1000');
        const logsData = logsResponse.ok ? await logsResponse.json() : {notifications: []};
        
        // Создать объект бэкапа
        const backup = {
            version: '1.0',
            exportDate: new Date().toISOString(),
            serverInfo: {
                ip: window.serverIP || 'Unknown',
                timestamp: new Date().toISOString()
            },
            users: usersData.success ? usersData.users : [],
            logs: logsData.success ? logsData.notifications : [],
            statistics: {
                totalUsers: usersData.success ? usersData.users.length : 0,
                activeUsers: usersData.success ? usersData.users.filter(u => u.enable).length : 0
            }
        };
        
        // Конвертировать в JSON
        const jsonContent = JSON.stringify(backup, null, 2);
        
        // Создать и скачать файл
        const blob = new Blob([jsonContent], {type: 'application/json'});
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `shadowsocks-backup-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(downloadUrl);
        
        showToast('Database backup created successfully!', 'success');
        
    } catch (error) {
        console.error('Error creating database backup:', error);
        showToast('Error creating backup: ' + error.message, 'error');
    }
}

// Настройки автоматического экспорта
function toggleAutoBackup() {
    const checkbox = document.getElementById('auto-backup');
    if (checkbox) {
        const enabled = checkbox.checked;
        localStorage.setItem('autoBackup', enabled.toString());
        
        if (enabled) {
            showToast('Auto backup enabled', 'success');
            // Запланировать автоматическое резервное копирование каждый день в 2:00
            scheduleAutoBackup();
        } else {
            showToast('Auto backup disabled', 'info');
        }
    }
}

function toggleAutoReport() {
    const checkbox = document.getElementById('auto-report');
    if (checkbox) {
        const enabled = checkbox.checked;
        localStorage.setItem('autoReport', enabled.toString());
        
        if (enabled) {
            showToast('Auto reports enabled', 'success');
            // Запланировать автоматические отчеты каждую неделю
            scheduleAutoReports();
        } else {
            showToast('Auto reports disabled', 'info');
        }
    }
}

function scheduleAutoBackup() {
    // Эта функция должна быть реализована с использованием серверного планировщика задач
    // В клиентской части мы только сохраняем настройку
    console.log('Auto backup scheduling would be implemented on server side');
}

function scheduleAutoReports() {
    // Эта функция должна быть реализована с использованием серверного планировщика задач
    console.log('Auto reports scheduling would be implemented on server side');
}

// Загрузить настройки экспорта
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

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    loadExportSettings();
});

// Сделать функции глобальными
window.exportAllConfigs = exportAllConfigs;
window.exportUsersCSV = exportUsersCSV;
window.exportTrafficReport = exportTrafficReport;
window.backupDatabase = backupDatabase;
window.toggleAutoBackup = toggleAutoBackup;
window.toggleAutoReport = toggleAutoReport;
window.loadExportSettings = loadExportSettings;