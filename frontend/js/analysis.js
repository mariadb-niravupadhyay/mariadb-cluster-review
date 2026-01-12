// MariaDB AI Advisor - Analysis Page
const API_BASE = 'http://localhost:8000';

let analysisData = null;
let analysisResults = null;
let chatHistory = [];

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    // Load analysis input data
    const savedData = localStorage.getItem('mariadb_analysis_input');
    if (!savedData) {
        alert('No analysis data found. Please configure your clusters first.');
        window.location.href = 'index.html';
        return;
    }
    
    analysisData = JSON.parse(savedData);
    
    // Update report header
    if (analysisData.length > 0) {
        const first = analysisData[0];
        const isNodeAnalysis = first.analysis_type === 'node' && first.nodes.length === 1;
        
        if (isNodeAnalysis) {
            document.getElementById('reportTitle').textContent = `Node Analysis: ${first.nodes[0].hostname}`;
            document.getElementById('reportCustomer').textContent = `Customer: ${first.customer}`;
            document.getElementById('reportCluster').textContent = `Cluster: ${first.cluster_name} (${first.topology_type})`;
        } else {
            document.getElementById('reportTitle').textContent = `Analysis Report: ${first.cluster_name}`;
            document.getElementById('reportCustomer').textContent = `Customer: ${first.customer}`;
            document.getElementById('reportCluster').textContent = `Topology: ${first.topology_type}`;
        }
        document.getElementById('reportDate').textContent = `Generated: ${new Date().toLocaleDateString()}`;
    }
    
    // Run the analysis
    await runAnalysis();
});

// Run Analysis
async function runAnalysis() {
    showLoading(true, 'Connecting to Gemini AI...');
    
    let aiSuccess = false;
    
    try {
        for (const cluster of analysisData) {
            console.log('Calling Gemini AI analysis for:', cluster.cluster_name);
            updateLoadingText('Analyzing with Gemini AI...');
            
            const response = await fetch(`${API_BASE}/api/v1/ai/analyze/cluster`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cluster_name: cluster.cluster_name,
                    topology_type: cluster.topology_type,
                    nodes: cluster.nodes
                })
            });
            
            console.log('API Response status:', response.status);
            
            if (response.ok) {
                const result = await response.json();
                console.log('Gemini AI response:', result);
                
                if (result.success && result.data) {
                    analysisResults = result.data;
                    displayResults(analysisResults, cluster);
                    aiSuccess = true;
                    updateAnalysisSource('Gemini AI');
                    console.log('Gemini AI analysis applied successfully');
                } else {
                    console.log('API returned but no data, using local analysis');
                    displayLocalAnalysis(cluster);
                    updateAnalysisSource('Local (API returned no data)');
                }
            } else {
                const errorText = await response.text();
                console.log('API error:', response.status, errorText);
                displayLocalAnalysis(cluster);
                updateAnalysisSource('Local (API error: ' + response.status + ')');
            }
        }
    } catch (error) {
        console.log('AI API not available:', error.message);
        // Fallback to local analysis
        if (analysisData.length > 0) {
            displayLocalAnalysis(analysisData[0]);
            updateAnalysisSource('Local (API unavailable)');
        }
    } finally {
        showLoading(false);
        // Run workload analysis separately
        runWorkloadAnalysis();
    }
}

// Run workload analysis
async function runWorkloadAnalysis() {
    const workloadDiv = document.getElementById('workloadAnalysis');
    const workloadSource = document.getElementById('workloadSource');
    
    if (!analysisData || analysisData.length === 0) {
        workloadDiv.innerHTML = '<p class="text-muted">No cluster data available for workload analysis.</p>';
        return;
    }
    
    const cluster = analysisData[0];
    
    try {
        const response = await fetch(`${API_BASE}/api/v1/ai/analyze/workload`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cluster_name: cluster.cluster_name,
                topology_type: cluster.topology_type,
                nodes: cluster.nodes
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.success && result.data) {
                displayWorkloadAnalysis(result.data);
                workloadSource.textContent = 'Gemini AI';
                workloadSource.className = 'source-badge ai';
            } else {
                workloadDiv.innerHTML = '<p class="text-muted">Workload analysis not available.</p>';
                workloadSource.textContent = 'N/A';
            }
        } else {
            workloadDiv.innerHTML = '<p class="text-muted">Workload analysis API error.</p>';
            workloadSource.textContent = 'Error';
            workloadSource.className = 'source-badge local';
        }
    } catch (error) {
        workloadDiv.innerHTML = '<p class="text-muted">Workload analysis requires AI API.</p>';
        workloadSource.textContent = 'Unavailable';
        workloadSource.className = 'source-badge local';
    }
}

