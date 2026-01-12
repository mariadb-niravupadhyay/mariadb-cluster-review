// MariaDB AI Advisor - Main Application
const API_BASE = 'http://localhost:8000';
const DATA_API = `${API_BASE}/api/v1/data`;

// Data Store
let appData = {
    customers: [],
    nextId: 1
};

// API connectivity flag
let useAPI = true;

// Generate unique ID (for localStorage fallback)
function generateId() {
    return `id_${appData.nextId++}_${Date.now()}`;
}

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    console.log('MariaDB AI Advisor initialized');
    await loadData();
    renderCustomers();
    updateStats();
});

// ==================== API Functions ====================

async function loadData() {
    try {
        // Try to load from API first
        const response = await fetch(`${DATA_API}/customers`);
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                // Load full data with clusters and nodes
                await loadFullDataFromAPI();
                useAPI = true;
                console.log('Data loaded from MariaDB Cloud');
                return;
            }
        }
    } catch (error) {
        console.log('API unavailable, using localStorage:', error.message);
    }
    
    // Fallback to localStorage
    useAPI = false;
    loadFromStorage();
}

async function loadFullDataFromAPI() {
    try {
        // Get customers
        const customersRes = await fetch(`${DATA_API}/customers`);
        const customersData = await customersRes.json();
        
        // Get clusters
        const clustersRes = await fetch(`${DATA_API}/clusters`);
        const clustersData = await clustersRes.json();
        
        // Get nodes
        const nodesRes = await fetch(`${DATA_API}/nodes`);
        const nodesData = await nodesRes.json();
        
        // Build nested structure
        appData.customers = customersData.data.map(customer => ({
            id: customer.id,
            name: customer.name,
            email: customer.email,
            createdAt: customer.created_at,
            clusters: clustersData.data
                .filter(c => c.customer_id === customer.id)
                .map(cluster => ({
                    id: cluster.id,
                    name: cluster.name,
                    topology: cluster.topology,
                    environment: cluster.environment,
                    createdAt: cluster.created_at,
                    nodes: nodesData.data
                        .filter(n => n.cluster_id === cluster.id)
                        .map(node => ({
                            id: node.id,
                            hostname: node.hostname,
                            role: node.role,
                            system_resources: {
                                cpu_cores: node.cpu_cores,
                                ram_gb: node.ram_gb,
                                disk_total_gb: node.disk_total_gb,
                                storage_type: node.storage_type
                            },
                            global_status: node.global_status ? JSON.parse(node.global_status) : {},
                            global_variables: node.global_variables ? JSON.parse(node.global_variables) : {},
                            maxscale_config: node.maxscale_config ? JSON.parse(node.maxscale_config) : null,
                            createdAt: node.created_at
                        }))
                }))
        }));
        
    } catch (error) {
        console.error('Error loading full data from API:', error);
        throw error;
    }
}

// Storage functions (localStorage fallback)
function saveToStorage() {
    localStorage.setItem('mariadb_advisor_data', JSON.stringify(appData));
}

function loadFromStorage() {
    const saved = localStorage.getItem('mariadb_advisor_data');
    if (saved) {
        appData = JSON.parse(saved);
    }
}

// Update statistics display
function updateStats() {
    let totalClusters = 0;
    let totalNodes = 0;
    let readyNodes = 0;
    
    appData.customers.forEach(customer => {
        totalClusters += customer.clusters.length;
        customer.clusters.forEach(cluster => {
            totalNodes += cluster.nodes.length;
            cluster.nodes.forEach(node => {
                if (node.global_status || node.global_variables) {
                    readyNodes++;
                }
            });
        });
    });
    
    const statCustomers = document.getElementById('statCustomers');
    const statClusters = document.getElementById('statClusters');
    const statNodes = document.getElementById('statNodes');
    
    if (statCustomers) statCustomers.textContent = appData.customers.length;
    if (statClusters) statClusters.textContent = totalClusters;
    if (statNodes) statNodes.textContent = totalNodes;
}

// Modal functions
function showModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
    // Clear form inputs
    const modal = document.getElementById(modalId);
    modal.querySelectorAll('input, textarea, select').forEach(el => {
        if (el.type !== 'hidden') {
            el.value = el.tagName === 'SELECT' ? el.options[0].value : '';
        }
    });
}

// Customer functions
function showAddCustomer() {
    showModal('customerModal');
}

async function addCustomer() {
    const name = document.getElementById('customerName').value.trim();
    const email = document.getElementById('customerEmail').value.trim();
    
    if (!name) {
        alert('Please enter a customer name');
        return;
    }
    
    if (!email) {
        alert('Please enter an email address');
        return;
    }
    
    if (useAPI) {
        try {
            const response = await fetch(`${DATA_API}/customers`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email })
            });
            
            const result = await response.json();
            if (!response.ok || !result.success) {
                alert(result.detail || result.error || 'Failed to create customer');
                return;
            }
            
            // Reload data from API
            await loadFullDataFromAPI();
        } catch (error) {
            alert('Error creating customer: ' + error.message);
            return;
        }
    } else {
        // LocalStorage fallback
        const customer = {
            id: generateId(),
            name: name,
            email: email,
            clusters: [],
            createdAt: new Date().toISOString()
        };
        appData.customers.push(customer);
        saveToStorage();
    }
    
    renderCustomers();
    updateStats();
    closeModal('customerModal');
}

