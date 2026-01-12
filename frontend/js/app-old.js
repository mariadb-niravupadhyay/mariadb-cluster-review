/**
 * MariaDB Cluster Analyzer - Frontend Application
 * AI-Powered Analysis with Vector Search and RAG
 */

const API_BASE = 'http://localhost:8000';

// Sample data for demo
const SAMPLE_CLUSTER_DATA = {
    "cluster_name": "demo-galera-cluster",
    "topology_type": "galera",
    "nodes": [
        {
            "hostname": "db-node-01.demo.local",
            "datacenter": "dc1",
            "role": "galera_node",
            "system_resources": {
                "cpu_cores": 8,
                "ram_gb": 32,
                "disk_total_gb": 300
            },
            "global_status": {
                "Uptime": "90000",
                "Questions": "19800000",
                "Threads_connected": "8",
                "Threads_running": "2",
                "Max_used_connections": "159",
                "Innodb_buffer_pool_read_requests": "890000000",
                "Innodb_buffer_pool_reads": "2670000",
                "wsrep_cluster_size": "7",
                "wsrep_cluster_status": "Primary",
                "wsrep_local_state": "4",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.00001"
            },
            "global_variables": {
                "max_connections": "1000",
                "innodb_buffer_pool_size": "7516192768",
                "wsrep_cluster_name": "demo-galera-cluster",
                "wsrep_node_name": "db-node-01",
                "wsrep_provider_options": "gcache.size=0; gcs.fc_limit=16"
            }
        },
        {
            "hostname": "db-node-02.demo.local",
            "datacenter": "dc1",
            "role": "galera_node",
            "system_resources": {
                "cpu_cores": 8,
                "ram_gb": 32,
                "disk_total_gb": 300
            },
            "global_status": {
                "Uptime": "90500",
                "Questions": "18500000",
                "Threads_connected": "12",
                "Max_used_connections": "145",
                "wsrep_cluster_size": "7",
                "wsrep_cluster_status": "Primary",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.00002"
            },
            "global_variables": {
                "max_connections": "1000",
                "innodb_buffer_pool_size": "7516192768",
                "wsrep_cluster_name": "demo-galera-cluster"
            }
        },
        {
            "hostname": "db-node-03.demo.local",
            "datacenter": "dc2",
            "role": "galera_node",
            "system_resources": {
                "cpu_cores": 8,
                "ram_gb": 32,
                "disk_total_gb": 300
            },
            "global_status": {
                "Uptime": "90800",
                "Questions": "236920535",
                "Threads_connected": "141",
                "Max_used_connections": "171",
                "wsrep_cluster_size": "7",
                "wsrep_cluster_status": "Primary",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.00001"
            },
            "global_variables": {
                "max_connections": "1000",
                "innodb_buffer_pool_size": "7516192768",
                "wsrep_cluster_name": "demo-galera-cluster"
            }
        }
    ]
};

// Sample log data
const SAMPLE_LOGS = [
    "2025-01-07 10:15:23 [ERROR] InnoDB: Unable to lock ./ibdata1 error: 11",
    "2025-01-07 10:16:45 [Warning] Aborted connection 12345 to db: 'appdb' user: 'appuser' host: '10.0.1.50' (Got timeout reading communication packets)",
    "2025-01-07 10:18:02 [Note] WSREP: Member 2.0 (db-node-03) synced with group."
];