// Display workload analysis results
function displayWorkloadAnalysis(data) {
    const container = document.getElementById('workloadAnalysis');
    
    const statusColors = {
        'under-provisioned': 'warning',
        'right-sized': 'success',
        'over-provisioned': 'info',
        'adequate': 'success',
        'needs_more': 'warning',
        'over_allocated': 'info',
        'needs_attention': 'warning',
        'critical': 'error'
    };
    
    const statusClass = statusColors[data.provisioning_status] || '';
    
    let html = `
        <div class="workload-summary">
            <div class="workload-status ${statusClass}">
                <span class="status-label">Overall Status:</span>
                <span class="status-value">${data.provisioning_status?.replace('-', ' ').toUpperCase() || 'Unknown'}</span>
            </div>
            <p class="workload-summary-text">${escapeHtml(data.summary || '')}</p>
        </div>
        
        <div class="workload-assessments">
    `;
    
    // CPU Assessment
    if (data.cpu_assessment) {
        html += renderAssessmentCard('CPU', data.cpu_assessment, statusColors);
    }
    
    // Memory Assessment
    if (data.memory_assessment) {
        html += renderAssessmentCard('Memory', data.memory_assessment, statusColors);
    }
    
    // Storage Assessment
    if (data.storage_assessment) {
        html += renderAssessmentCard('Storage', data.storage_assessment, statusColors);
    }
    
    // Connection Assessment
    if (data.connection_assessment) {
        html += renderAssessmentCard('Connections', data.connection_assessment, statusColors);
    }
    
    html += '</div>';
    
    // Cost Optimization
    if (data.cost_optimization) {
        html += `
            <div class="cost-optimization">
                <h4>Cost Optimization</h4>
                <p>${escapeHtml(data.cost_optimization)}</p>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

function renderAssessmentCard(title, assessment, statusColors) {
    const statusClass = statusColors[assessment.status] || '';
    return `
        <div class="assessment-card">
            <div class="assessment-header">
                <span class="assessment-title">${title}</span>
                <span class="assessment-status ${statusClass}">${assessment.status?.replace('_', ' ') || 'N/A'}</span>
            </div>
            <p class="assessment-analysis">${escapeHtml(assessment.analysis || '')}</p>
            <p class="assessment-rec"><strong>Recommendation:</strong> ${escapeHtml(assessment.recommendation || 'N/A')}</p>
        </div>
    `;
}

function updateLoadingText(text) {
    const loadingText = document.querySelector('.loading-text');
    if (loadingText) loadingText.textContent = text;
}

function updateAnalysisSource(source) {
    const badge = document.getElementById('analysisSource');
    if (badge) {
        badge.textContent = source;
        badge.className = source.includes('Gemini') ? 'source-badge ai' : 'source-badge local';
    }
}

// Display results
function displayResults(results, clusterData) {
    // Health badge
    const healthBadge = document.getElementById('healthBadge');
    const score = results.health_score || calculateLocalScore(clusterData);
    
    if (score >= 80) {
        healthBadge.textContent = 'Healthy';
        healthBadge.className = 'health-badge status-good';
    } else if (score >= 60) {
        healthBadge.textContent = 'Needs Attention';
        healthBadge.className = 'health-badge status-average';
    } else {
        healthBadge.textContent = 'Critical';
        healthBadge.className = 'health-badge status-critical';
    }
    
    // Summary - convert to bullet points
    const summaryElement = document.getElementById('healthSummary');
    const summaryText = results.summary || `Analysis of ${clusterData.cluster_name} with ${clusterData.nodes.length} node(s).`;
    summaryElement.innerHTML = formatSummaryAsBullets(summaryText);
    
    // Query throughput and connection stats (displayed before findings)
    displayQueryStats(clusterData);
    
    // Node details (moved up, replacing resource summary)
    displayNodes(clusterData.nodes);
    
    // Architecture Assessment (Critical Questions) - only show if AI provided assessments
    displayArchitectureAssessment(results, clusterData);
    
    // Findings - make them user friendly (filter for node analysis)
    const isNodeAnalysis = clusterData.analysis_type === 'node';
    let findings = results.findings || generateLocalFindings(clusterData);
    if (isNodeAnalysis) {
        findings = filterNodeAnalysisFindings(findings);
    }
    displayFindings(findings);
    
    // Recommendations
    displayRecommendations(results.recommendations || generateLocalRecommendations(clusterData));
    
    // Display RAG sources if available
    displayAnalysisSources(results.rag_metadata);
}

// Display Architecture Assessment (Critical Questions Answered)
function displayArchitectureAssessment(results, clusterData) {
    const assessmentCard = document.getElementById('assessmentCard');
    const assessmentGrid = document.getElementById('assessmentGrid');
    const assessmentTitle = document.getElementById('assessmentCardTitle');
    const nodeDetailsCard = document.getElementById('nodeDetailsCard');
    
    if (!assessmentCard || !assessmentGrid) return;
    
    const isNodeAnalysis = clusterData.analysis_type === 'node';
    
    // Update title based on analysis type
    if (assessmentTitle) {
        assessmentTitle.textContent = isNodeAnalysis ? 'Node Assessment' : 'Architecture Assessment';
    }
    
    // Hide Node Details section for node analysis
    if (nodeDetailsCard) {
        nodeDetailsCard.style.display = isNodeAnalysis ? 'none' : 'block';
    }
    
    // Check if we have AI assessment data
    const hasCapacity = results.capacity_assessment;
    const hasHaDr = results.ha_dr_assessment && !isNodeAnalysis; // Skip HA/DR for node analysis
    const hasBottlenecks = results.bottlenecks && results.bottlenecks.length > 0;
    const hasWorkload = results.workload_assessment;
    
    if (!hasCapacity && !hasHaDr && !hasBottlenecks && !hasWorkload) {
        assessmentCard.style.display = 'none';
        return;
    }
    
    assessmentCard.style.display = 'block';
    let html = '<div class="assessment-cards">';
    
    // Capacity Assessment Card
    if (hasCapacity) {
        const cap = results.capacity_assessment;
        const statusClass = cap.status === 'right-sized' ? 'good' : 
                           cap.status === 'over-provisioned' ? 'warning' : 'critical';
        const statusIcon = cap.status === 'right-sized' ? '✓' : 
                          cap.status === 'over-provisioned' ? '📉' : '📈';
        html += `
            <div class="assessment-card ${statusClass}">
                <div class="assessment-icon">${statusIcon}</div>
                <div class="assessment-content">
                    <h4>Capacity & Scaling</h4>
                    <div class="assessment-status ${statusClass}">${cap.status?.replace('-', ' ').toUpperCase() || 'Unknown'}</div>
                    <p><strong>Can handle workload:</strong> ${cap.can_handle_current_workload ? 'Yes ✓' : 'No ✗'}</p>
                    <p><strong>Recommendation:</strong> ${cap.scale_recommendation?.replace('_', ' ') || 'N/A'}</p>
                    ${cap.cost_optimization_possible ? '<p class="cost-hint">💰 Cost optimization possible</p>' : ''}
                    <p class="assessment-details">${cap.details || ''}</p>
                </div>
            </div>`;
    }
    
    // HA/DR Assessment Card (only for architecture analysis, not node analysis)
    if (hasHaDr) {
        const ha = results.ha_dr_assessment;
        const statusClass = ha.ha_status === 'healthy' ? 'good' : 
                           ha.ha_status === 'degraded' ? 'warning' : 
                           ha.ha_status === 'none' ? 'neutral' : 'critical';
        const statusIcon = ha.ha_status === 'healthy' ? '🛡️' : 
                          ha.ha_status === 'degraded' ? '⚠️' : 
                          ha.ha_status === 'none' ? '⊘' : '🚨';
        html += `
            <div class="assessment-card ${statusClass}">
                <div class="assessment-icon">${statusIcon}</div>
                <div class="assessment-content">
                    <h4>High Availability & DR</h4>
                    <div class="assessment-status ${statusClass}">${ha.ha_status?.toUpperCase() || 'Unknown'}</div>
                    <p><strong>HA Configured:</strong> ${ha.ha_configured ? 'Yes ✓' : 'No ✗'}</p>
                    <p><strong>Quorum:</strong> ${ha.quorum_status || 'N/A'}</p>
                    <p><strong>Replication:</strong> ${ha.replication_health || 'N/A'}</p>
                    <p><strong>Failover Ready:</strong> ${ha.failover_ready ? 'Yes ✓' : 'No ✗'}</p>
                    <p class="assessment-details">${ha.details || ''}</p>
                </div>
            </div>`;
    }
    
    // Workload Assessment Card
    if (hasWorkload) {
        const wl = results.workload_assessment;
        html += `
            <div class="assessment-card neutral">
                <div class="assessment-icon">📊</div>
                <div class="assessment-content">
                    <h4>Workload Profile</h4>
                    <div class="assessment-status">${wl.workload_type?.toUpperCase() || 'Unknown'}</div>
                    <p><strong>Total QPS:</strong> ${wl.total_qps || 'N/A'}</p>
                    <p><strong>Read/Write Ratio:</strong> ${wl.read_write_ratio || 'N/A'}</p>
                    <p><strong>Reads/sec:</strong> ${wl.reads_per_sec || 'N/A'}</p>
                    <p><strong>Writes/sec:</strong> ${wl.writes_per_sec || 'N/A'}</p>
                    <p><strong>Connection Util:</strong> ${wl.connection_utilization || 'N/A'}</p>
                </div>
            </div>`;
    }
    
    // Bottlenecks Card
    if (hasBottlenecks) {
        const bottlenecks = results.bottlenecks;
        const hasCritical = bottlenecks.some(b => b.severity === 'critical');
        const statusClass = hasCritical ? 'critical' : 'warning';
        html += `
            <div class="assessment-card ${statusClass}">
                <div class="assessment-icon">🔍</div>
                <div class="assessment-content">
                    <h4>Bottlenecks Detected</h4>
                    <div class="assessment-status ${statusClass}">${bottlenecks.length} FOUND</div>
                    <ul class="bottleneck-list">`;
        for (const b of bottlenecks) {
            // Support both old format (area/metric/value) and new format (node/resource/current_value/impact)
            const location = b.node || b.area || 'Unknown';
            const resource = b.resource || b.metric || 'Unknown';
            const value = b.current_value || b.value || '';
            // Truncate impact to first sentence only (complete sentence)
            let impact = b.impact || '';
            if (impact) {
                // Get first complete sentence
                const sentenceMatch = impact.match(/^[^.!?]+[.!?]/);
                if (sentenceMatch) {
                    impact = sentenceMatch[0];
                } else if (impact.length > 80) {
                    // No sentence ending found, truncate at word boundary
                    impact = impact.substring(0, 80).replace(/\s+\S*$/, '') + '...';
                }
            }
            html += `<li class="${b.severity || 'warning'}"><strong>${location}</strong> (${resource})${value ? ': ' + value : ''}${impact ? ' - ' + impact : ''}</li>`;
        }
        html += `</ul>
                </div>
            </div>`;
    }
    
    html += '</div>';
    assessmentGrid.innerHTML = html;
}

// Display Query Throughput and Connection Stats
function displayQueryStats(clusterData) {
    const metricsGrid = document.getElementById('metricsGrid');
    if (!metricsGrid) return;
    
    const isNodeAnalysis = clusterData.analysis_type === 'node' && clusterData.nodes.length === 1;
    
    let totalQPS = 0, totalReads = 0, totalWrites = 0;
    let totalConnections = 0, maxConnections = 0, maxUsedConnections = 0;
    let hasQPSData = false, hasConnData = false;
    
    for (const node of clusterData.nodes) {
        const status = node.global_status || {};
        const vars = node.global_variables || {};
        
        // Calculate QPS from Questions and Uptime
        const questions = parseInt(status.Questions) || 0;
        const uptime = parseInt(status.Uptime) || 1;
        if (questions > 0) {
            hasQPSData = true;
            const nodeQPS = questions / uptime;
            totalQPS += nodeQPS;
            
            // Read/Write breakdown
            const selects = parseInt(status.Com_select) || 0;
            const inserts = parseInt(status.Com_insert) || 0;
            const updates = parseInt(status.Com_update) || 0;
            const deletes = parseInt(status.Com_delete) || 0;
            
            totalReads += selects / uptime;
            totalWrites += (inserts + updates + deletes) / uptime;
        }
        
        // Connection stats
        const connected = parseInt(status.Threads_connected) || 0;
        const maxConn = parseInt(vars.max_connections) || 0;
        const maxUsed = parseInt(status.Max_used_connections) || 0;
        
        if (maxConn > 0) {
            hasConnData = true;
            totalConnections += connected;
            maxConnections += maxConn;
            maxUsedConnections = Math.max(maxUsedConnections, maxUsed);
        }
    }
    
    let statsHtml = '<div class="query-stats-summary">';
    statsHtml += `<h4>${isNodeAnalysis ? 'Node' : 'Database'} Workload Metrics</h4>`;
    statsHtml += '<div class="stats-grid">';
    
    // QPS Stats
    if (hasQPSData) {
        statsHtml += `
            <div class="stat-box">
                <span class="stat-label">Total QPS</span>
                <span class="stat-value">${totalQPS.toFixed(1)}</span>
            </div>
            <div class="stat-box">
                <span class="stat-label">Reads/sec</span>
                <span class="stat-value">${totalReads.toFixed(1)}</span>
            </div>
            <div class="stat-box">
                <span class="stat-label">Writes/sec</span>
                <span class="stat-value">${totalWrites.toFixed(1)}</span>
            </div>
        `;
    } else {
        statsHtml += `
            <div class="stat-box stat-unavailable">
                <span class="stat-label">Query Throughput</span>
                <span class="stat-value">Data not available</span>
                <span class="stat-note">Requires: Questions, Uptime, Com_select, Com_insert, Com_update, Com_delete from GLOBAL STATUS</span>
            </div>
        `;
    }
    
    // Connection Stats
    if (hasConnData) {
        const connUsage = maxConnections > 0 ? ((totalConnections / maxConnections) * 100).toFixed(1) : 0;
        statsHtml += `
            <div class="stat-box">
                <span class="stat-label">Active Connections</span>
                <span class="stat-value">${totalConnections} / ${maxConnections}</span>
                <span class="stat-note">${connUsage}% usage</span>
            </div>
            <div class="stat-box">
                <span class="stat-label">Peak Connections</span>
                <span class="stat-value">${maxUsedConnections}</span>
            </div>
        `;
    } else {
        statsHtml += `
            <div class="stat-box stat-unavailable">
                <span class="stat-label">Connection Stats</span>
                <span class="stat-value">Data not available</span>
                <span class="stat-note">Requires: Threads_connected, max_connections, Max_used_connections</span>
            </div>
        `;
    }
    
    statsHtml += '</div></div>';
    
    // Insert before the metrics grid content
    metricsGrid.insertAdjacentHTML('beforebegin', statsHtml);
}

// Display analysis sources/references with actual links
function displayAnalysisSources(ragMetadata) {
    const sourcesDiv = document.getElementById('analysisSources');
    if (!sourcesDiv) return;
    
    // MariaDB documentation reference links
    const docLinks = {
        'galera': [
            { title: 'Galera Cluster Overview', url: 'https://mariadb.com/kb/en/galera-cluster/' },
            { title: 'Galera Cluster System Variables', url: 'https://mariadb.com/kb/en/galera-cluster-system-variables/' },
            { title: 'Galera Cluster Status Variables', url: 'https://mariadb.com/kb/en/galera-cluster-status-variables/' }
        ],
        'replication': [
            { title: 'Replication Overview', url: 'https://mariadb.com/kb/en/replication-overview/' },
            { title: 'Setting Up Replication', url: 'https://mariadb.com/kb/en/setting-up-replication/' }
        ],
        'general': [
            { title: 'InnoDB Buffer Pool', url: 'https://mariadb.com/kb/en/innodb-buffer-pool/' },
            { title: 'Server System Variables', url: 'https://mariadb.com/kb/en/server-system-variables/' },
            { title: 'Server Status Variables', url: 'https://mariadb.com/kb/en/server-status-variables/' },
            { title: 'Optimization and Tuning', url: 'https://mariadb.com/kb/en/optimization-and-tuning/' }
        ]
    };
    
    let html = '<div class="sources-info">';
    
    // Get topology type from analysis data
    const topology = analysisData?.[0]?.topology_type?.toLowerCase() || 'standalone';
    
    // Show documentation reference links
    html += '<div class="sources-section"><h4>MariaDB Documentation References</h4><ul class="sources-list">';
    
    // Add topology-specific links
    if (docLinks[topology]) {
        docLinks[topology].forEach(link => {
            html += `<li><a href="${link.url}" target="_blank" class="ref-link"><span class="source-icon">📘</span> ${link.title}</a></li>`;
        });
    }
    
    // Add general links
    docLinks.general.forEach(link => {
        html += `<li><a href="${link.url}" target="_blank" class="ref-link"><span class="source-icon">📘</span> ${link.title}</a></li>`;
    });
    
    html += '</ul></div>';
    
    // Show RAG context if available
    if (ragMetadata && ragMetadata.context_retrieved) {
        const sources = ragMetadata.context_sources || [];
        if (sources.length > 0) {
            html += '<div class="sources-section"><h4>Knowledge Base Sources Used</h4><ul class="sources-list">';
            sources.forEach(source => {
                html += `<li><span class="source-icon">📄</span> ${escapeHtml(source)}</li>`;
            });
            html += '</ul></div>';
        }
    }
    
    html += '<p class="sources-note">Analysis powered by MariaDB Cloud Vector Store (RAG) + Google Gemini AI</p>';
    html += '</div>';
    
    sourcesDiv.innerHTML = html;
}

// Filter out cluster-level findings for individual node analysis
function filterNodeAnalysisFindings(findings) {
    if (!findings || !Array.isArray(findings)) return findings;
    
    // Keywords that indicate cluster-level findings (not applicable to single node)
    const clusterKeywords = [
        'cluster consists of',
        'cluster requires',
        'minimum of',
        'nodes for fault tolerance',
        'quorum',
        'cluster size',
        'number of nodes',
        'add more nodes',
        'single node cluster',
        'standalone cluster'
    ];
    
    return findings.filter(finding => {
        const text = (finding.title + ' ' + finding.description).toLowerCase();
        return !clusterKeywords.some(keyword => text.includes(keyword.toLowerCase()));
    });
}

// Display local analysis when API is unavailable
function displayLocalAnalysis(clusterData) {
    const score = calculateLocalScore(clusterData);
    const healthBadge = document.getElementById('healthBadge');
    
    if (score >= 80) {
        healthBadge.textContent = 'Healthy';
        healthBadge.className = 'health-badge status-good';
    } else if (score >= 60) {
        healthBadge.textContent = 'Needs Attention';
        healthBadge.className = 'health-badge status-average';
    } else {
        healthBadge.textContent = 'Critical';
        healthBadge.className = 'health-badge status-critical';
    }
    
    document.getElementById('healthSummary').textContent = 
        `Local analysis of ${clusterData.cluster_name} (${clusterData.topology_type}) with ${clusterData.nodes.length} node(s).`;
    
    // Query throughput and connection stats (displayed before findings)
    displayQueryStats(clusterData);
    
    // Node details (moved up)
    displayNodes(clusterData.nodes);
    
    // Filter findings for node analysis
    const isNodeAnalysis = clusterData.analysis_type === 'node';
    let findings = generateLocalFindings(clusterData);
    if (isNodeAnalysis) {
        findings = filterNodeAnalysisFindings(findings);
    }
    displayFindings(findings);
    
    displayRecommendations(generateLocalRecommendations(clusterData));
    displayAnalysisSources(null);
}

// Calculate local health score
function calculateLocalScore(clusterData) {
    let score = 100;
    
    for (const node of clusterData.nodes) {
        const status = node.global_status || {};
        const vars = node.global_variables || {};
        const resources = node.system_resources || {};
        
        // Check buffer pool hit ratio
        const requests = parseInt(status.Innodb_buffer_pool_read_requests) || 0;
        const reads = parseInt(status.Innodb_buffer_pool_reads) || 0;
        if (requests > 0) {
            const hitRatio = ((requests - reads) / requests) * 100;
            if (hitRatio < 99) score -= 10;
            if (hitRatio < 95) score -= 10;
        }
        
        // Check connection usage
        const maxConn = parseInt(vars.max_connections) || 500;
        const connected = parseInt(status.Threads_connected) || 0;
        const connUsage = (connected / maxConn) * 100;
        if (connUsage > 80) score -= 15;
        else if (connUsage > 60) score -= 5;
        
        // Check Galera status
        if (status.wsrep_ready === 'OFF') score -= 30;
        if (status.wsrep_local_state_comment !== 'Synced') score -= 20;
    }
    
    return Math.max(0, Math.min(100, score));
}

// Display resource utilization summary (concise)
function displayMetrics(clusterData) {
    const metricsGrid = document.getElementById('metricsGrid');
    if (!metricsGrid) return;
    
    const isNodeAnalysis = clusterData.analysis_type === 'node' && clusterData.nodes.length === 1;
    
    let html = '<div class="resource-summary">';
    html += '<h4>Resource Utilization Summary</h4>';
    html += '<div class="resource-grid">';
    
    for (const node of clusterData.nodes) {
        const status = node.global_status || {};
        const vars = node.global_variables || {};
        const resources = node.system_resources || {};
        
        html += `<div class="resource-node">`;
        if (!isNodeAnalysis) {
            html += `<div class="node-name">${node.hostname}</div>`;
        }
        
        // CPU Analysis
        const cpuCores = resources.cpu_cores;
        const threadsRunning = parseInt(status.Threads_running) || 0;
        
        if (cpuCores) {
            const cpuUsageEstimate = ((threadsRunning / cpuCores) * 100).toFixed(0);
            html += `
                <div class="resource-item">
                    <span class="resource-label">CPU</span>
                    <span class="resource-value">${threadsRunning} active threads / ${cpuCores} cores</span>
                    <span class="resource-note">~${cpuUsageEstimate}% estimated utilization</span>
                </div>
            `;
        } else {
            html += `
                <div class="resource-item unavailable">
                    <span class="resource-label">CPU</span>
                    <span class="resource-value">Data not available</span>
                    <span class="resource-note">Add cpu_cores to system resources</span>
                </div>
            `;
        }
        
        // RAM Analysis
        const ramGB = resources.ram_gb;
        const bufferPoolSize = parseInt(vars.innodb_buffer_pool_size) || 0;
        const bufferPoolGB = (bufferPoolSize / (1024 * 1024 * 1024)).toFixed(1);
        
        if (ramGB) {
            const ramUsage = ((bufferPoolGB / ramGB) * 100).toFixed(0);
            html += `
                <div class="resource-item">
                    <span class="resource-label">Memory</span>
                    <span class="resource-value">Buffer Pool: ${bufferPoolGB} GB / ${ramGB} GB RAM</span>
                    <span class="resource-note">${ramUsage}% allocated to buffer pool</span>
                </div>
            `;
        } else {
            html += `
                <div class="resource-item unavailable">
                    <span class="resource-label">Memory</span>
                    <span class="resource-value">Data not available</span>
                    <span class="resource-note">Add ram_gb to system resources</span>
                </div>
            `;
        }
        
        // Storage Analysis
        const diskTotalGB = resources.disk_total_gb;
        // Note: Data directory size would need to be collected separately
        
        if (diskTotalGB) {
            html += `
                <div class="resource-item">
                    <span class="resource-label">Storage</span>
                    <span class="resource-value">Capacity: ${diskTotalGB} GB (${resources.storage_type || 'unknown'})</span>
                    <span class="resource-note">Data dir/schema size: Not available - collect via OS/SQL</span>
                </div>
            `;
        } else {
            html += `
                <div class="resource-item unavailable">
                    <span class="resource-label">Storage</span>
                    <span class="resource-value">Data not available</span>
                    <span class="resource-note">Add disk_total_gb to system resources; collect data dir size via: du -sh /var/lib/mysql</span>
                </div>
            `;
        }
        
        html += '</div>';
    }
    
    html += '</div></div>';
    metricsGrid.innerHTML = html;
}

// Generate user-friendly findings
function generateLocalFindings(clusterData) {
    const findings = [];
    
    for (const node of clusterData.nodes) {
        const status = node.global_status || {};
        const vars = node.global_variables || {};
        const resources = node.system_resources || {};
        
        // CPU Analysis
        if (resources.cpu_cores) {
            const running = parseInt(status.Threads_running) || 0;
            const cpuUsage = (running / resources.cpu_cores) * 100;
            
            if (cpuUsage < 20) {
                findings.push({
                    severity: 'info',
                    title: 'CPU cores may be over-provisioned',
                    description: `${node.hostname} is using only ${cpuUsage.toFixed(0)}% of its ${resources.cpu_cores} CPU cores. You might be able to reduce costs by using a smaller instance.`
                });
            } else if (cpuUsage > 80) {
                findings.push({
                    severity: 'warning',
                    title: 'High CPU utilization detected',
                    description: `${node.hostname} is running at ${cpuUsage.toFixed(0)}% CPU capacity. Consider upgrading to more CPU cores or optimizing queries.`
                });
            }
        }
        
        // RAM Analysis
        if (resources.ram_gb) {
            const bufferPool = parseInt(vars.innodb_buffer_pool_size) || 0;
            const bufferPoolGB = bufferPool / (1024 * 1024 * 1024);
            const ramUsage = (bufferPoolGB / resources.ram_gb) * 100;
            
            if (ramUsage < 50) {
                findings.push({
                    severity: 'info',
                    title: 'Memory allocation could be optimized',
                    description: `${node.hostname} has ${resources.ram_gb}GB RAM but buffer pool is only ${bufferPoolGB.toFixed(1)}GB (${ramUsage.toFixed(0)}%). Consider increasing buffer pool or downsizing instance.`
                });
            } else if (ramUsage > 85) {
                findings.push({
                    severity: 'warning',
                    title: 'Memory usage is high',
                    description: `${node.hostname} buffer pool uses ${ramUsage.toFixed(0)}% of available RAM. This leaves limited memory for OS and other processes.`
                });
            }
        }
        
        // Buffer Pool Hit Ratio
        const requests = parseInt(status.Innodb_buffer_pool_read_requests) || 0;
        const reads = parseInt(status.Innodb_buffer_pool_reads) || 0;
        if (requests > 0) {
            const hitRatio = ((requests - reads) / requests) * 100;
            if (hitRatio < 99) {
                findings.push({
                    severity: hitRatio < 95 ? 'critical' : 'warning',
                    title: 'Database is reading from disk too often',
                    description: `${node.hostname} buffer pool hit ratio is ${hitRatio.toFixed(2)}%. This means ${(100 - hitRatio).toFixed(2)}% of data requests require disk I/O, which slows performance. Increase buffer pool size.`
                });
            }
        }
        
        // Connection Usage
        const maxConn = parseInt(vars.max_connections) || 500;
        const connected = parseInt(status.Threads_connected) || 0;
        const connUsage = (connected / maxConn) * 100;
        
        if (connUsage > 80) {
            findings.push({
                severity: 'critical',
                title: 'Running low on available connections',
                description: `${node.hostname} is using ${connected} of ${maxConn} connections (${connUsage.toFixed(0)}%). Your application may experience connection errors. Increase max_connections or use connection pooling.`
            });
        } else if (connUsage < 10 && maxConn > 200) {
            findings.push({
                severity: 'info',
                title: 'Connection limit may be unnecessarily high',
                description: `${node.hostname} has ${maxConn} max connections but only ${connected} are in use. Each idle connection uses memory. Consider reducing max_connections.`
            });
        }
        
        // Galera specific
        if (status.wsrep_ready === 'OFF') {
            findings.push({
                severity: 'critical',
                title: 'Galera node is not ready',
                description: `${node.hostname} shows wsrep_ready=OFF. This node cannot process transactions. Check cluster connectivity and Galera status.`
            });
        }
        
        if (status.wsrep_local_state_comment && status.wsrep_local_state_comment !== 'Synced') {
            findings.push({
                severity: 'warning',
                title: 'Node is not fully synchronized',
                description: `${node.hostname} state is "${status.wsrep_local_state_comment}" instead of "Synced". Data may be inconsistent with other cluster nodes.`
            });
        }
    }
    
    // If no issues found
    if (findings.length === 0) {
        findings.push({
            severity: 'info',
            title: 'No significant issues detected',
            description: 'Your database configuration appears healthy based on the provided metrics.'
        });
    }
    
    return findings;
}

// Generate recommendations
function generateLocalRecommendations(clusterData) {
    const recommendations = [];
    
    for (const node of clusterData.nodes) {
        const status = node.global_status || {};
        const vars = node.global_variables || {};
        const resources = node.system_resources || {};
        
        // CPU recommendation
        if (resources.cpu_cores) {
            const running = parseInt(status.Threads_running) || 0;
            const cpuUsage = (running / resources.cpu_cores) * 100;
            
            if (cpuUsage < 20) {
                recommendations.push(`Consider reducing CPU cores from ${resources.cpu_cores} to ${Math.max(2, Math.ceil(resources.cpu_cores / 2))} to optimize costs.`);
            } else if (cpuUsage > 80) {
                recommendations.push(`Upgrade ${node.hostname} to at least ${resources.cpu_cores * 2} CPU cores to handle current workload.`);
            }
        }
        
        // RAM recommendation
        if (resources.ram_gb) {
            const bufferPool = parseInt(vars.innodb_buffer_pool_size) || 0;
            const bufferPoolGB = bufferPool / (1024 * 1024 * 1024);
            const optimalBufferPool = resources.ram_gb * 0.7;
            
            if (bufferPoolGB < optimalBufferPool * 0.5) {
                recommendations.push(`Increase innodb_buffer_pool_size to ${optimalBufferPool.toFixed(0)}GB (70% of RAM) for better performance.`);
            }
        }
        
        // Buffer pool hit ratio
        const requests = parseInt(status.Innodb_buffer_pool_read_requests) || 0;
        const reads = parseInt(status.Innodb_buffer_pool_reads) || 0;
        if (requests > 0) {
            const hitRatio = ((requests - reads) / requests) * 100;
            if (hitRatio < 99) {
                recommendations.push('Increase buffer pool size to improve cache hit ratio and reduce disk I/O.');
            }
        }
    }
    
    // General recommendations
    if (clusterData.topology_type === 'galera' && clusterData.nodes.length < 3) {
        recommendations.push('For high availability, Galera clusters should have at least 3 nodes to maintain quorum.');
    }
    
    if (recommendations.length === 0) {
        recommendations.push('Continue monitoring performance metrics and maintain regular backup schedules.');
    }
    
    return recommendations;
}

// Display findings with user-friendly language
function displayFindings(findings) {
    const container = document.getElementById('findingsList');
    const countsEl = document.getElementById('findingCounts');
    
    // Normalize findings to handle both AI format and local format
    const normalizedFindings = findings.map(f => ({
        severity: f.severity || 'info',
        title: f.title || f.finding || f.category || 'Finding',
        description: f.description || f.recommendation || ''
    }));
    
    const counts = { critical: 0, warning: 0, info: 0 };
    normalizedFindings.forEach(f => {
        if (counts[f.severity] !== undefined) counts[f.severity]++;
    });
    
    countsEl.innerHTML = `
        ${counts.critical > 0 ? `<span class="finding-count critical">${counts.critical} Critical</span>` : ''}
        ${counts.warning > 0 ? `<span class="finding-count warning">${counts.warning} Warning</span>` : ''}
        ${counts.info > 0 ? `<span class="finding-count info">${counts.info} Info</span>` : ''}
    `;
    
    const icons = { critical: '🔴', warning: '🟡', info: '🔵' };
    
    container.innerHTML = normalizedFindings.map(f => `
        <div class="finding-item ${f.severity}">
            <span class="finding-icon">${icons[f.severity] || '🔵'}</span>
            <div class="finding-content">
                <div class="finding-title">${formatMarkdown(f.title)}</div>
                ${f.description ? `<div class="finding-description">${formatMarkdown(f.description)}</div>` : ''}
            </div>
        </div>
    `).join('');
}

// Display recommendations
function displayRecommendations(recommendations) {
    const container = document.getElementById('recommendationsList');
    
    container.innerHTML = recommendations.map((rec, i) => `
        <div class="recommendation-item">
            <span class="recommendation-number">${i + 1}</span>
            <span class="recommendation-text">${formatRecommendation(rec)}</span>
        </div>
    `).join('');
}

// Display node details with comprehensive metrics
function displayNodes(nodes) {
    const container = document.getElementById('nodesGrid');
    
    container.innerHTML = nodes.map(node => {
        const status = node.global_status || {};
        const vars = node.global_variables || {};
        const resources = node.system_resources || {};
        
        // Uptime
        const uptime = parseInt(status.Uptime) || 0;
        const uptimeDays = Math.floor(uptime / 86400);
        const uptimeHours = Math.floor((uptime % 86400) / 3600);
        
        // QPS Calculations
        const questions = parseInt(status.Questions) || 0;
        const qps = uptime > 0 ? (questions / uptime).toFixed(1) : '0';
        
        // Read/Write breakdown
        const comSelect = parseInt(status.Com_select) || 0;
        const comInsert = parseInt(status.Com_insert) || 0;
        const comUpdate = parseInt(status.Com_update) || 0;
        const comDelete = parseInt(status.Com_delete) || 0;
        const reads = comSelect;
        const writes = comInsert + comUpdate + comDelete;
        const readsPerSec = uptime > 0 ? (reads / uptime).toFixed(1) : '0';
        const writesPerSec = uptime > 0 ? (writes / uptime).toFixed(1) : '0';
        
        // System Resources
        const cpuCores = resources.cpu_cores || 0;
        const ramGb = resources.ram_gb || 0;
        const threadsRunning = parseInt(status.Threads_running) || 0;
        
        // Buffer Pool (not RAM usage - it's allocation)
        const bufferPoolSize = parseInt(vars.innodb_buffer_pool_size) || 0;
        const bufferPoolGb = bufferPoolSize / (1024 * 1024 * 1024);
        const bufferPoolPct = ramGb > 0 ? Math.round((bufferPoolGb / ramGb) * 100) : 0;
        
        // Connection Usage (this is real data from SHOW STATUS)
        const maxConn = parseInt(vars.max_connections) || 500;
        const connected = parseInt(status.Threads_connected) || 0;
        const connUsage = Math.round((connected / maxConn) * 100);
        const connStatus = connUsage < 50 ? 'low' : connUsage < 80 ? 'medium' : 'high';
        
        return `
            <div class="node-detail-card">
                <div class="node-detail-header">
                    <span class="node-detail-name">${escapeHtml(node.hostname)}</span>
                    <span class="node-detail-role">${node.role}</span>
                </div>
                
                <div class="node-section">
                    <div class="node-section-title">Query Throughput</div>
                    <div class="node-metrics-grid">
                        <div class="metric-box">
                            <span class="metric-label">Total QPS</span>
                            <span class="metric-val">${qps}</span>
                        </div>
                        <div class="metric-box">
                            <span class="metric-label">Reads/sec</span>
                            <span class="metric-val">${readsPerSec}</span>
                        </div>
                        <div class="metric-box">
                            <span class="metric-label">Writes/sec</span>
                            <span class="metric-val">${writesPerSec}</span>
                        </div>
                    </div>
                </div>
                
                <div class="node-section">
                    <div class="node-section-title">Connections</div>
                    <div class="node-metrics-grid">
                        <div class="metric-box">
                            <span class="metric-label">Connected</span>
                            <span class="metric-val">${connected}</span>
                        </div>
                        <div class="metric-box">
                            <span class="metric-label">Max Allowed</span>
                            <span class="metric-val">${maxConn}</span>
                        </div>
                        <div class="metric-box">
                            <span class="metric-label">Usage</span>
                            <span class="metric-val ${connStatus}">${connUsage}%</span>
                        </div>
                    </div>
                </div>
                
                <div class="node-footer">
                    <span>Uptime: ${uptimeDays}d ${uptimeHours}h</span>
                </div>
            </div>
        `;
    }).join('');
}

// Chat functions
async function sendChat() {
    const input = document.getElementById('chatInput');
    const question = input.value.trim();
    
    if (!question) return;
    
    addChatMessage('user', question);
    input.value = '';
    
    try {
        const response = await fetch(`${API_BASE}/api/v1/ai/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                cluster_context: analysisData[0],
                chat_history: chatHistory.slice(-5)
            })
        });
        
        const result = await response.json();
        chatHistory.push({ role: 'user', content: question });
        chatHistory.push({ role: 'assistant', content: result.answer });
        addChatMessage('assistant', result.answer);
    } catch (error) {
        addChatMessage('assistant', 'Sorry, I could not process your question. Please check the API connection.');
    }
}