async function deleteCustomer(customerId) {
    if (!confirm('Delete this customer and all their clusters?')) return;
    
    if (useAPI) {
        try {
            const response = await fetch(`${DATA_API}/customers/${customerId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                alert('Failed to delete customer');
                return;
            }
            await loadFullDataFromAPI();
        } catch (error) {
            alert('Error deleting customer: ' + error.message);
            return;
        }
    } else {
        appData.customers = appData.customers.filter(c => c.id !== customerId);
        saveToStorage();
    }
    
    renderCustomers();
    updateStats();
}

// Cluster functions
function showAddCluster(customerId) {
    document.getElementById('clusterCustomerId').value = customerId;
    showModal('clusterModal');
}

async function addCluster() {
    const customerId = document.getElementById('clusterCustomerId').value;
    const name = document.getElementById('clusterName').value.trim();
    const topology = document.getElementById('clusterTopology').value;
    const env = document.getElementById('clusterEnv').value;
    
    if (!name) {
        alert('Please enter a cluster name');
        return;
    }
    
    if (useAPI) {
        try {
            const response = await fetch(`${DATA_API}/clusters`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: parseInt(customerId),
                    name: name,
                    topology: topology,
                    environment: env
                })
            });
            
            const result = await response.json();
            if (!response.ok || !result.success) {
                alert(result.detail || result.error || 'Failed to create cluster');
                return;
            }
            
            await loadFullDataFromAPI();
        } catch (error) {
            alert('Error creating cluster: ' + error.message);
            return;
        }
    } else {
        const customer = appData.customers.find(c => c.id === customerId);
        if (!customer) return;
        
        const cluster = {
            id: generateId(),
            name: name,
            topology: topology,
            environment: env,
            nodes: [],
            createdAt: new Date().toISOString()
        };
        
        customer.clusters.push(cluster);
        saveToStorage();
    }
    
    renderCustomers();
    updateStats();
    closeModal('clusterModal');
}

async function deleteCluster(customerId, clusterId) {
    if (!confirm('Delete this cluster and all its nodes?')) return;
    
    if (useAPI) {
        try {
            const response = await fetch(`${DATA_API}/clusters/${clusterId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                alert('Failed to delete cluster');
                return;
            }
            await loadFullDataFromAPI();
        } catch (error) {
            alert('Error deleting cluster: ' + error.message);
            return;
        }
    } else {
        const customer = appData.customers.find(c => c.id === customerId);
        if (customer) {
            customer.clusters = customer.clusters.filter(c => c.id !== clusterId);
            saveToStorage();
        }
    }
    
    renderCustomers();
    updateStats();
}

// Node functions
function showAddNode(clusterId) {
    document.getElementById('nodeClusterId').value = clusterId;
    showModal('nodeModal');
}

function switchNodeTab(tabName) {
    document.querySelectorAll('#nodeModal .tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('#nodeModal .tab-content').forEach(tab => tab.classList.add('hidden'));
    
    event.target.classList.add('active');
    document.getElementById(`nodeTab-${tabName}`).classList.remove('hidden');
}

async function addNode() {
    const clusterId = document.getElementById('nodeClusterId').value;
    const name = document.getElementById('nodeName').value.trim();
    const role = document.getElementById('nodeRole').value;
    const cpu = parseInt(document.getElementById('nodeCpu').value) || 0;
    const ram = parseInt(document.getElementById('nodeRam').value) || 0;
    const storage = parseInt(document.getElementById('nodeStorage').value) || 0;
    const storageType = document.getElementById('nodeStorageType').value;
    
    if (!name) {
        alert('Please enter a node hostname');
        return;
    }
    
    // Parse status and variables
    const statusText = document.getElementById('nodeStatus').value.trim();
    const variablesText = document.getElementById('nodeVariables').value.trim();
    const maxscaleText = document.getElementById('nodeMaxscale').value.trim();
    
    const globalStatus = statusText ? parseKeyValueData(statusText) : null;
    const globalVariables = variablesText ? parseKeyValueData(variablesText) : null;
    const maxscaleConfig = maxscaleText ? parseIniConfig(maxscaleText) : null;
    
    if (useAPI) {
        try {
            const response = await fetch(`${DATA_API}/nodes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cluster_id: parseInt(clusterId),
                    hostname: name,
                    role: role,
                    cpu_cores: cpu,
                    ram_gb: ram,
                    disk_total_gb: storage,
                    storage_type: storageType,
                    global_status: globalStatus,
                    global_variables: globalVariables,
                    maxscale_config: maxscaleConfig
                })
            });
            
            const result = await response.json();
            if (!response.ok || !result.success) {
                alert(result.detail || result.error || 'Failed to create node');
                return;
            }
            
            await loadFullDataFromAPI();
        } catch (error) {
            alert('Error creating node: ' + error.message);
            return;
        }
    } else {
        // Find the cluster for localStorage fallback
        let targetCluster = null;
        for (const customer of appData.customers) {
            for (const cluster of customer.clusters) {
                if (cluster.id === clusterId) {
                    targetCluster = cluster;
                    break;
                }
            }
            if (targetCluster) break;
        }
        
        if (!targetCluster) return;
        
        const node = {
            id: generateId(),
            hostname: name,
            role: role,
            system_resources: {
                cpu_cores: cpu,
                ram_gb: ram,
                disk_total_gb: storage,
                storage_type: storageType
            },
            global_status: globalStatus || {},
            global_variables: globalVariables || {},
            maxscale_config: maxscaleConfig,
            createdAt: new Date().toISOString()
        };
        
        targetCluster.nodes.push(node);
        saveToStorage();
    }
    
    renderCustomers();
    updateStats();
    closeModal('nodeModal');
}

async function deleteNode(customerId, clusterId, nodeId) {
    if (!confirm('Delete this node?')) return;
    
    if (useAPI) {
        try {
            const response = await fetch(`${DATA_API}/nodes/${nodeId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                alert('Failed to delete node');
                return;
            }
            await loadFullDataFromAPI();
        } catch (error) {
            alert('Error deleting node: ' + error.message);
            return;
        }
    } else {
        const customer = appData.customers.find(c => c.id === customerId);
        if (customer) {
            const cluster = customer.clusters.find(c => c.id === clusterId);
            if (cluster) {
                cluster.nodes = cluster.nodes.filter(n => n.id !== nodeId);
                saveToStorage();
            }
        }
    }
    
    renderCustomers();
    updateStats();
}

// Parse functions
function parseKeyValueData(input) {
    const result = {};
    const lines = input.split('\n');
    
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('+') || (trimmed.startsWith('|') && trimmed.includes('Variable_name'))) {
            continue;
        }
        
        if (trimmed.startsWith('|')) {
            const parts = trimmed.split('|').map(p => p.trim()).filter(p => p);
            if (parts.length >= 2) {
                result[parts[0]] = parts[1];
            }
            continue;
        }
        
        const tabIndex = trimmed.indexOf('\t');
        if (tabIndex > 0) {
            result[trimmed.substring(0, tabIndex).trim()] = trimmed.substring(tabIndex + 1).trim();
        } else {
            const match = trimmed.match(/^(\S+)\s{2,}(.+)$/);
            if (match) {
                result[match[1]] = match[2].trim();
            }
        }
    }
    
    return result;
}

function parseIniConfig(input) {
    const result = {};
    let currentSection = null;
    
    for (const line of input.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith(';')) continue;
        
        const sectionMatch = trimmed.match(/^\[([^\]]+)\]$/);
        if (sectionMatch) {
            currentSection = sectionMatch[1];
            result[currentSection] = {};
            continue;
        }
        
        if (currentSection) {
            const eqIndex = trimmed.indexOf('=');
            if (eqIndex > 0) {
                result[currentSection][trimmed.substring(0, eqIndex).trim()] = trimmed.substring(eqIndex + 1).trim();
            }
        }
    }
    
    return result;
}

// Render functions - Update counts on dashboard
function renderCustomers() {
    // Update nav card counts if on dashboard
    const navCustomerCount = document.getElementById('navCustomerCount');
    const navClusterCount = document.getElementById('navClusterCount');
    const navNodeCount = document.getElementById('navNodeCount');
    
    if (navCustomerCount) {
        let totalClusters = 0;
        let totalNodes = 0;
        appData.customers.forEach(c => {
            totalClusters += c.clusters.length;
            c.clusters.forEach(cl => totalNodes += cl.nodes.length);
        });
        
        navCustomerCount.textContent = appData.customers.length;
        navClusterCount.textContent = totalClusters;
        navNodeCount.textContent = totalNodes;
    }
}