// Sample data for different topologies
const SAMPLE_DATA = {
    galera: SAMPLE_CLUSTER_DATA,
    semisync: {
        "cluster_name": "demo-semisync-cluster",
        "topology_type": "semi-sync",
        "nodes": [
            {
                "hostname": "db-master-01.demo.local",
                "role": "master",
                "system_resources": { "cpu_cores": 8, "ram_gb": 32, "disk_total_gb": 500 },
                "global_status": {
                    "Uptime": "86400",
                    "Questions": "25000000",
                    "Threads_connected": "45",
                    "Max_used_connections": "180",
                    "Rpl_semi_sync_master_status": "ON",
                    "Rpl_semi_sync_master_clients": "2",
                    "Rpl_semi_sync_master_yes_tx": "150000",
                    "Rpl_semi_sync_master_no_tx": "5",
                    "Innodb_buffer_pool_read_requests": "500000000",
                    "Innodb_buffer_pool_reads": "1500000"
                },
                "global_variables": {
                    "max_connections": "500",
                    "innodb_buffer_pool_size": "21474836480",
                    "rpl_semi_sync_master_enabled": "ON",
                    "rpl_semi_sync_master_timeout": "10000",
                    "rpl_semi_sync_master_wait_point": "AFTER_SYNC"
                }
            },
            {
                "hostname": "db-replica-01.demo.local",
                "role": "replica",
                "system_resources": { "cpu_cores": 8, "ram_gb": 32, "disk_total_gb": 500 },
                "global_status": {
                    "Uptime": "86400",
                    "Slave_IO_Running": "Yes",
                    "Slave_SQL_Running": "Yes",
                    "Seconds_Behind_Master": "0",
                    "Rpl_semi_sync_slave_status": "ON"
                },
                "global_variables": {
                    "max_connections": "500",
                    "innodb_buffer_pool_size": "21474836480",
                    "rpl_semi_sync_slave_enabled": "ON",
                    "read_only": "ON"
                }
            },
            {
                "hostname": "db-replica-02.demo.local",
                "role": "replica",
                "system_resources": { "cpu_cores": 8, "ram_gb": 32, "disk_total_gb": 500 },
                "global_status": {
                    "Uptime": "86200",
                    "Slave_IO_Running": "Yes",
                    "Slave_SQL_Running": "Yes",
                    "Seconds_Behind_Master": "2",
                    "Rpl_semi_sync_slave_status": "ON"
                },
                "global_variables": {
                    "max_connections": "500",
                    "innodb_buffer_pool_size": "21474836480",
                    "rpl_semi_sync_slave_enabled": "ON",
                    "read_only": "ON"
                }
            }
        ]
    },
    standalone: {
        "cluster_name": "demo-standalone",
        "topology_type": "standalone",
        "nodes": [
            {
                "hostname": "db-standalone-01.demo.local",
                "role": "standalone",
                "system_resources": { "cpu_cores": 4, "ram_gb": 16, "disk_total_gb": 200 },
                "global_status": {
                    "Uptime": "172800",
                    "Questions": "8500000",
                    "Threads_connected": "25",
                    "Max_used_connections": "85",
                    "Innodb_buffer_pool_read_requests": "120000000",
                    "Innodb_buffer_pool_reads": "360000",
                    "Com_select": "6000000",
                    "Com_insert": "1500000",
                    "Com_update": "800000",
                    "Com_delete": "200000"
                },
                "global_variables": {
                    "max_connections": "200",
                    "innodb_buffer_pool_size": "10737418240",
                    "innodb_log_file_size": "536870912",
                    "query_cache_size": "0",
                    "slow_query_log": "ON",
                    "long_query_time": "2"
                }
            }
        ]
    }
};

// State
let currentAnalysis = null;
let chatHistory = [];
let currentLogs = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('MariaDB Cluster Analyzer initialized');
    checkAPIHealth();
});

// API Health Check
async function checkAPIHealth() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/health`);
        if (response.ok) {
            updateStatus('🟢', 'Connected to backend. Ready to analyze.');
        } else {
            updateStatus('🟡', 'Backend responding but with issues.');
        }
    } catch (error) {
        updateStatus('🔴', 'Cannot connect to backend. Start the server on port 8000.');
    }
}

// Update status bar
function updateStatus(icon, text) {
    document.querySelector('.status-icon').textContent = icon;
    document.querySelector('.status-text').textContent = text;
}

// Load sample data
function loadSampleData(type = 'galera') {
    const data = SAMPLE_DATA[type] || SAMPLE_DATA.galera;
    const textarea = document.getElementById('clusterData');
    textarea.value = JSON.stringify(data, null, 2);
    document.getElementById('clusterName').value = data.cluster_name;
    document.getElementById('topologyType').value = data.topology_type;
    switchInputTab('json');
    updateStatus('📊', `${type.charAt(0).toUpperCase() + type.slice(1)} sample loaded. Click "Run AI Analysis" to analyze.`);
}

// Switch input tabs
function switchInputTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.tab-btn[onclick*="${tabName}"]`)?.classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.input-tab-content').forEach(tab => tab.classList.add('hidden'));
    document.getElementById(`tab-${tabName}`)?.classList.remove('hidden');
}

