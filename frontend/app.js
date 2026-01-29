// API Configuration
const API_BASE = 'http://127.0.0.1:8000';

// State
let authToken = localStorage.getItem('token');
let userRole = localStorage.getItem('role');
let isRegistered = localStorage.getItem('isRegistered') === 'true';
let dashboardInterval = null;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

async function apiCall(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Request failed');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
}

function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById(`section-${sectionId}`).classList.add('active');
    
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelector(`[data-section="${sectionId}"]`).classList.add('active');
}

function showResult(elementId, message, type = 'success') {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.className = `result-msg ${type}`;
    el.style.display = 'block';
    
    setTimeout(() => {
        el.style.display = 'none';
    }, 5000);
}

function formatDate(dateStr) {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleString();
}

// ============================================================================
// AUTHENTICATION
// ============================================================================

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const userid = document.getElementById('login-userid').value;
    const password = document.getElementById('login-password').value;
    
    try {
        const formData = new URLSearchParams();
        formData.append('username', userid);
        formData.append('password', password);
        
        const response = await fetch(`${API_BASE}/token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Login failed');
        }
        
        authToken = data.access_token;
        userRole = data.role;
        isRegistered = data.is_registered;
        
        localStorage.setItem('token', authToken);
        localStorage.setItem('role', userRole);
        localStorage.setItem('isRegistered', isRegistered);
        
        if (!isRegistered) {
            showPage('register-page');
        } else {
            initDashboard();
        }
        
    } catch (error) {
        document.getElementById('login-error').textContent = error.message;
    }
});

document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = {
        first_name: document.getElementById('reg-firstname').value,
        last_name: document.getElementById('reg-lastname').value,
        email: document.getElementById('reg-email').value,
        phone_number: document.getElementById('reg-phone').value,
        substation_id: document.getElementById('reg-substation').value,
        substation_location: document.getElementById('reg-location').value,
        new_userid: document.getElementById('reg-new-userid').value,
        new_password: document.getElementById('reg-new-password').value
    };
    
    try {
        await apiCall('/register', {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        // Clear stored credentials and go back to login
        localStorage.clear();
        authToken = null;
        alert('Registration complete! Please login with your new credentials.');
        showPage('login-page');
        
    } catch (error) {
        document.getElementById('register-error').textContent = error.message;
    }
});

function logout() {
    localStorage.clear();
    authToken = null;
    userRole = null;
    isRegistered = false;
    
    if (dashboardInterval) {
        clearInterval(dashboardInterval);
    }
    
    showPage('login-page');
    document.getElementById('login-userid').value = '';
    document.getElementById('login-password').value = '';
}

// ============================================================================
// DASHBOARD
// ============================================================================

function initDashboard() {
    showPage('dashboard-page');
    showSection('dashboard');
    
    // Show admin panel for admins
    if (userRole === 'admin') {
        document.querySelectorAll('.admin-only').forEach(el => el.classList.add('visible'));
    }
    
    // Load initial data
    loadDashboard();
    
    // Auto-refresh dashboard every 5 seconds
    dashboardInterval = setInterval(loadDashboard, 5000);
}

async function loadDashboard() {
    try {
        const data = await apiCall('/api/dashboard');
        
        document.getElementById('stat-voltage').textContent = data.voltage_reading?.toFixed(1) || '0';
        document.getElementById('stat-current').textContent = data.current_reading?.toFixed(2) || '0';
        document.getElementById('stat-status').textContent = data.grid_status || 'WAITING';
        document.getElementById('stat-updated').textContent = formatDate(data.last_updated);
        
        // Update status icon
        const statusIcon = document.getElementById('status-icon');
        if (data.grid_status === 'CRITICAL') {
            statusIcon.textContent = '🔴';
        } else if (data.grid_status === 'STABLE') {
            statusIcon.textContent = '🟢';
        } else {
            statusIcon.textContent = '🟡';
        }
        
        // Update fault logs
        const logsBody = document.getElementById('fault-logs-body');
        if (data.logs && data.logs.length > 0) {
            logsBody.innerHTML = data.logs.map(log => `
                <tr>
                    <td>${formatDate(log.timestamp)}</td>
                    <td>${log.substation_id || '-'}</td>
                    <td>${log.line_id || '-'}</td>
                    <td><span class="badge badge-danger">${log.fault_type}</span></td>
                    <td>${log.voltage?.toFixed(1) || '-'} V</td>
                    <td>${log.current?.toFixed(2) || '-'} A</td>
                    <td><span class="badge ${log.status === 'Active' ? 'badge-danger' : 'badge-success'}">${log.status}</span></td>
                </tr>
            `).join('');
        } else {
            logsBody.innerHTML = '<tr><td colspan="7" class="no-data">No fault logs yet</td></tr>';
        }
        
    } catch (error) {
        console.error('Dashboard load error:', error);
    }
}

// ============================================================================
// GRID CONTROL
// ============================================================================

async function sendControlCommand(action) {
    try {
        const data = await apiCall(`/api/control/${action}`, {
            method: 'POST'
        });
        
        showResult('control-result', `✅ ${action} command queued: ${data.message}`, 'success');
        
    } catch (error) {
        showResult('control-result', `❌ Error: ${error.message}`, 'error');
    }
}

document.getElementById('manual-input-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const data = {
        voltage_a: parseFloat(document.getElementById('input-voltage').value),
        current_a: parseFloat(document.getElementById('input-current').value),
        load_kw: parseFloat(document.getElementById('input-load').value),
        power_factor: parseFloat(document.getElementById('input-pf').value)
    };
    
    try {
        const result = await apiCall('/api/input-grid-data', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        
        const msg = result.command === 'TRIP' 
            ? `🚨 FAULT DETECTED: ${result.reason} - Circuit TRIPPED!`
            : `✅ Normal operation - ${result.reason}`;
            
        showResult('manual-input-result', msg, result.command === 'TRIP' ? 'error' : 'success');
        
    } catch (error) {
        showResult('manual-input-result', `❌ Error: ${error.message}`, 'error');
    }
});

// ============================================================================
// CONSUMER MANAGEMENT
// ============================================================================

document.getElementById('consumer-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const data = {
        meter_id: document.getElementById('consumer-meter').value,
        substation_id: document.getElementById('consumer-substation').value,
        email: document.getElementById('consumer-email').value || null
    };
    
    try {
        const result = await apiCall('/api/consumer/register', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        
        showResult('consumer-result', `✅ Consumer registered! ID: ${result.consumer_id}`, 'success');
        e.target.reset();
        
    } catch (error) {
        showResult('consumer-result', `❌ Error: ${error.message}`, 'error');
    }
});

document.getElementById('power-reading-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const data = {
        meter_id: document.getElementById('reading-meter').value,
        power_kw: parseFloat(document.getElementById('reading-power').value),
        voltage: parseFloat(document.getElementById('reading-voltage').value),
        power_factor: parseFloat(document.getElementById('reading-pf').value)
    };
    
    try {
        const result = await apiCall('/api/consumer/reading', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        
        let msg = `📊 Reading recorded for ${result.meter_id}\n`;
        msg += `Trip Count: ${result.trip_count}`;
        
        if (result.trip_occurred) {
            msg += ` ⚠️ TRIP OCCURRED!`;
        }
        
        if (result.fault_type) {
            msg += `\n🚨 ${result.fault_message}`;
        }
        
        if (result.email_sent) {
            msg += `\n📧 Email notification sent!`;
        }
        
        const type = result.fault_type || result.trip_occurred ? 'warning' : 'success';
        showResult('power-reading-result', msg, type);
        
    } catch (error) {
        showResult('power-reading-result', `❌ Error: ${error.message}`, 'error');
    }
});

// ============================================================================
// THEFT DETECTION
// ============================================================================

document.getElementById('theft-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const power = document.getElementById('theft-power').value;
    const substation = document.getElementById('theft-substation').value;
    const phase = document.getElementById('theft-phase').value;
    
    try {
        const result = await apiCall(`/api/theft/detect?power_transmission=${power}&substation_id=${substation}&phase=${phase}`);
        
        const resultBox = document.getElementById('theft-result');
        resultBox.classList.add('visible');
        resultBox.classList.remove('theft', 'normal');
        resultBox.classList.add(result.theft_detected ? 'theft' : 'normal');
        
        resultBox.innerHTML = `
            <h4>${result.theft_detected ? '🚨 POWER THEFT DETECTED!' : '✅ No Theft Detected'}</h4>
            <p><strong>Phase:</strong> ${result.phase}</p>
            <p><strong>Power Transmitted:</strong> ${result.power_transmission} kW</p>
            <p><strong>Total Consumer Power:</strong> ${result.total_consumer_power} kW</p>
            ${result.theft_detected ? `<p><strong>Unauthorized Power:</strong> ${result.unauthorized_power} kW</p>` : ''}
            <p><strong>Consumers in Substation:</strong> ${result.consumers_count}</p>
            <p><strong>Status:</strong> ${result.status}</p>
            <p style="margin-top: 10px; color: var(--text-secondary); font-size: 12px;">${result.message}</p>
        `;
        
    } catch (error) {
        const resultBox = document.getElementById('theft-result');
        resultBox.classList.add('visible');
        resultBox.classList.remove('theft', 'normal');
        resultBox.innerHTML = `<p style="color: var(--danger);">❌ Error: ${error.message}</p>`;
    }
});

// ============================================================================
// ADMIN PANEL
// ============================================================================

document.getElementById('admin-create-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const role = document.getElementById('admin-role').value;
    
    try {
        const result = await apiCall('/admin/create-temp-credentials', {
            method: 'POST',
            body: JSON.stringify({ role })
        });
        
        const resultBox = document.getElementById('admin-result');
        resultBox.classList.add('visible');
        resultBox.innerHTML = `
            <h4>✅ Credentials Generated!</h4>
            <div class="credentials-box">
                <p><strong>User ID:</strong> ${result.userid}</p>
                <p><strong>Password:</strong> ${result.password}</p>
            </div>
            <p style="margin-top: 16px; color: var(--warning); font-size: 12px;">
                ⚠️ Share these credentials securely with the officer. They will need to complete registration on first login.
            </p>
        `;
        
    } catch (error) {
        const resultBox = document.getElementById('admin-result');
        resultBox.classList.add('visible');
        resultBox.innerHTML = `<p style="color: var(--danger);">❌ Error: ${error.message}</p>`;
    }
});

// ============================================================================
// NAVIGATION
// ============================================================================

document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        const section = item.dataset.section;
        showSection(section);
        
        // Load data for specific sections
        if (section === 'dashboard') {
            loadDashboard();
        }
    });
});

// ============================================================================
// INITIALIZATION
// ============================================================================

// Check if already logged in
if (authToken && isRegistered) {
    initDashboard();
} else if (authToken && !isRegistered) {
    showPage('register-page');
} else {
    showPage('login-page');
}