function addChatMessage(role, content) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    // Use formatMarkdown for assistant responses, escapeHtml for user messages
    const formattedContent = role === 'assistant' ? formatMarkdown(content) : escapeHtml(content);
    div.innerHTML = `<div class="message-content">${formattedContent}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function handleChatKeypress(event) {
    if (event.key === 'Enter') {
        sendChat();
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Convert markdown to HTML (after escaping)
function formatMarkdown(text) {
    if (!text) return '';
    
    // First escape HTML for security
    let html = escapeHtml(text);
    
    // Convert markdown formatting
    // Bold: **text** or __text__
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
    
    // Italic: *text* (skip _text_ to preserve parameter names like innodb_buffer_pool_size)
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    // Note: We don't convert _text_ to italic to avoid breaking variable names with underscores
    
    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    
    // Lists: lines starting with - or *
    html = html.replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // Numbered lists: lines starting with 1. 2. etc
    html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');
    
    return html;
}

// Format summary as bullet points
function formatSummaryAsBullets(text) {
    if (!text) return '';
    
    // Split by periods, semicolons, or existing line breaks
    let sentences = text
        .replace(/\.\s+/g, '.|')  // Mark sentence endings
        .replace(/;\s*/g, ';|')   // Mark semicolon separations
        .replace(/\n/g, '|')      // Mark line breaks
        .split('|')
        .map(s => s.trim())
        .filter(s => s.length > 0);
    
    // If only one sentence, just return it formatted
    if (sentences.length <= 1) {
        return `<p>${escapeHtml(text)}</p>`;
    }
    
    // Create bullet list
    let html = '<ul class="summary-bullets">';
    for (const sentence of sentences) {
        // Clean up trailing periods for consistency
        const cleanSentence = sentence.replace(/\.+$/, '').trim();
        if (cleanSentence) {
            html += `<li>${escapeHtml(cleanSentence)}</li>`;
        }
    }
    html += '</ul>';
    return html;
}

// Format recommendation without converting underscores to italic
function formatRecommendation(text) {
    if (!text) return '';
    
    let html = escapeHtml(text);
    
    // Bold: **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Remove any leading bullet/dash that AI might have included
    html = html.replace(/^[-•]\s*/, '');
    html = html.replace(/^\d+\.\s*/, '');
    
    return html;
}

function showLoading(show, message) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        if (show) {
            overlay.classList.add('active');
            if (message) updateLoadingText(message);
        } else {
            overlay.classList.remove('active');
        }
    }
}