// Parse SHOW GLOBAL STATUS output to JSON
function parseStatusToJson() {
    const input = document.getElementById('statusData').value.trim();
    if (!input) {
        updateStatus('⚠️', 'Please paste SHOW GLOBAL STATUS output first.');
        return;
    }
    
    const status = parseTabSeparatedData(input);
    
    // Update or create node in cluster data
    let clusterData = getOrCreateClusterData();
    if (clusterData.nodes.length === 0) {
        clusterData.nodes.push({ hostname: 'node-01', global_status: {}, global_variables: {} });
    }
    clusterData.nodes[0].global_status = status;
    
    document.getElementById('clusterData').value = JSON.stringify(clusterData, null, 2);
    switchInputTab('json');
    updateStatus('✅', `Parsed ${Object.keys(status).length} status variables. Check JSON tab.`);
}

// Parse SHOW GLOBAL VARIABLES output to JSON
function parseVariablesToJson() {
    const input = document.getElementById('variablesData').value.trim();
    if (!input) {
        updateStatus('⚠️', 'Please paste SHOW GLOBAL VARIABLES output first.');
        return;
    }
    
    const variables = parseTabSeparatedData(input);
    
    // Update or create node in cluster data
    let clusterData = getOrCreateClusterData();
    if (clusterData.nodes.length === 0) {
        clusterData.nodes.push({ hostname: 'node-01', global_status: {}, global_variables: {} });
    }
    clusterData.nodes[0].global_variables = variables;
    
    document.getElementById('clusterData').value = JSON.stringify(clusterData, null, 2);
    switchInputTab('json');
    updateStatus('✅', `Parsed ${Object.keys(variables).length} variables. Check JSON tab.`);
}

// Parse MaxScale config to JSON
function parseMaxScaleToJson() {
    const input = document.getElementById('maxscaleConfig').value.trim();
    if (!input) {
        updateStatus('⚠️', 'Please paste MaxScale configuration first.');
        return;
    }
    
    const config = parseIniConfig(input);
    
    // Update cluster data with MaxScale config
    let clusterData = getOrCreateClusterData();
    clusterData.maxscale_config = config;
    
    document.getElementById('clusterData').value = JSON.stringify(clusterData, null, 2);
    switchInputTab('json');
    updateStatus('✅', `Parsed MaxScale config with ${Object.keys(config).length} sections. Check JSON tab.`);
}

// Parse tab-separated key-value data (SHOW STATUS/VARIABLES output)
function parseTabSeparatedData(input) {
    const result = {};
    const lines = input.split('\n');
    
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('+') || trimmed.startsWith('|') && trimmed.includes('Variable_name')) {
            continue; // Skip header/border lines
        }
        
        // Handle pipe-delimited format (mysql client output)
        if (trimmed.startsWith('|')) {
            const parts = trimmed.split('|').map(p => p.trim()).filter(p => p);
            if (parts.length >= 2) {
                result[parts[0]] = parts[1];
            }
            continue;
        }
        
        // Handle tab-separated format
        const tabIndex = trimmed.indexOf('\t');
        if (tabIndex > 0) {
            const key = trimmed.substring(0, tabIndex).trim();
            const value = trimmed.substring(tabIndex + 1).trim();
            result[key] = value;
        } else {
            // Try space-separated (at least 2 spaces)
            const match = trimmed.match(/^(\S+)\s{2,}(.+)$/);
            if (match) {
                result[match[1]] = match[2].trim();
            }
        }
    }
    
    return result;
}

// Parse INI-style config (MaxScale)
function parseIniConfig(input) {
    const result = {};
    let currentSection = null;
    
    const lines = input.split('\n');
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith(';')) {
            continue; // Skip comments and empty lines
        }
        
        // Section header
        const sectionMatch = trimmed.match(/^\[([^\]]+)\]$/);
        if (sectionMatch) {
            currentSection = sectionMatch[1];
            result[currentSection] = {};
            continue;
        }
        
        // Key=value pair
        if (currentSection) {
            const eqIndex = trimmed.indexOf('=');
            if (eqIndex > 0) {
                const key = trimmed.substring(0, eqIndex).trim();
                const value = trimmed.substring(eqIndex + 1).trim();
                result[currentSection][key] = value;
            }
        }
    }
    
    return result;
}

// Get or create cluster data structure
function getOrCreateClusterData() {
    const existing = document.getElementById('clusterData').value.trim();
    if (existing) {
        try {
            return JSON.parse(existing);
        } catch (e) {}
    }
    
    return {
        cluster_name: document.getElementById('clusterName').value || 'my-cluster',
        topology_type: document.getElementById('topologyType').value || 'standalone',
        nodes: []
    };
}