function renderCustomersTable() {
    const tbody = document.getElementById('customersTableBody');
    
    if (appData.customers.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="4">No customers. Click "+ Add" or "Load Demo Data".</td></tr>';
        return;
    }
    
    tbody.innerHTML = appData.customers.map(customer => `
        <tr>
            <td><strong>${escapeHtml(customer.name)}</strong></td>
            <td>${customer.email || '-'}</td>
            <td>${customer.clusters.length}</td>
            <td class="actions-cell">
                <button class="btn btn-xs btn-primary" onclick="showAddCluster('${customer.id}')">+ Cluster</button>
                <button class="btn btn-xs btn-danger" onclick="deleteCustomer('${customer.id}')">Delete</button>
            </td>
        </tr>
    `).join('');
}

function renderClustersTable() {
    const tbody = document.getElementById('clustersTableBody');
    const allClusters = [];
    
    appData.customers.forEach(customer => {
        customer.clusters.forEach(cluster => {
            allClusters.push({ customer, cluster });
        });
    });
    
    if (allClusters.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="5">No clusters configured.</td></tr>';
        return;
    }
    
    tbody.innerHTML = allClusters.map(({ customer, cluster }) => {
        const hasNodes = cluster.nodes.length > 0;
        return `
        <tr>
            <td>${escapeHtml(customer.name)}</td>
            <td><strong>${escapeHtml(cluster.name)}</strong></td>
            <td><span class="badge badge-${cluster.topology}">${cluster.topology}</span></td>
            <td>${cluster.nodes.length}</td>
            <td class="actions-cell">
                ${hasNodes ? `<button class="btn btn-xs btn-primary" onclick="runClusterAnalysis('${customer.id}', '${cluster.id}')">AI Analysis</button>` : ''}
                ${hasNodes ? `<button class="btn btn-xs btn-outline" onclick="openLogsAnalyzer('${customer.id}', '${cluster.id}')">Logs</button>` : ''}
                <button class="btn btn-xs btn-secondary" onclick="showAddNode('${cluster.id}')">+ Node</button>
                <button class="btn btn-xs btn-danger" onclick="deleteCluster('${customer.id}', '${cluster.id}')">Delete</button>
            </td>
        </tr>
    `}).join('');
}

function renderNodesTable() {
    const tbody = document.getElementById('nodesTableBody');
    const allNodes = [];
    
    appData.customers.forEach(customer => {
        customer.clusters.forEach(cluster => {
            cluster.nodes.forEach(node => {
                allNodes.push({ customer, cluster, node });
            });
        });
    });
    
    if (allNodes.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="8">No nodes configured.</td></tr>';
        return;
    }
    
    tbody.innerHTML = allNodes.map(({ customer, cluster, node }) => {
        const hasData = Object.keys(node.global_status || {}).length > 0;
        const resources = node.system_resources || {};
        return `
        <tr>
            <td>${escapeHtml(customer.name)}</td>
            <td>${escapeHtml(cluster.name)}</td>
            <td><strong>${escapeHtml(node.hostname)}</strong></td>
            <td><span class="badge badge-role">${node.role}</span></td>
            <td>${resources.cpu_cores || '-'}</td>
            <td>${resources.ram_gb ? resources.ram_gb + ' GB' : '-'}</td>
            <td><span class="status-dot ${hasData ? 'status-ok' : 'status-pending'}"></span> ${hasData ? 'Ready' : 'Pending'}</td>
            <td class="actions-cell">
                <button class="btn btn-xs btn-danger" onclick="deleteNode('${customer.id}', '${cluster.id}', '${node.id}')">Delete</button>
            </td>
        </tr>
    `}).join('');
}

// Show add dialogs from table buttons
function showAddClusterFromTable() {
    if (appData.customers.length === 0) {
        alert('Please add a customer first.');
        return;
    }
    // Use first customer or show selection
    showAddCluster(appData.customers[0].id);
}

