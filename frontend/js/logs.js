// Logs Analyzer JavaScript
const API_BASE = 'http://localhost:8000';

let logsData = null;
let nodeLogs = {};
let inputMode = 'upload'; // 'upload' or 'paste'
let uploadedFiles = {}; // Store file contents

document.addEventListener('DOMContentLoaded', () => {
    const savedData = localStorage.getItem('mariadb_logs_input');
    if (savedData) {
        logsData = JSON.parse(savedData);
        initializePage();
    } else {
        document.getElementById('clusterInfo').textContent = 'No cluster selected';
        document.getElementById('nodeLogInputs').innerHTML = `
            <div class="empty-state">
                <p>No cluster data found. Please go to the Dashboard and click "Logs Analyzer" on a cluster.</p>
                <a href="index.html" class="btn btn-primary">Go to Dashboard</a>
            </div>
        `;
    }
});

function initializePage() {
    // Update cluster info
    document.getElementById('clusterInfo').textContent = 
        `${logsData.cluster_name} (${logsData.topology_type}) - ${logsData.customer}`;
    
    // Generate log input fields for each node
    renderNodeLogInputs();
}

function setInputMode(mode) {
    inputMode = mode;
    document.getElementById('btnUpload').classList.toggle('active', mode === 'upload');
    document.getElementById('btnPaste').classList.toggle('active', mode === 'paste');
    renderNodeLogInputs();
}