// Clear data
function clearData() {
    document.getElementById('clusterData').value = '';
    document.getElementById('logData').value = '';
    hideResults();
    updateStatus('📊', 'Ready to analyze. Load sample data or paste your cluster configuration.');
}

// Load sample logs
function loadSampleLogs() {
    document.getElementById('logData').value = SAMPLE_LOGS.join('\n');
    updateStatus('📋', 'Sample logs loaded. Enable "Log Analysis" and run analysis.');
}

// Hide all result cards
function hideResults() {
    document.getElementById('healthCard').style.display = 'none';
    document.getElementById('findingsCard').style.display = 'none';
    document.getElementById('recommendationsCard').style.display = 'none';
    document.getElementById('logAnalysisCard').style.display = 'none';
}

// Show loading overlay
function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

// Run AI Analysis
async function runAnalysis() {
    const clusterDataText = document.getElementById('clusterData').value.trim();
    
    if (!clusterDataText) {
        updateStatus('⚠️', 'Please paste cluster data or load sample data first.');
        return;
    }
    
    let clusterData;
    try {
        clusterData = JSON.parse(clusterDataText);
    } catch (e) {
        updateStatus('❌', 'Invalid JSON. Please check your cluster data format.');
        return;
    }
    
    showLoading(true);
    updateStatus('🔄', 'Analyzing cluster with AI...');
    
    try {
        // Prepare request
        const request = {
            cluster_name: document.getElementById('clusterName').value || clusterData.cluster_name,
            topology_type: document.getElementById('topologyType').value || clusterData.topology_type,
            nodes: clusterData.nodes || [],
            maxscale_config: clusterData.maxscale_config || null,
            server_config: clusterData.server_config || null
        };
        
        // Call AI analysis endpoint
        const response = await fetch(`${API_BASE}/api/v1/ai/analyze/cluster`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(request)
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentAnalysis = result.data;
            displayResults(result.data);
            
            // Run log analysis if logs provided and option enabled
            const logData = document.getElementById('logData').value.trim();
            const includeLogs = document.getElementById('includeLogs').checked;
            
            if (logData && includeLogs) {
                await runLogAnalysis(logData);
            }
            
            updateStatus('✅', 'Analysis complete! Review findings below.');
        } else {
            updateStatus('❌', `Analysis failed: ${result.error}`);
        }
    } catch (error) {
        console.error('Analysis error:', error);
        updateStatus('❌', `Error: ${error.message}`);
    } finally {
        showLoading(false);
    }
}