function showAddNodeFromTable() {
    const allClusters = [];
    appData.customers.forEach(c => c.clusters.forEach(cl => allClusters.push(cl)));
    if (allClusters.length === 0) {
        alert('Please add a cluster first.');
        return;
    }
    showAddNode(allClusters[0].id);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Open Logs Analyzer
function openLogsAnalyzer(customerId, clusterId) {
    const customer = appData.customers.find(c => c.id == customerId);
    if (!customer) {
        console.log('Customer not found:', customerId);
        return;
    }
    
    const cluster = customer.clusters.find(c => c.id == clusterId);
    if (!cluster || cluster.nodes.length === 0) {
        alert('No nodes in this cluster to analyze logs.');
        return;
    }
    
    // Store cluster info for logs page
    const logsData = {
        customer: customer.name,
        cluster_name: cluster.name,
        topology_type: cluster.topology,
        nodes: cluster.nodes.map(n => ({
            id: n.id,
            hostname: n.hostname,
            role: n.role
        }))
    };
    
    localStorage.setItem('mariadb_logs_input', JSON.stringify(logsData));
    window.location.href = 'logs.html';
}

// Loading spinner functions
function showLoadingSpinner(message = 'Loading...') {
    let overlay = document.getElementById('globalLoadingOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'globalLoadingOverlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-spinner-container">
                <div class="spinner"></div>
                <p class="loading-message">${message}</p>
            </div>
        `;
        document.body.appendChild(overlay);
    } else {
        overlay.querySelector('.loading-message').textContent = message;
    }
    overlay.classList.add('active');
}

function hideLoadingSpinner() {
    const overlay = document.getElementById('globalLoadingOverlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

// Toggle demo dropdown menu
function toggleDemoMenu() {
    const menu = document.getElementById('demoMenu');
    if (menu) {
        menu.classList.toggle('show');
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.demo-dropdown')) {
        const menu = document.getElementById('demoMenu');
        if (menu) menu.classList.remove('show');
    }
});

// Load Demo Data - Galera Balanced Workload
async function loadSampleCustomer() {
    showLoadingSpinner('Loading Galera demo data...');
    
    const demoNodes = [
        {
            hostname: "db-node-01.demo.local",
            role: "galera",
            cpu_cores: 8, ram_gb: 32, disk_total_gb: 500, storage_type: "ssd",
            global_status: {
                "Uptime": "345600",
                "Questions": "125000000",
                "Threads_connected": "85",
                "Threads_running": "12",
                "Max_used_connections": "245",
                "Com_select": "98000000",
                "Com_insert": "15000000",
                "Com_update": "8500000",
                "Com_delete": "3500000",
                "wsrep_cluster_size": "3",
                "wsrep_cluster_status": "Primary",
                "wsrep_ready": "ON",
                "wsrep_local_state_comment": "Synced",
                "Innodb_buffer_pool_read_requests": "980000000",
                "Innodb_buffer_pool_reads": "2500000",
                "Innodb_buffer_pool_pages_total": "1310720",
                "Innodb_buffer_pool_pages_free": "85000"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "21474836480",
                "wsrep_cluster_name": "production-galera",
                "wsrep_node_name": "db-node-01"
            }
        },
        {
            hostname: "db-node-02.demo.local",
            role: "galera",
            cpu_cores: 8, ram_gb: 32, disk_total_gb: 500, storage_type: "ssd",
            global_status: {
                "Uptime": "345500",
                "Questions": "118000000",
                "Threads_connected": "78",
                "Threads_running": "10",
                "Com_select": "92000000",
                "Com_insert": "14000000",
                "Com_update": "8000000",
                "Com_delete": "4000000",
                "wsrep_cluster_size": "3",
                "wsrep_ready": "ON",
                "wsrep_local_state_comment": "Synced"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "21474836480"
            }
        },
        {
            hostname: "db-node-03.demo.local",
            role: "galera",
            cpu_cores: 8, ram_gb: 32, disk_total_gb: 500, storage_type: "ssd",
            global_status: {
                "Uptime": "345400",
                "Questions": "115000000",
                "Threads_connected": "72",
                "Threads_running": "8",
                "Com_select": "90000000",
                "Com_insert": "13500000",
                "Com_update": "7500000",
                "Com_delete": "4000000",
                "wsrep_cluster_size": "3",
                "wsrep_ready": "ON",
                "wsrep_local_state_comment": "Synced"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "21474836480"
            }
        }
    ];
    
    if (useAPI) {
        try {
            // Create customer
            const custRes = await fetch(`${DATA_API}/customers`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: "Demo Corporation", email: "admin@demo.corp" })
            });
            if (!custRes.ok) {
                throw new Error('API unavailable');
            }
            const custData = await custRes.json();
            
            // Create cluster
            const clusterRes = await fetch(`${DATA_API}/clusters`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: custData.id,
                    name: "production-galera",
                    topology: "galera",
                    environment: "production"
                })
            });
            const clusterData = await clusterRes.json();
            
            // Create nodes
            for (const node of demoNodes) {
                await fetch(`${DATA_API}/nodes`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cluster_id: clusterData.id,
                        hostname: node.hostname,
                        role: node.role,
                        cpu_cores: node.cpu_cores,
                        ram_gb: node.ram_gb,
                        disk_total_gb: node.disk_total_gb,
                        storage_type: node.storage_type,
                        global_status: node.global_status,
                        global_variables: node.global_variables
                    })
                });
            }
            
            await loadFullDataFromAPI();
        } catch (error) {
            console.warn('API unavailable, using localStorage fallback:', error.message);
            // Fall through to localStorage fallback below
            useAPI = false;
        }
    }
    
    if (!useAPI) {
        // LocalStorage fallback
        const demoCustomer = {
            id: generateId(),
            name: "Demo Corporation",
            email: "admin@demo.corp",
            clusters: [{
                id: generateId(),
                name: "production-galera",
                topology: "galera",
                environment: "production",
                nodes: demoNodes.map(n => ({
                    id: generateId(),
                    hostname: n.hostname,
                    role: n.role,
                    system_resources: {
                        cpu_cores: n.cpu_cores,
                        ram_gb: n.ram_gb,
                        disk_total_gb: n.disk_total_gb,
                        storage_type: n.storage_type
                    },
                    global_status: n.global_status,
                    global_variables: n.global_variables
                }))
            }],
            createdAt: new Date().toISOString()
        };
        appData.customers.push(demoCustomer);
        saveToStorage();
    }
    
    renderCustomers();
    updateStats();
    hideLoadingSpinner();
}

// Load Demo Data - Async Replication at Max Capacity (needs scale up)
async function loadAsyncReplicationDemo() {
    showLoadingSpinner('Loading Async Replication demo data...');
    
    const demoNodes = [
        {
            hostname: "db-primary-01.ecom.local",
            role: "primary",
            cpu_cores: 4, ram_gb: 16, disk_total_gb: 200, storage_type: "ssd",
            global_status: {
                "Uptime": "172800",
                "Questions": "285000000",
                "Threads_connected": "380",
                "Threads_running": "45",
                "Max_used_connections": "478",
                "Com_select": "85000000",
                "Com_insert": "95000000",
                "Com_update": "72000000",
                "Com_delete": "33000000",
                "Slow_queries": "12500",
                "Innodb_buffer_pool_read_requests": "650000000",
                "Innodb_buffer_pool_reads": "18500000",
                "Innodb_buffer_pool_pages_total": "524288",
                "Innodb_buffer_pool_pages_free": "8500",
                "Innodb_row_lock_waits": "45000",
                "Innodb_row_lock_time_avg": "850",
                "Bytes_received": "125000000000",
                "Bytes_sent": "380000000000"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "8589934592",
                "server_id": "1",
                "log_bin": "ON",
                "binlog_format": "ROW"
            }
        },
        {
            hostname: "db-replica-01.ecom.local",
            role: "replica",
            cpu_cores: 4, ram_gb: 16, disk_total_gb: 200, storage_type: "ssd",
            global_status: {
                "Uptime": "172700",
                "Questions": "92000000",
                "Threads_connected": "125",
                "Threads_running": "18",
                "Max_used_connections": "185",
                "Com_select": "88000000",
                "Com_insert": "1500000",
                "Com_update": "1800000",
                "Com_delete": "700000",
                "Slave_IO_Running": "Yes",
                "Slave_SQL_Running": "Yes",
                "Seconds_Behind_Master": "45",
                "Innodb_buffer_pool_read_requests": "420000000",
                "Innodb_buffer_pool_reads": "9500000",
                "Innodb_buffer_pool_pages_total": "524288",
                "Innodb_buffer_pool_pages_free": "12000"
            },
            global_variables: {
                "max_connections": "300",
                "innodb_buffer_pool_size": "8589934592",
                "server_id": "2",
                "read_only": "ON"
            }
        },
        {
            hostname: "db-replica-02.ecom.local",
            role: "replica",
            cpu_cores: 4, ram_gb: 16, disk_total_gb: 200, storage_type: "ssd",
            global_status: {
                "Uptime": "172650",
                "Questions": "88000000",
                "Threads_connected": "118",
                "Threads_running": "15",
                "Max_used_connections": "172",
                "Com_select": "85000000",
                "Com_insert": "1200000",
                "Com_update": "1300000",
                "Com_delete": "500000",
                "Slave_IO_Running": "Yes",
                "Slave_SQL_Running": "Yes",
                "Seconds_Behind_Master": "62",
                "Innodb_buffer_pool_read_requests": "395000000",
                "Innodb_buffer_pool_reads": "11000000",
                "Innodb_buffer_pool_pages_total": "524288",
                "Innodb_buffer_pool_pages_free": "9500"
            },
            global_variables: {
                "max_connections": "300",
                "innodb_buffer_pool_size": "8589934592",
                "server_id": "3",
                "read_only": "ON"
            }
        }
    ];
    
    if (useAPI) {
        try {
            const custRes = await fetch(`${DATA_API}/customers`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: "E-Commerce Platform Inc", email: "dba@ecommerce.io" })
            });
            if (!custRes.ok) {
                throw new Error('API unavailable');
            }
            const custData = await custRes.json();
            
            const clusterRes = await fetch(`${DATA_API}/clusters`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: custData.id,
                    name: "ecom-async-replication",
                    topology: "async",
                    environment: "production"
                })
            });
            const clusterData = await clusterRes.json();
            
            for (const node of demoNodes) {
                await fetch(`${DATA_API}/nodes`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cluster_id: clusterData.id,
                        hostname: node.hostname,
                        role: node.role,
                        cpu_cores: node.cpu_cores,
                        ram_gb: node.ram_gb,
                        disk_total_gb: node.disk_total_gb,
                        storage_type: node.storage_type,
                        global_status: node.global_status,
                        global_variables: node.global_variables
                    })
                });
            }
            
            await loadFullDataFromAPI();
        } catch (error) {
            console.warn('API unavailable, using localStorage fallback:', error.message);
            useAPI = false;
        }
    }
    
    if (!useAPI) {
        const demoCustomer = {
            id: generateId(),
            name: "E-Commerce Platform Inc",
            email: "dba@ecommerce.io",
            clusters: [{
                id: generateId(),
                name: "ecom-async-replication",
                topology: "async",
                environment: "production",
                nodes: demoNodes.map(n => ({
                    id: generateId(),
                    hostname: n.hostname,
                    role: n.role,
                    system_resources: {
                        cpu_cores: n.cpu_cores,
                        ram_gb: n.ram_gb,
                        disk_total_gb: n.disk_total_gb,
                        storage_type: n.storage_type
                    },
                    global_status: n.global_status,
                    global_variables: n.global_variables
                }))
            }],
            createdAt: new Date().toISOString()
        };
        appData.customers.push(demoCustomer);
        saveToStorage();
    }
    
    renderCustomers();
    updateStats();
    hideLoadingSpinner();
}

// Load Demo Data - Healthy Galera Write-Heavy (well configured)
async function loadGaleraHealthyDemo() {
    showLoadingSpinner('Loading Galera Write-Heavy demo data...');
    
    const demoNodes = [
        {
            hostname: "galera-prod-01.fintech.local",
            role: "galera",
            cpu_cores: 16, ram_gb: 64, disk_total_gb: 1000, storage_type: "nvme",
            global_status: {
                "Uptime": "864000",
                "Questions": "520000000",
                "Threads_connected": "185",
                "Threads_running": "22",
                "Max_used_connections": "312",
                "Com_select": "145000000",
                "Com_insert": "185000000",
                "Com_update": "125000000",
                "Com_delete": "65000000",
                "Slow_queries": "450",
                "wsrep_cluster_size": "3",
                "wsrep_cluster_status": "Primary",
                "wsrep_ready": "ON",
                "wsrep_connected": "ON",
                "wsrep_local_state": "4",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.002",
                "wsrep_flow_control_sent": "125",
                "wsrep_local_recv_queue_avg": "0.05",
                "wsrep_local_send_queue_avg": "0.02",
                "wsrep_cert_deps_distance": "85.5",
                "Innodb_buffer_pool_read_requests": "2850000000",
                "Innodb_buffer_pool_reads": "4200000",
                "Innodb_buffer_pool_pages_total": "2097152",
                "Innodb_buffer_pool_pages_free": "125000",
                "Innodb_row_lock_waits": "8500",
                "Innodb_row_lock_time_avg": "120"
            },
            global_variables: {
                "max_connections": "1000",
                "innodb_buffer_pool_size": "34359738368",
                "wsrep_cluster_name": "fintech-galera-prod",
                "wsrep_node_name": "galera-prod-01",
                "wsrep_provider_options": "gcache.size=2G;gcs.fc_limit=256",
                "innodb_flush_log_at_trx_commit": "2",
                "sync_binlog": "0"
            }
        },
        {
            hostname: "galera-prod-02.fintech.local",
            role: "galera",
            cpu_cores: 16, ram_gb: 64, disk_total_gb: 1000, storage_type: "nvme",
            global_status: {
                "Uptime": "863900",
                "Questions": "515000000",
                "Threads_connected": "178",
                "Threads_running": "20",
                "Max_used_connections": "298",
                "Com_select": "142000000",
                "Com_insert": "182000000",
                "Com_update": "122000000",
                "Com_delete": "69000000",
                "Slow_queries": "380",
                "wsrep_cluster_size": "3",
                "wsrep_cluster_status": "Primary",
                "wsrep_ready": "ON",
                "wsrep_connected": "ON",
                "wsrep_local_state": "4",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.003",
                "wsrep_flow_control_sent": "98",
                "Innodb_buffer_pool_read_requests": "2780000000",
                "Innodb_buffer_pool_reads": "3950000",
                "Innodb_buffer_pool_pages_total": "2097152",
                "Innodb_buffer_pool_pages_free": "118000"
            },
            global_variables: {
                "max_connections": "1000",
                "innodb_buffer_pool_size": "34359738368",
                "wsrep_cluster_name": "fintech-galera-prod",
                "wsrep_node_name": "galera-prod-02"
            }
        },
        {
            hostname: "galera-prod-03.fintech.local",
            role: "galera",
            cpu_cores: 16, ram_gb: 64, disk_total_gb: 1000, storage_type: "nvme",
            global_status: {
                "Uptime": "863800",
                "Questions": "508000000",
                "Threads_connected": "172",
                "Threads_running": "18",
                "Max_used_connections": "285",
                "Com_select": "138000000",
                "Com_insert": "180000000",
                "Com_update": "120000000",
                "Com_delete": "70000000",
                "Slow_queries": "410",
                "wsrep_cluster_size": "3",
                "wsrep_cluster_status": "Primary",
                "wsrep_ready": "ON",
                "wsrep_connected": "ON",
                "wsrep_local_state": "4",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.001",
                "wsrep_flow_control_sent": "75",
                "Innodb_buffer_pool_read_requests": "2720000000",
                "Innodb_buffer_pool_reads": "3800000",
                "Innodb_buffer_pool_pages_total": "2097152",
                "Innodb_buffer_pool_pages_free": "132000"
            },
            global_variables: {
                "max_connections": "1000",
                "innodb_buffer_pool_size": "34359738368",
                "wsrep_cluster_name": "fintech-galera-prod",
                "wsrep_node_name": "galera-prod-03"
            }
        }
    ];
    
    if (useAPI) {
        try {
            const custRes = await fetch(`${DATA_API}/customers`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: "FinTech Solutions Ltd", email: "ops@fintech.local" })
            });
            if (!custRes.ok) {
                throw new Error('API unavailable');
            }
            const custData = await custRes.json();
            
            const clusterRes = await fetch(`${DATA_API}/clusters`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: custData.id,
                    name: "fintech-galera-prod",
                    topology: "galera",
                    environment: "production"
                })
            });
            const clusterData = await clusterRes.json();
            
            for (const node of demoNodes) {
                await fetch(`${DATA_API}/nodes`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cluster_id: clusterData.id,
                        hostname: node.hostname,
                        role: node.role,
                        cpu_cores: node.cpu_cores,
                        ram_gb: node.ram_gb,
                        disk_total_gb: node.disk_total_gb,
                        storage_type: node.storage_type,
                        global_status: node.global_status,
                        global_variables: node.global_variables
                    })
                });
            }
            
            await loadFullDataFromAPI();
        } catch (error) {
            console.warn('API unavailable, using localStorage fallback:', error.message);
            useAPI = false;
        }
    }
    
    if (!useAPI) {
        const demoCustomer = {
            id: generateId(),
            name: "FinTech Solutions Ltd",
            email: "ops@fintech.local",
            clusters: [{
                id: generateId(),
                name: "fintech-galera-prod",
                topology: "galera",
                environment: "production",
                nodes: demoNodes.map(n => ({
                    id: generateId(),
                    hostname: n.hostname,
                    role: n.role,
                    system_resources: {
                        cpu_cores: n.cpu_cores,
                        ram_gb: n.ram_gb,
                        disk_total_gb: n.disk_total_gb,
                        storage_type: n.storage_type
                    },
                    global_status: n.global_status,
                    global_variables: n.global_variables
                }))
            }],
            createdAt: new Date().toISOString()
        };
        appData.customers.push(demoCustomer);
        saveToStorage();
    }
    
    renderCustomers();
    updateStats();
    hideLoadingSpinner();
}

// ============ NEW HIGH-QUALITY DEMO SCENARIOS ============

// Demo 1: Galera with Flow Control Bottleneck (one slow node dragging down cluster)
async function loadGaleraFlowControlDemo() {
    showLoadingSpinner('Loading Galera Flow Control demo...');
    
    const demoNodes = [
        {
            hostname: "galera-dc1-01.retail.local",
            role: "galera",
            cpu_cores: 8, ram_gb: 32, disk_total_gb: 500, storage_type: "ssd",
            global_status: {
                "Uptime": "604800",
                "Questions": "285000000",
                "Threads_connected": "145",
                "Threads_running": "18",
                "Max_used_connections": "312",
                "Com_select": "195000000",
                "Com_insert": "45000000",
                "Com_update": "32000000",
                "Com_delete": "13000000",
                "Slow_queries": "1250",
                "wsrep_cluster_size": "5",
                "wsrep_cluster_status": "Primary",
                "wsrep_ready": "ON",
                "wsrep_connected": "ON",
                "wsrep_local_state": "4",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.008",
                "wsrep_flow_control_sent": "45",
                "wsrep_flow_control_recv": "2850",
                "wsrep_local_recv_queue_avg": "0.12",
                "wsrep_local_send_queue_avg": "0.05",
                "wsrep_cert_deps_distance": "125.5",
                "Innodb_buffer_pool_read_requests": "1850000000",
                "Innodb_buffer_pool_reads": "2800000",
                "Innodb_buffer_pool_pages_total": "1310720",
                "Innodb_buffer_pool_pages_free": "95000",
                "Innodb_row_lock_waits": "4500",
                "Innodb_row_lock_time_avg": "85"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "21474836480",
                "wsrep_cluster_name": "retail-galera-prod",
                "wsrep_node_name": "galera-dc1-01",
                "wsrep_slave_threads": "4",
                "innodb_flush_log_at_trx_commit": "2",
                "sync_binlog": "0"
            }
        },
        {
            hostname: "galera-dc1-02.retail.local",
            role: "galera",
            cpu_cores: 8, ram_gb: 32, disk_total_gb: 500, storage_type: "ssd",
            global_status: {
                "Uptime": "604750",
                "Questions": "278000000",
                "Threads_connected": "138",
                "Threads_running": "15",
                "Max_used_connections": "298",
                "Com_select": "188000000",
                "Com_insert": "44000000",
                "Com_update": "33000000",
                "Com_delete": "13000000",
                "wsrep_cluster_size": "5",
                "wsrep_ready": "ON",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.006",
                "wsrep_flow_control_sent": "32",
                "wsrep_flow_control_recv": "2780",
                "Innodb_buffer_pool_read_requests": "1780000000",
                "Innodb_buffer_pool_reads": "2650000"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "21474836480",
                "wsrep_slave_threads": "4"
            }
        },
        {
            hostname: "galera-dc2-01.retail.local",
            role: "galera",
            cpu_cores: 8, ram_gb: 32, disk_total_gb: 500, storage_type: "ssd",
            global_status: {
                "Uptime": "604700",
                "Questions": "265000000",
                "Threads_connected": "125",
                "Threads_running": "12",
                "Max_used_connections": "278",
                "Com_select": "180000000",
                "Com_insert": "42000000",
                "Com_update": "31000000",
                "Com_delete": "12000000",
                "wsrep_cluster_size": "5",
                "wsrep_ready": "ON",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.005",
                "wsrep_flow_control_sent": "28",
                "wsrep_flow_control_recv": "2650",
                "Innodb_buffer_pool_read_requests": "1680000000",
                "Innodb_buffer_pool_reads": "2450000"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "21474836480",
                "wsrep_slave_threads": "4"
            }
        },
        {
            hostname: "galera-dc2-02.retail.local",
            role: "galera",
            cpu_cores: 4, ram_gb: 16, disk_total_gb: 200, storage_type: "hdd",
            global_status: {
                "Uptime": "604650",
                "Questions": "142000000",
                "Threads_connected": "85",
                "Threads_running": "28",
                "Max_used_connections": "185",
                "Com_select": "95000000",
                "Com_insert": "24000000",
                "Com_update": "16000000",
                "Com_delete": "7000000",
                "Slow_queries": "8500",
                "wsrep_cluster_size": "5",
                "wsrep_ready": "ON",
                "wsrep_local_state_comment": "Synced",
                "wsrep_flow_control_paused": "0.185",
                "wsrep_flow_control_sent": "4250",
                "wsrep_flow_control_recv": "185",
                "wsrep_local_recv_queue_avg": "8.5",
                "wsrep_local_send_queue_avg": "0.8",
                "wsrep_apply_window": "12.5",
                "Innodb_buffer_pool_read_requests": "850000000",
                "Innodb_buffer_pool_reads": "28500000",
                "Innodb_buffer_pool_pages_total": "524288",
                "Innodb_buffer_pool_pages_free": "8500",
                "Innodb_row_lock_waits": "45000",
                "Innodb_row_lock_time_avg": "1250"
            },
            global_variables: {
                "max_connections": "300",
                "innodb_buffer_pool_size": "8589934592",
                "wsrep_slave_threads": "1"
            }
        },
        {
            hostname: "galera-arb.retail.local",
            role: "arbitrator",
            cpu_cores: 2, ram_gb: 4, disk_total_gb: 50, storage_type: "ssd",
            global_status: {
                "wsrep_cluster_size": "5",
                "wsrep_ready": "ON",
                "wsrep_local_state_comment": "Synced"
            },
            global_variables: {}
        }
    ];
    
    await loadDemoData("Retail Systems Corp", "retail@corp.local", "retail-galera-5node", "galera", demoNodes);
}

// Demo 2: Semi-Sync Replication with Data Loss Risk Configuration
async function loadSemiSyncDataLossRiskDemo() {
    showLoadingSpinner('Loading Semi-Sync Data Loss Risk demo...');
    
    const demoNodes = [
        {
            hostname: "db-primary.healthcare.local",
            role: "primary",
            cpu_cores: 16, ram_gb: 64, disk_total_gb: 1000, storage_type: "nvme",
            global_status: {
                "Uptime": "2592000",
                "Questions": "1850000000",
                "Threads_connected": "285",
                "Threads_running": "35",
                "Max_used_connections": "412",
                "Com_select": "1250000000",
                "Com_insert": "285000000",
                "Com_update": "225000000",
                "Com_delete": "90000000",
                "Slow_queries": "3500",
                "Rpl_semi_sync_master_status": "ON",
                "Rpl_semi_sync_master_clients": "1",
                "Rpl_semi_sync_master_yes_tx": "45000000",
                "Rpl_semi_sync_master_no_tx": "125000",
                "Rpl_semi_sync_master_net_avg_wait_time": "850",
                "Innodb_buffer_pool_read_requests": "8500000000",
                "Innodb_buffer_pool_reads": "12500000",
                "Innodb_buffer_pool_pages_total": "2621440",
                "Innodb_buffer_pool_pages_free": "185000",
                "Binlog_commits": "600000000",
                "Binlog_group_commits": "125000000"
            },
            global_variables: {
                "max_connections": "1000",
                "innodb_buffer_pool_size": "42949672960",
                "server_id": "1",
                "log_bin": "mysql-bin",
                "binlog_format": "ROW",
                "rpl_semi_sync_master_enabled": "ON",
                "rpl_semi_sync_master_timeout": "10000",
                "rpl_semi_sync_master_wait_point": "AFTER_COMMIT",
                "sync_binlog": "0",
                "innodb_flush_log_at_trx_commit": "2"
            }
        },
        {
            hostname: "db-replica-semisync.healthcare.local",
            role: "replica",
            cpu_cores: 16, ram_gb: 64, disk_total_gb: 1000, storage_type: "nvme",
            global_status: {
                "Uptime": "2591900",
                "Questions": "850000000",
                "Threads_connected": "185",
                "Threads_running": "22",
                "Max_used_connections": "312",
                "Com_select": "845000000",
                "Slave_IO_Running": "Yes",
                "Slave_SQL_Running": "Yes",
                "Seconds_Behind_Master": "2",
                "Rpl_semi_sync_slave_status": "ON",
                "Innodb_buffer_pool_read_requests": "6200000000",
                "Innodb_buffer_pool_reads": "9500000",
                "Innodb_buffer_pool_pages_total": "2621440",
                "Innodb_buffer_pool_pages_free": "215000"
            },
            global_variables: {
                "max_connections": "800",
                "innodb_buffer_pool_size": "42949672960",
                "server_id": "2",
                "read_only": "ON",
                "rpl_semi_sync_slave_enabled": "ON",
                "sync_binlog": "1",
                "innodb_flush_log_at_trx_commit": "1"
            }
        },
        {
            hostname: "db-replica-async-dc2.healthcare.local",
            role: "replica",
            cpu_cores: 8, ram_gb: 32, disk_total_gb: 500, storage_type: "ssd",
            global_status: {
                "Uptime": "2591800",
                "Questions": "425000000",
                "Threads_connected": "95",
                "Threads_running": "12",
                "Max_used_connections": "185",
                "Com_select": "420000000",
                "Slave_IO_Running": "Yes",
                "Slave_SQL_Running": "Yes",
                "Seconds_Behind_Master": "45",
                "Innodb_buffer_pool_read_requests": "3100000000",
                "Innodb_buffer_pool_reads": "8500000",
                "Innodb_buffer_pool_pages_total": "1310720",
                "Innodb_buffer_pool_pages_free": "85000"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "21474836480",
                "server_id": "3",
                "read_only": "ON"
            }
        },
        {
            hostname: "db-replica-async-dc3.healthcare.local",
            role: "replica",
            cpu_cores: 8, ram_gb: 32, disk_total_gb: 500, storage_type: "ssd",
            global_status: {
                "Uptime": "2591700",
                "Questions": "380000000",
                "Threads_connected": "78",
                "Threads_running": "8",
                "Max_used_connections": "165",
                "Com_select": "375000000",
                "Slave_IO_Running": "Yes",
                "Slave_SQL_Running": "Yes",
                "Seconds_Behind_Master": "125",
                "Innodb_buffer_pool_read_requests": "2800000000",
                "Innodb_buffer_pool_reads": "7500000",
                "Innodb_buffer_pool_pages_total": "1310720",
                "Innodb_buffer_pool_pages_free": "95000"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "21474836480",
                "server_id": "4",
                "read_only": "ON"
            }
        }
    ];
    
    await loadDemoData("Healthcare Systems Inc", "dba@healthcare.local", "healthcare-semi-sync", "semi-sync", demoNodes);
}

// Demo 3: Standalone Database - Critical No HA (needs immediate attention)
async function loadStandaloneNoHADemo() {
    showLoadingSpinner('Loading Standalone No-HA demo...');
    
    const demoNodes = [
        {
            hostname: "db-standalone.startup.io",
            role: "standalone",
            cpu_cores: 4, ram_gb: 16, disk_total_gb: 200, storage_type: "ssd",
            global_status: {
                "Uptime": "7776000",
                "Questions": "2850000000",
                "Threads_connected": "245",
                "Threads_running": "42",
                "Max_used_connections": "488",
                "Com_select": "1950000000",
                "Com_insert": "450000000",
                "Com_update": "325000000",
                "Com_delete": "125000000",
                "Slow_queries": "28500",
                "Connections": "15000000",
                "Aborted_connects": "125000",
                "Aborted_clients": "85000",
                "Innodb_buffer_pool_read_requests": "12500000000",
                "Innodb_buffer_pool_reads": "385000000",
                "Innodb_buffer_pool_pages_total": "524288",
                "Innodb_buffer_pool_pages_free": "2500",
                "Innodb_buffer_pool_pages_dirty": "125000",
                "Innodb_row_lock_waits": "185000",
                "Innodb_row_lock_time_avg": "2850",
                "Innodb_data_reads": "450000000",
                "Innodb_data_writes": "285000000",
                "Innodb_log_waits": "12500",
                "Created_tmp_disk_tables": "8500000",
                "Handler_read_rnd_next": "125000000000",
                "Select_full_join": "2500000",
                "Open_tables": "1850",
                "Opened_tables": "125000"
            },
            global_variables: {
                "max_connections": "500",
                "innodb_buffer_pool_size": "8589934592",
                "server_id": "1",
                "log_bin": "OFF",
                "innodb_flush_log_at_trx_commit": "1",
                "sync_binlog": "0",
                "table_open_cache": "2000",
                "tmp_table_size": "67108864",
                "max_heap_table_size": "67108864",
                "innodb_log_file_size": "268435456",
                "innodb_io_capacity": "200",
                "innodb_io_capacity_max": "400"
            },
            system_resources: {
                "swap_total_gb": 8,
                "swap_used_gb": 3.5,
                "swappiness": 60
            }
        }
    ];
    
    await loadDemoData("TechStartup Inc", "dev@startup.io", "production-standalone", "standalone", demoNodes);
}

// Generic demo data loader
async function loadDemoData(customerName, customerEmail, clusterName, topology, nodes) {
    if (useAPI) {
        try {
            const custRes = await fetch(`${DATA_API}/customers`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: customerName, email: customerEmail })
            });
            if (!custRes.ok) throw new Error('API unavailable');
            const custData = await custRes.json();
            
            const clusterRes = await fetch(`${DATA_API}/clusters`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: custData.id,
                    name: clusterName,
                    topology: topology,
                    environment: "production"
                })
            });
            const clusterData = await clusterRes.json();
            
            for (const node of nodes) {
                await fetch(`${DATA_API}/nodes`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cluster_id: clusterData.id,
                        hostname: node.hostname,
                        role: node.role,
                        cpu_cores: node.cpu_cores,
                        ram_gb: node.ram_gb,
                        disk_total_gb: node.disk_total_gb,
                        storage_type: node.storage_type,
                        global_status: node.global_status,
                        global_variables: node.global_variables,
                        system_resources: node.system_resources
                    })
                });
            }
            await loadFullDataFromAPI();
        } catch (error) {
            console.warn('API unavailable, using localStorage fallback:', error.message);
            useAPI = false;
        }
    }
    
    if (!useAPI) {
        const demoCustomer = {
            id: generateId(),
            name: customerName,
            email: customerEmail,
            clusters: [{
                id: generateId(),
                name: clusterName,
                topology: topology,
                environment: "production",
                nodes: nodes.map(n => ({
                    id: generateId(),
                    hostname: n.hostname,
                    role: n.role,
                    system_resources: {
                        cpu_cores: n.cpu_cores,
                        ram_gb: n.ram_gb,
                        disk_total_gb: n.disk_total_gb,
                        storage_type: n.storage_type,
                        ...(n.system_resources || {})
                    },
                    global_status: n.global_status,
                    global_variables: n.global_variables
                }))
            }],
            createdAt: new Date().toISOString()
        };
        appData.customers.push(demoCustomer);
        saveToStorage();
    }
    
    renderCustomers();
    updateStats();
    hideLoadingSpinner();
}

// ============ END NEW DEMO SCENARIOS ============

// Run analysis for a specific cluster
function runClusterAnalysis(customerId, clusterId) {
    const customer = appData.customers.find(c => c.id == customerId);
    if (!customer) {
        console.log('Customer not found:', customerId);
        return;
    }
    
    const cluster = customer.clusters.find(c => c.id == clusterId);
    if (!cluster || cluster.nodes.length === 0) {
        alert('No nodes in this cluster to analyze.');
        return;
    }
    
    const analysisData = [{
        customer: customer.name,
        cluster_name: cluster.name,
        topology_type: cluster.topology,
        environment: cluster.environment,
        nodes: cluster.nodes.map(n => ({
            hostname: n.hostname,
            role: n.role,
            system_resources: n.system_resources,
            global_status: n.global_status,
            global_variables: n.global_variables
        }))
    }];
    
    localStorage.setItem('mariadb_analysis_input', JSON.stringify(analysisData));
    window.location.href = 'analysis.html';
}

// Run Full Analysis (all clusters)
async function runFullAnalysis() {
    const analysisData = [];
    
    for (const customer of appData.customers) {
        for (const cluster of customer.clusters) {
            if (cluster.nodes.length === 0) continue;
            
            analysisData.push({
                customer: customer.name,
                cluster_name: cluster.name,
                topology_type: cluster.topology,
                environment: cluster.environment,
                nodes: cluster.nodes.map(n => ({
                    hostname: n.hostname,
                    role: n.role,
                    system_resources: n.system_resources,
                    global_status: n.global_status,
                    global_variables: n.global_variables
                }))
            });
        }
    }
    
    if (analysisData.length === 0) {
        alert('Please add at least one cluster with nodes before running analysis.');
        return;
    }
    
    localStorage.setItem('mariadb_analysis_input', JSON.stringify(analysisData));
    window.location.href = 'analysis.html';
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

// Run analysis for a specific node
function runNodeAnalysis(customerId, clusterId, nodeId) {
    const customer = appData.customers.find(c => c.id == customerId);
    if (!customer) {
        console.log('Customer not found:', customerId);
        return;
    }
    
    const cluster = customer.clusters.find(c => c.id == clusterId);
    if (!cluster) {
        console.log('Cluster not found:', clusterId);
        return;
    }
    
    const node = cluster.nodes.find(n => n.id == nodeId);
    if (!node) {
        console.log('Node not found:', nodeId);
        return;
    }
    
    // Create analysis data for single node
    const analysisData = [{
        customer: customer.name,
        cluster_name: cluster.name,
        topology_type: cluster.topology,
        environment: cluster.environment,
        analysis_type: 'node',
        nodes: [{
            hostname: node.hostname,
            role: node.role,
            system_resources: node.system_resources,
            global_status: node.global_status,
            global_variables: node.global_variables,
            maxscale_config: node.maxscale_config
        }]
    }];
    
    localStorage.setItem('mariadb_analysis_input', JSON.stringify(analysisData));
    window.location.href = 'analysis.html';
}

// Open Logs Analyzer for a specific node
function openNodeLogsAnalyzer(customerId, clusterId, nodeId) {
    const customer = appData.customers.find(c => c.id == customerId);
    if (!customer) {
        console.log('Customer not found:', customerId);
        return;
    }
    
    const cluster = customer.clusters.find(c => c.id == clusterId);
    if (!cluster) {
        console.log('Cluster not found:', clusterId);
        return;
    }
    
    const node = cluster.nodes.find(n => n.id == nodeId);
    if (!node) {
        console.log('Node not found:', nodeId);
        return;
    }
    
    // Store single node info for logs page
    const logsData = {
        customer: customer.name,
        cluster_name: cluster.name,
        topology_type: cluster.topology,
        nodes: [{
            id: node.id,
            hostname: node.hostname,
            role: node.role
        }]
    };
    
    localStorage.setItem('mariadb_logs_input', JSON.stringify(logsData));
    window.location.href = 'logs.html';
}