function renderNodeLogInputs() {
    const container = document.getElementById('nodeLogInputs');
    
    if (inputMode === 'upload') {
        container.innerHTML = logsData.nodes.map(node => `
            <div class="node-log-input">
                <div class="node-log-header">
                    <span class="node-log-name">${escapeHtml(node.hostname)}</span>
                    <span class="node-log-role">${node.role}</span>
                </div>
                <div class="log-input-group">
                    <label>MariaDB Error Log</label>
                    <div class="file-upload-zone" id="dropzone-mariadb-${node.id}" 
                         ondrop="handleDrop(event, '${node.id}', 'mariadb')" 
                         ondragover="handleDragOver(event)"
                         ondragleave="handleDragLeave(event)">
                        <input type="file" id="file-mariadb-${node.id}" 
                               onchange="handleFileSelect(event, '${node.id}', 'mariadb')" 
                               accept=".log,.txt,.err">
                        <div class="upload-content">
                            <span class="upload-icon">📄</span>
                            <span class="upload-text" id="label-mariadb-${node.id}">Drop file or click to upload</span>
                        </div>
                    </div>
                </div>
                <div class="log-input-group">
                    <label>MaxScale Log (optional)</label>
                    <div class="file-upload-zone" id="dropzone-maxscale-${node.id}"
                         ondrop="handleDrop(event, '${node.id}', 'maxscale')" 
                         ondragover="handleDragOver(event)"
                         ondragleave="handleDragLeave(event)">
                        <input type="file" id="file-maxscale-${node.id}" 
                               onchange="handleFileSelect(event, '${node.id}', 'maxscale')" 
                               accept=".log,.txt">
                        <div class="upload-content">
                            <span class="upload-icon">📄</span>
                            <span class="upload-text" id="label-maxscale-${node.id}">Drop file or click to upload</span>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    } else {
        container.innerHTML = logsData.nodes.map(node => `
            <div class="node-log-input">
                <div class="node-log-header">
                    <span class="node-log-name">${escapeHtml(node.hostname)}</span>
                    <span class="node-log-role">${node.role}</span>
                </div>
                <div class="log-input-group">
                    <label>MariaDB Error Log</label>
                    <textarea 
                        id="mariadb-log-${node.id}" 
                        class="log-textarea" 
                        placeholder="Paste MariaDB error log content here..."
                        rows="6"
                    ></textarea>
                </div>
                <div class="log-input-group">
                    <label>MaxScale Log (optional)</label>
                    <textarea 
                        id="maxscale-log-${node.id}" 
                        class="log-textarea" 
                        placeholder="Paste MaxScale log content here (if applicable)..."
                        rows="4"
                    ></textarea>
                </div>
            </div>
        `).join('');
    }
}

// File upload handlers
function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
}

function handleDrop(e, nodeId, logType) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) {
        readFile(file, nodeId, logType);
    }
}

function handleFileSelect(e, nodeId, logType) {
    const file = e.target.files[0];
    if (file) {
        readFile(file, nodeId, logType);
    }
}

function readFile(file, nodeId, logType) {
    const reader = new FileReader();
    reader.onload = function(e) {
        const key = `${nodeId}-${logType}`;
        uploadedFiles[key] = e.target.result;
        
        // Update label
        const label = document.getElementById(`label-${logType}-${nodeId}`);
        if (label) {
            label.textContent = `✓ ${file.name} (${formatFileSize(file.size)})`;
            label.classList.add('file-loaded');
        }
        
        // Mark zone as loaded
        const zone = document.getElementById(`dropzone-${logType}-${nodeId}`);
        if (zone) {
            zone.classList.add('has-file');
        }
    };
    reader.readAsText(file);
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function analyzeAllLogs() {
    // Collect all logs from inputs (either uploaded files or pasted text)
    nodeLogs = {};
    let hasAnyLogs = false;
    
    for (const node of logsData.nodes) {
        let mariadbLog, maxscaleLog;
        
        if (inputMode === 'upload') {
            mariadbLog = uploadedFiles[`${node.id}-mariadb`] || '';
            maxscaleLog = uploadedFiles[`${node.id}-maxscale`] || '';
        } else {
            const mariadbEl = document.getElementById(`mariadb-log-${node.id}`);
            const maxscaleEl = document.getElementById(`maxscale-log-${node.id}`);
            mariadbLog = mariadbEl ? mariadbEl.value.trim() : '';
            maxscaleLog = maxscaleEl ? maxscaleEl.value.trim() : '';
        }
        
        if (mariadbLog || maxscaleLog) {
            hasAnyLogs = true;
            nodeLogs[node.id] = {
                hostname: node.hostname,
                role: node.role,
                mariadb_log: mariadbLog,
                maxscale_log: maxscaleLog
            };
        }
    }
    
    if (!hasAnyLogs) {
        alert('Please paste at least one log to analyze.');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`${API_BASE}/api/v1/ai/analyze/logs/timeline`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cluster_name: logsData.cluster_name,
                topology_type: logsData.topology_type,
                node_logs: nodeLogs
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.success && result.data) {
                displayLogsAnalysis(result.data);
                document.getElementById('logsSource').textContent = 'Gemini AI';
                document.getElementById('logsSource').className = 'source-badge ai';
            } else {
                displayLocalLogsAnalysis();
            }
        } else {
            displayLocalLogsAnalysis();
        }
    } catch (error) {
        console.error('Logs analysis error:', error);
        displayLocalLogsAnalysis();
    } finally {
        showLoading(false);
        document.getElementById('logsResultsSection').style.display = 'block';
    }
}

function displayLogsAnalysis(data) {
    const resultsContainer = document.getElementById('logsAnalysisResults');
    const timelineContainer = document.getElementById('eventsTimeline');
    
    // Display summary
    resultsContainer.innerHTML = `
        <div class="logs-summary">
            <h4>Analysis Summary</h4>
            <p>${escapeHtml(data.summary || 'No summary available.')}</p>
        </div>
        
        ${data.root_cause_analysis ? `
            <div class="logs-root-cause">
                <h4>Root Cause Analysis</h4>
                <p>${escapeHtml(data.root_cause_analysis)}</p>
            </div>
        ` : ''}
        
        ${data.critical_findings && data.critical_findings.length > 0 ? `
            <div class="logs-findings critical">
                <h4>Critical Findings</h4>
                <ul>
                    ${data.critical_findings.map(f => `<li>${escapeHtml(f)}</li>`).join('')}
                </ul>
            </div>
        ` : ''}
        
        ${data.warnings && data.warnings.length > 0 ? `
            <div class="logs-findings warning">
                <h4>Warnings</h4>
                <ul>
                    ${data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}
                </ul>
            </div>
        ` : ''}
        
        ${data.correlation_insights ? `
            <div class="logs-correlation">
                <h4>Cross-Node Correlation</h4>
                <p>${escapeHtml(data.correlation_insights)}</p>
            </div>
        ` : ''}
        
        ${data.recommendations && data.recommendations.length > 0 ? `
            <div class="logs-recommendations">
                <h4>Recommendations</h4>
                <ul>
                    ${data.recommendations.map(r => `<li>${escapeHtml(r)}</li>`).join('')}
                </ul>
            </div>
        ` : ''}
        
        ${data.local_analysis ? `
            <div class="logs-local-stats">
                <small>Pattern matching: ${data.local_analysis.findings_count} findings, ${data.local_analysis.events_extracted} events from ${data.local_analysis.nodes_analyzed?.length || 0} node(s)</small>
            </div>
        ` : ''}
    `;
    
    // Display timeline
    if (data.events && data.events.length > 0) {
        timelineContainer.innerHTML = `
            <div class="events-timeline">
                ${data.events.map(event => `
                    <div class="timeline-event ${event.severity || 'info'}">
                        <div class="event-time">${escapeHtml(event.timestamp || 'Unknown time')}</div>
                        <div class="event-node">${escapeHtml(event.node || 'Unknown node')}</div>
                        <div class="event-description">${escapeHtml(event.description || '')}</div>
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        timelineContainer.innerHTML = '<p class="text-muted">No significant events extracted from logs.</p>';
    }
}

function displayLocalLogsAnalysis() {
    const resultsContainer = document.getElementById('logsAnalysisResults');
    const timelineContainer = document.getElementById('eventsTimeline');
    
    document.getElementById('logsSource').textContent = 'Local (API unavailable)';
    document.getElementById('logsSource').className = 'source-badge local';
    
    // Basic local analysis - extract error patterns
    const allErrors = [];
    const allWarnings = [];
    
    for (const nodeId in nodeLogs) {
        const node = nodeLogs[nodeId];
        const logContent = (node.mariadb_log + '\n' + node.maxscale_log).toLowerCase();
        
        if (logContent.includes('error') || logContent.includes('fatal')) {
            allErrors.push(`Errors detected in ${node.hostname} logs`);
        }
        if (logContent.includes('warning') || logContent.includes('warn')) {
            allWarnings.push(`Warnings detected in ${node.hostname} logs`);
        }
    }
    
    resultsContainer.innerHTML = `
        <div class="logs-summary">
            <h4>Basic Analysis (AI unavailable)</h4>
            <p>For detailed AI-powered analysis, ensure the backend API is running.</p>
        </div>
        
        ${allErrors.length > 0 ? `
            <div class="logs-findings critical">
                <h4>Detected Issues</h4>
                <ul>
                    ${allErrors.map(e => `<li>${escapeHtml(e)}</li>`).join('')}
                </ul>
            </div>
        ` : ''}
        
        ${allWarnings.length > 0 ? `
            <div class="logs-findings warning">
                <h4>Warnings</h4>
                <ul>
                    ${allWarnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}
                </ul>
            </div>
        ` : ''}
    `;
    
    timelineContainer.innerHTML = '<p class="text-muted">Timeline extraction requires AI API.</p>';
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        if (show) {
            overlay.classList.add('active');
        } else {
            overlay.classList.remove('active');
        }
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