// Run log analysis
async function runLogAnalysis(logData) {
    const logEntries = logData.split('\n').filter(line => line.trim());
    
    if (logEntries.length === 0) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/v1/ai/analyze/logs`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                log_type: 'mariadb',
                log_entries: logEntries.slice(0, 5) // Limit to 5 for demo
            })
        });
        
        const result = await response.json();
        
        if (result.success && result.data.interpretations) {
            displayLogAnalysis(result.data.interpretations);
        }
    } catch (error) {
        console.error('Log analysis error:', error);
    }
}

// Display log analysis results
function displayLogAnalysis(interpretations) {
    const card = document.getElementById('logAnalysisCard');
    const listEl = document.getElementById('logAnalysisList');
    
    listEl.innerHTML = interpretations.map(log => `
        <div class="log-item">
            <div class="log-original">${escapeHtml(log.original_entry || '')}</div>
            <div class="log-interpretation">
                <div class="log-field">
                    <div class="log-field-label">Severity</div>
                    <div class="log-field-value">${log.severity || 'unknown'}</div>
                </div>
                <div class="log-field">
                    <div class="log-field-label">Category</div>
                    <div class="log-field-value">${log.category || 'general'}</div>
                </div>
                <div class="log-field" style="grid-column: 1 / -1;">
                    <div class="log-field-label">Summary</div>
                    <div class="log-field-value">${log.summary || ''}</div>
                </div>
                <div class="log-action">
                    💡 ${log.recommended_action || 'No action required'}
                </div>
            </div>
        </div>
    `).join('');
    
    card.style.display = 'block';
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Display analysis results
function displayResults(data) {
    // Health Status Badge
    const healthCard = document.getElementById('healthCard');
    const healthBadge = document.getElementById('healthBadge');
    const healthSummary = document.getElementById('healthSummary');
    
    const score = data.health_score || 0;
    healthBadge.className = 'health-badge';
    
    if (score >= 80) {
        healthBadge.classList.add('status-good');
        healthBadge.textContent = '✓ Good';
    } else if (score >= 60) {
        healthBadge.classList.add('status-average');
        healthBadge.textContent = '⚠ Needs Attention';
    } else {
        healthBadge.classList.add('status-critical');
        healthBadge.textContent = '✕ Critical';
    }
    
    healthSummary.textContent = data.summary || '';
    healthCard.style.display = 'block';
    
    // Findings
    const findings = data.findings || [];
    if (findings.length > 0) {
        displayFindings(findings);
    }
    
    // Recommendations
    const recommendations = data.recommendations || [];
    if (recommendations.length > 0) {
        displayRecommendations(recommendations);
    }
}

// Display findings
function displayFindings(findings) {
    const card = document.getElementById('findingsCard');
    const countsEl = document.getElementById('findingCounts');
    const listEl = document.getElementById('findingsList');
    
    // Count by severity
    const counts = { critical: 0, warning: 0, info: 0 };
    findings.forEach(f => {
        const severity = f.severity?.toLowerCase() || 'info';
        if (counts[severity] !== undefined) counts[severity]++;
    });
    
    countsEl.innerHTML = `
        ${counts.critical > 0 ? `<span class="finding-count critical">🔴 ${counts.critical}</span>` : ''}
        ${counts.warning > 0 ? `<span class="finding-count warning">🟡 ${counts.warning}</span>` : ''}
        ${counts.info > 0 ? `<span class="finding-count info">🔵 ${counts.info}</span>` : ''}
    `;
    
    listEl.innerHTML = findings.map(f => {
        const severity = f.severity?.toLowerCase() || 'info';
        return `
            <div class="finding-item ${severity}">
                <div class="finding-header">
                    <span class="finding-category">${f.category || 'General'}</span>
                    <span class="finding-severity ${severity}">${severity}</span>
                </div>
                <div class="finding-text">${f.finding || ''}</div>
                ${f.recommendation ? `<div class="finding-recommendation">💡 ${f.recommendation}</div>` : ''}
            </div>
        `;
    }).join('');
    
    card.style.display = 'block';
}

// Display recommendations
function displayRecommendations(recommendations) {
    const card = document.getElementById('recommendationsCard');
    const listEl = document.getElementById('recommendationsList');
    
    listEl.innerHTML = recommendations.map((rec, i) => `
        <div class="recommendation-item">
            <span class="recommendation-number">${i + 1}</span>
            <span class="recommendation-text">${rec}</span>
        </div>
    `).join('');
    
    card.style.display = 'block';
}


// Chat functionality
async function sendChat() {
    const input = document.getElementById('chatInput');
    const question = input.value.trim();
    
    if (!question) return;
    
    // Add user message to UI
    addChatMessage('user', question);
    input.value = '';
    
    // Get cluster context if available
    let clusterContext = null;
    const clusterDataText = document.getElementById('clusterData').value.trim();
    if (clusterDataText) {
        try {
            clusterContext = JSON.parse(clusterDataText);
        } catch (e) {}
    }
    
    // Get log context if available
    const logDataText = document.getElementById('logData').value.trim();
    const logEntries = logDataText ? logDataText.split('\n').filter(l => l.trim()) : [];
    
    try {
        const response = await fetch(`${API_BASE}/api/v1/ai/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                cluster_context: clusterContext,
                log_entries: logEntries.slice(0, 10),
                chat_history: chatHistory.slice(-5)
            })
        });
        
        const result = await response.json();
        
        // Add to history
        chatHistory.push({ role: 'user', content: question });
        chatHistory.push({ role: 'assistant', content: result.answer });
        
        // Display response
        addChatMessage('assistant', result.answer);
        
        if (result.context_used) {
            addChatMessage('assistant', '📚 <em>Answer enhanced with documentation context</em>', true);
        }
    } catch (error) {
        addChatMessage('assistant', `Error: ${error.message}`);
    }
}

// Add chat message to UI
function addChatMessage(role, content, isHtml = false) {
    const messagesEl = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (isHtml) {
        contentDiv.innerHTML = content;
    } else {
        contentDiv.textContent = content;
    }
    
    messageDiv.appendChild(contentDiv);
    messagesEl.appendChild(messageDiv);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// Handle chat keypress
function handleChatKeypress(event) {
    if (event.key === 'Enter') {
        sendChat();
    }
}
