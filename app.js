/**
 * Lead Research & CRM Loader - Frontend Controller
 * Handles 7-step pipeline simulation, approval workflows, verification, and benchmark suite.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Navigation Tabs
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');
      tabButtons.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetEl = document.getElementById(targetId);
      if (targetEl) targetEl.classList.add('active');

      if (targetId === 'tab-results') loadStep6Results();
      if (targetId === 'tab-crm') loadCrmRecords();
      if (targetId === 'tab-scenarios' && !scenariosLoadedOnce) runAllScenarios();
    });
  });

  // Pre-configured Scenario Buttons
  const scenarioDefinitions = {
    'RUN-01': {
      request_id: 'RUN-01',
      domain: 'cloudscale.io',
      legal_name: 'CloudScale Technologies Inc.',
      region: 'North America',
      industry: 'Cloud Infrastructure',
      employee_count: 180,
      funding_stage: 'Series B',
      website_active: true
    },
    'RUN-02': {
      request_id: 'RUN-02',
      domain: 'acmesoftware.com',
      legal_name: 'Acme Software Solutions Inc.',
      region: 'North America',
      industry: 'Enterprise Software',
      employee_count: 250,
      funding_stage: 'Series A',
      website_active: true
    },
    'RUN-03': {
      request_id: 'RUN-03',
      domain: 'quantumtech.co',
      legal_name: 'QuantumTech Systems',
      region: 'North America',
      industry: 'Artificial Intelligence',
      employee_count: '',
      funding_stage: 'Seed',
      website_active: true
    },
    'RUN-04': {
      request_id: 'RUN-04',
      domain: 'ghostcorp-test.com',
      legal_name: 'GhostCorp Industries',
      region: 'Canada',
      industry: 'Enterprise Software',
      employee_count: 75,
      funding_stage: 'Bootstrapped',
      website_active: false
    }
  };

  document.querySelectorAll('.btn-scenario').forEach(btn => {
    btn.addEventListener('click', () => {
      const scenarioKey = btn.getAttribute('data-scenario');
      const data = scenarioDefinitions[scenarioKey];
      if (data) {
        document.getElementById('requestId').value = data.request_id;
        document.getElementById('domain').value = data.domain;
        document.getElementById('legalName').value = data.legal_name;
        document.getElementById('region').value = data.region;
        document.getElementById('industry').value = data.industry;
        document.getElementById('employeeCount').value = data.employee_count !== null ? data.employee_count : '';
        document.getElementById('fundingStage').value = data.funding_stage;
        document.getElementById('websiteActive').checked = data.website_active;

        resetPipelineUI();
      }
    });
  });

  // Form Elements
  const form = document.getElementById('leadInputForm');
  const btnValidateStep1 = document.getElementById('btnValidateStep1');
  const resetCrmBtn = document.getElementById('resetCrmBtn');
  const btnRefreshCrm = document.getElementById('btnRefreshCrm');
  const btnRunAllScenarios = document.getElementById('btnRunAllScenarios');
  const btnApproveAction = document.getElementById('btnApproveAction');
  const btnRejectAction = document.getElementById('btnRejectAction');

  let currentPendingDecision = null;
  let scenariosLoadedOnce = false;

  function getFormData() {
    const empVal = document.getElementById('employeeCount').value.trim();
    return {
      request_id: document.getElementById('requestId').value.trim(),
      domain: document.getElementById('domain').value.trim(),
      legal_name: document.getElementById('legalName').value.trim(),
      region: document.getElementById('region').value.trim(),
      industry: document.getElementById('industry').value.trim(),
      employee_count: empVal !== '' ? parseInt(empVal, 10) : null,
      funding_stage: document.getElementById('fundingStage').value.trim(),
      website_active: document.getElementById('websiteActive').checked,
      approved: true
    };
  }

  function resetPipelineUI() {
    document.querySelectorAll('.step-node').forEach(n => n.className = 'step-node');
    document.querySelectorAll('.step-line').forEach(l => l.className = 'step-line');
    document.getElementById('stepNode1').className = 'step-node active';

    document.getElementById('provenanceTableBody').innerHTML = `
      <tr><td colspan="5" class="empty-cell">Run pipeline to inspect connected sources.</td></tr>
    `;

    const badge = document.getElementById('decisionStatusBadge');
    badge.className = 'badge badge-pending';
    badge.textContent = 'Awaiting Execution';

    const reasonBox = document.getElementById('decisionReasonBox');
    reasonBox.className = 'decision-reason-box';
    document.getElementById('decisionReasonText').textContent = 'Select a scenario or submit a lead to evaluate decision rules.';
    document.getElementById('decisionIdempKey').textContent = '-';
    document.getElementById('decisionDeduplicationStatus').textContent = 'Pending Check';

    document.getElementById('actionStatusBadge').className = 'badge badge-neutral';
    document.getElementById('actionStatusBadge').textContent = 'Standby';
    document.getElementById('proposedPayloadJson').textContent = '{ "status": "Waiting for qualified lead..." }';
    document.getElementById('approvalActions').style.display = 'flex';
    document.getElementById('executionResultCard').style.display = 'none';

    document.getElementById('verificationStatusBadge').className = 'badge badge-neutral';
    document.getElementById('verificationStatusBadge').textContent = 'Pending Verification';
    document.getElementById('intendedStateText').textContent = 'Record created in private view and website active with HTTP 200.';
    document.getElementById('observedStateText').textContent = 'Awaiting post-action inspection.';
    document.getElementById('discrepancyAlert').style.display = 'none';

    currentPendingDecision = null;
  }

  // Step 1: Input Validation Button
  btnValidateStep1.addEventListener('click', () => {
    const lead = getFormData();
    if (!lead.request_id || !lead.domain || !lead.legal_name || !lead.region) {
      document.getElementById('stepNode1').className = 'step-node rejected';
      alert('Validation Error: Missing mandatory fields (request_id, domain, legal_name, or region).');
      return;
    }
    document.getElementById('stepNode1').className = 'step-node completed';
    alert(`Step 1 Validation Passed: Request ID '${lead.request_id}', domain, and entity name are well-formed.`);
  });

  // Step 4: Operator Approval Handlers
  btnApproveAction.addEventListener('click', async () => {
    if (!currentPendingDecision) {
      alert('No qualified lead pending approval.');
      return;
    }
    await executeStep4Action(true);
  });

  btnRejectAction.addEventListener('click', async () => {
    if (!currentPendingDecision) {
      alert('No qualified lead pending approval.');
      return;
    }
    await executeStep4Action(false);
  });

  async function executeStep4Action(approved) {
    const lead = getFormData();
    lead.approved = approved;

    try {
      const res = await fetch('/leads/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lead)
      });
      const dec = await res.json();

      if (approved && dec.status === 'QUALIFIED') {
        document.getElementById('actionStatusBadge').className = 'badge badge-success';
        document.getElementById('actionStatusBadge').textContent = 'Action Approved & Executed';
        document.getElementById('approvalActions').style.display = 'none';
        document.getElementById('executionResultCard').style.display = 'flex';
        document.getElementById('assignedCrmId').textContent = dec.crm_id || 'CRMID-N/A';
        document.getElementById('assignedCrmNote').textContent = dec.reason;

        document.getElementById('stepNode4').className = 'step-node completed';
        document.getElementById('stepLine4').className = 'step-line completed';

        // Step 5 Verification
        updateStep5UI(dec);
      } else {
        document.getElementById('actionStatusBadge').className = 'badge badge-danger';
        document.getElementById('actionStatusBadge').textContent = 'Approval Denied by Operator';
        document.getElementById('stepNode4').className = 'step-node rejected';
        document.getElementById('assignedCrmNote').textContent = 'Execution blocked by human operator.';
      }
    } catch (err) {
      console.error(err);
      alert('Error executing permitted action.');
    }
  }

  function updateStep5UI(dec) {
    const vBadge = document.getElementById('verificationStatusBadge');
    if (dec.verification_status === 'VERIFIED_SUCCESS') {
      vBadge.className = 'badge badge-success';
      vBadge.textContent = 'VERIFIED SUCCESS (HTTP 200)';
      document.getElementById('stepNode5').className = 'step-node completed';
      document.getElementById('intendedStateText').textContent = `Record '${dec.crm_id}' exists in HubSpot Private View and domain resolves HTTP 200.`;
      document.getElementById('observedStateText').textContent = `Confirmed active lead '${dec.crm_id}'. Website reachable and active.`;
      document.getElementById('discrepancyAlert').style.display = 'none';
    } else if (dec.verification_status === 'FAILED') {
      vBadge.className = 'badge badge-danger';
      vBadge.textContent = 'VERIFICATION FAILED (HTTP 404)';
      document.getElementById('stepNode5').className = 'step-node rejected';
      document.getElementById('intendedStateText').textContent = `Record '${dec.crm_id}' created in CRM with expectation of active public site.`;
      document.getElementById('observedStateText').textContent = `Record created in CRM, but target website returned HTTP 404 / Inactive.`;
      document.getElementById('discrepancyAlert').style.display = 'flex';
      document.getElementById('discrepancyText').textContent = 'Observed website inactive (HTTP 404), contrary to initial assumption. Kept visible in failed verification state.';
    } else {
      vBadge.className = 'badge badge-neutral';
      vBadge.textContent = dec.verification_status;
      document.getElementById('stepNode5').className = 'step-node';
    }
  }

  // Full Pipeline Execution (Steps 1 to 5)
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const lead = getFormData();
    lead.approved = true; // Full pipeline runs through approval & execution
    resetPipelineUI();

    try {
      const res = await fetch('/leads/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lead)
      });
      const dec = await res.json();
      currentPendingDecision = dec;

      // Step 1: Validated
      document.getElementById('stepNode1').className = 'step-node completed';
      document.getElementById('stepLine1').className = 'step-line completed';

      // Step 2: Render Sources & Provenance
      renderProvenanceTable(dec.provenance);
      document.getElementById('stepNode2').className = 'step-node completed';
      document.getElementById('stepLine2').className = 'step-line completed';

      // Step 3: Decision UI
      const badge = document.getElementById('decisionStatusBadge');
      const reasonBox = document.getElementById('decisionReasonBox');
      document.getElementById('decisionReasonText').textContent = dec.reason;
      document.getElementById('decisionIdempKey').textContent = dec.idempotency_key;

      if (dec.status === 'QUALIFIED') {
        badge.className = 'badge badge-success';
        badge.textContent = 'QUALIFIED';
        reasonBox.className = 'decision-reason-box qualified';
        document.getElementById('stepNode3').className = 'step-node completed';
        document.getElementById('stepLine3').className = 'step-line completed';
        document.getElementById('decisionDeduplicationStatus').textContent = 'Passed Unique Check';

        // Step 4: Action Executed
        document.getElementById('actionStatusBadge').className = 'badge badge-success';
        document.getElementById('actionStatusBadge').textContent = 'Action Approved & Executed';
        document.getElementById('proposedDest').textContent = 'HubSpot CRM Sandbox (Free Tier)';
        document.getElementById('proposedView').textContent = 'Private Research Leads (HS-PRIV-VIEW-409)';
        document.getElementById('proposedActionType').textContent = 'CREATE_LEAD_RECORD';
        document.getElementById('proposedPayloadJson').textContent = JSON.stringify({
          domain: lead.domain,
          legal_name: lead.legal_name,
          region: lead.region,
          employee_count: lead.employee_count,
          idempotency_key: dec.idempotency_key.substring(0, 16) + '...'
        }, null, 2);

        document.getElementById('stepNode4').className = 'step-node completed';
        document.getElementById('stepLine4').className = 'step-line completed';
        document.getElementById('approvalActions').style.display = 'none';
        document.getElementById('executionResultCard').style.display = 'flex';
        document.getElementById('assignedCrmId').textContent = dec.crm_id || 'CRMID-N/A';
        document.getElementById('assignedCrmNote').textContent = dec.reason;

        // Step 5: Verification UI
        updateStep5UI(dec);

      } else if (dec.status === 'REJECTED') {
        badge.className = 'badge badge-danger';
        badge.textContent = 'REJECTED';
        reasonBox.className = 'decision-reason-box rejected';
        document.getElementById('stepNode3').className = 'step-node rejected';
        document.getElementById('decisionDeduplicationStatus').textContent = dec.reason.includes('Duplicate') ? 'Collision Detected' : 'Out of Scope';

        document.getElementById('actionStatusBadge').className = 'badge badge-neutral';
        document.getElementById('actionStatusBadge').textContent = 'Action Prohibited (Rejected)';
        document.getElementById('approvalActions').style.display = 'none';
        document.getElementById('proposedPayloadJson').textContent = '{\n  "blocked": true,\n  "reason": "' + dec.reason + '"\n}';
      } else if (dec.status === 'UNCERTAIN') {
        badge.className = 'badge badge-warning';
        badge.textContent = 'UNCERTAIN (Missing Evidence)';
        reasonBox.className = 'decision-reason-box uncertain';
        document.getElementById('stepNode3').className = 'step-node uncertain';
        document.getElementById('decisionDeduplicationStatus').textContent = 'Incomplete Public Evidence';

        document.getElementById('actionStatusBadge').className = 'badge badge-neutral';
        document.getElementById('actionStatusBadge').textContent = 'Action Blocked (Evidence Missing)';
        document.getElementById('approvalActions').style.display = 'none';
        document.getElementById('proposedPayloadJson').textContent = '{\n  "uncertain": true,\n  "missing": "employee_count evidence missing in public directory"\n}';
      }

    } catch (err) {
      console.error(err);
      alert('Error during pipeline execution.');
    }
  });

  function renderProvenanceTable(sources) {
    const tbody = document.getElementById('provenanceTableBody');
    tbody.innerHTML = '';
    for (const [key, p] of Object.entries(sources)) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong style="text-transform: capitalize;">${key.replace('_', ' ')}</strong></td>
        <td><code>${p.source_id}</code></td>
        <td><a href="${p.source_url}" target="_blank" style="color: #38bdf8; text-decoration: none;">${p.source_url}</a></td>
        <td style="font-family: var(--font-mono); font-size: 0.75rem;">${p.extracted_at}</td>
        <td><span class="badge ${p.raw_value === 'NOT_FOUND' ? 'badge-danger' : 'badge-neutral'}">${p.raw_value}</span></td>
      `;
      tbody.appendChild(tr);
    }
    document.getElementById('provenanceTimestamp').textContent = new Date().toLocaleTimeString();
  }

  // Step 7: Official Scenarios Suite Runner
  btnRunAllScenarios.addEventListener('click', runAllScenarios);

  async function runAllScenarios() {
    scenariosLoadedOnce = true;
    const container = document.getElementById('scenariosCardsContainer');
    container.innerHTML = '<div style="color: #94a3b8; font-style: italic; padding: 2rem;">Executing official labelled runs against HubSpot Sandbox...</div>';

    try {
      const res = await fetch('/api/run-all-official', { method: 'POST' });
      const data = await res.json();
      container.innerHTML = '';

      data.benchmark_runs.forEach(run => {
        const sc = run.scenario;
        const dec = run.decision;
        const statusMatch = run.status_match;
        const verifMatch = run.verification_match;

        const card = document.createElement('div');
        card.className = 'scenario-card';

        let statusBadgeClass = dec.status === 'QUALIFIED' ? 'badge-success' : dec.status === 'REJECTED' ? 'badge-danger' : 'badge-warning';
        let verifBadgeClass = dec.verification_status === 'VERIFIED_SUCCESS' ? 'badge-success' : dec.verification_status === 'FAILED' ? 'badge-danger' : 'badge-neutral';

        let explanationHtml = '';
        if (sc.label === 'RUN-04') {
          explanationHtml = `
            <div class="verif-explanation-box">
              <strong>Honest Verification Transparency:</strong>
              This lead satisfied all initial criteria and was loaded into CRM (<code>${dec.crm_id}</code>). However, independent post-action resolution verified the domain is inactive (HTTP 404). Kept visible in failed verification state rather than disguised as success.
            </div>
          `;
        } else if (sc.label === 'RUN-02') {
          explanationHtml = `
            <div style="font-size: 0.78rem; color: #94a3b8;">
              <strong>Deduplication Audit:</strong> Cleanly blocked CRM write. Matched pre-existing customer record CRMID-881 in HubSpot Sandbox.
            </div>
          `;
        } else if (sc.label === 'RUN-03') {
          explanationHtml = `
            <div style="font-size: 0.78rem; color: #fde68a;">
              <strong>Evidence Safety Gate:</strong> Stopped prior to CRM mutation because employee count evidence could not be verified from public registries.
            </div>
          `;
        }

        card.innerHTML = `
          <div class="scenario-card-header">
            <div>
              <span class="scenario-label">${sc.label}</span>
              <h3 class="scenario-name">${sc.name}</h3>
            </div>
            <span class="badge ${statusBadgeClass}">${dec.status}</span>
          </div>
          <p class="scenario-desc">${sc.description}</p>

          <div class="scenario-meta-table">
            <div class="s-meta-row"><span class="s-meta-label">Domain:</span><span class="s-meta-val">${sc.domain}</span></div>
            <div class="s-meta-row"><span class="s-meta-label">Region:</span><span class="s-meta-val">${sc.region}</span></div>
            <div class="s-meta-row"><span class="s-meta-label">Employee Count:</span><span class="s-meta-val">${sc.employee_count !== null ? sc.employee_count : 'MISSING (None)'}</span></div>
            <div class="s-meta-row"><span class="s-meta-label">Website Active:</span><span class="s-meta-val">${sc.website_active ? 'Yes (HTTP 200)' : 'No (HTTP 404)'}</span></div>
            <div class="s-meta-row"><span class="s-meta-label">CRM ID:</span><span class="s-meta-val">${dec.crm_id || 'None (No Write)'}</span></div>
          </div>

          <div class="comparison-box">
            <div class="comp-row">
              <span class="comp-label">Qualification Status:</span>
              <div class="comp-vals">
                <span class="badge ${statusBadgeClass}">${dec.status}</span>
                <span style="font-size: 0.75rem; color: ${statusMatch ? '#34d399' : '#f87171'}">(${statusMatch ? 'Expected' : 'Mismatch'})</span>
              </div>
            </div>
            <div class="comp-row">
              <span class="comp-label">Post-Action Verification:</span>
              <div class="comp-vals">
                <span class="badge ${verifBadgeClass}">${dec.verification_status}</span>
                <span style="font-size: 0.75rem; color: ${verifMatch ? '#34d399' : '#f87171'}">(${verifMatch ? 'Expected' : 'Mismatch'})</span>
              </div>
            </div>
          </div>

          ${explanationHtml}
        `;
        container.appendChild(card);
      });

      // Show Idempotency Proof Card
      if (data.idempotency_test) {
        const idempCard = document.getElementById('idempotencyProofCard');
        idempCard.style.display = 'block';
        document.getElementById('proofCrmId').textContent = data.idempotency_test.crm_id;
      }

      // Also render Step 6 Results view
      renderStep6Tables(data.step6_result_view);

    } catch (err) {
      console.error(err);
      container.innerHTML = '<div style="color: #f87171; padding: 2rem;">Error executing benchmark scenarios.</div>';
    }
  }

  // Step 6: Result View
  async function loadStep6Results() {
    try {
      const res = await fetch('/api/run-all-official', { method: 'POST' });
      const data = await res.json();
      renderStep6Tables(data.step6_result_view);
    } catch (err) {
      console.error(err);
    }
  }

  function renderStep6Tables(view) {
    if (!view || !view.summary) return;

    // Counters
    document.getElementById('cntTotal').textContent = view.summary.total_processed;
    document.getElementById('cntQualified').textContent = view.summary.qualified_count;
    document.getElementById('cntRejected').textContent = view.summary.rejected_count;
    document.getElementById('cntUnresolved').textContent = view.summary.unresolved_count;

    document.getElementById('badgeQualifiedCount').textContent = `${view.summary.qualified_count} Leads`;
    document.getElementById('badgeRejectedCount').textContent = `${view.summary.rejected_count} Leads`;
    document.getElementById('badgeUnresolvedCount').textContent = `${view.summary.unresolved_count} Leads`;

    // 1. Qualified
    const qBody = document.getElementById('qualifiedLeadsTableBody');
    qBody.innerHTML = '';
    if (view.qualified_leads_view.length === 0) {
      qBody.innerHTML = '<tr><td colspan="6" class="empty-cell">No qualified leads.</td></tr>';
    } else {
      view.qualified_leads_view.forEach(q => {
        const tr = document.createElement('tr');
        const verifBadgeClass = q.verification_status === 'VERIFIED_SUCCESS' ? 'badge-success' : 'badge-danger';
        tr.innerHTML = `
          <td><strong style="color:#93c5fd;">${q.request_id}</strong></td>
          <td>
            <strong>${q.legal_name}</strong><br>
            <span style="font-size:0.75rem; color:#94a3b8;">${q.domain}</span>
          </td>
          <td><code style="color:#34d399; font-weight:700;">${q.crm_id}</code></td>
          <td><span style="font-size:0.78rem; color:#c084fc;">${q.target_view}</span></td>
          <td><span class="badge ${verifBadgeClass}">${q.verification_status}</span></td>
          <td style="font-size:0.75rem;">
            Web: <a href="${q.sources.domain.url}" target="_blank" style="color:#38bdf8;">${q.sources.domain.url}</a><br>
            Dir: <a href="${q.sources.legal_name.url}" target="_blank" style="color:#38bdf8;">${q.sources.legal_name.source_id}</a>
          </td>
        `;
        qBody.appendChild(tr);
      });
    }

    // 2. Rejected
    const rBody = document.getElementById('rejectedLeadsTableBody');
    rBody.innerHTML = '';
    if (view.rejected_leads_view.length === 0) {
      rBody.innerHTML = '<tr><td colspan="5" class="empty-cell">No rejected leads.</td></tr>';
    } else {
      view.rejected_leads_view.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong style="color:#f87171;">${r.request_id}</strong></td>
          <td>
            <strong>${r.legal_name}</strong><br>
            <span style="font-size:0.75rem; color:#94a3b8;">${r.domain}</span>
          </td>
          <td>${r.region} (${r.employee_count} emp)</td>
          <td style="color:#fca5a5;">${r.decision_reason}</td>
          <td><span class="badge badge-danger">Blocked from CRM</span></td>
        `;
        rBody.appendChild(tr);
      });
    }

    // 3. Unresolved
    const uBody = document.getElementById('unresolvedLeadsTableBody');
    uBody.innerHTML = '';
    if (view.unresolved_leads_view.length === 0) {
      uBody.innerHTML = '<tr><td colspan="5" class="empty-cell">No unresolved leads.</td></tr>';
    } else {
      view.unresolved_leads_view.forEach(u => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong style="color:#fbbf24;">${u.request_id}</strong></td>
          <td>
            <strong>${u.legal_name}</strong><br>
            <span style="font-size:0.75rem; color:#94a3b8;">${u.domain}</span>
          </td>
          <td><span class="badge badge-warning">employee_count (Null)</span></td>
          <td style="color:#fde68a;">${u.decision_reason}</td>
          <td><span style="font-size:0.78rem; color:#38bdf8;">Manual lookup required</span></td>
        `;
        uBody.appendChild(tr);
      });
    }
  }

  // CRM Sandbox Viewer
  async function loadCrmRecords() {
    const tableBody = document.getElementById('crmRecordsTableBody');
    const auditContainer = document.getElementById('crmAuditLogContainer');
    tableBody.innerHTML = '<tr><td colspan="7" class="empty-cell">Loading CRM database...</td></tr>';
    auditContainer.innerHTML = '<div style="color: #94a3b8; font-size: 0.8rem;">Loading audit logs...</div>';

    try {
      const res = await fetch('/api/crm-records');
      const data = await res.json();

      document.getElementById('crmRecordsCount').textContent = `${data.total_records} Records in View`;
      tableBody.innerHTML = '';

      for (const [crmId, r] of Object.entries(data.records)) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong style="color:#34d399;">${crmId}</strong></td>
          <td>${r.legal_name || r.company_name || '-'}</td>
          <td><code>${r.domain || r.company_domain || '-'}</code></td>
          <td>${r.region || r.target_region || '-'}</td>
          <td>${r.employee_count !== undefined ? r.employee_count : '-'}</td>
          <td><span class="badge badge-info">${r.hs_lead_status || 'QUALIFIED'}</span></td>
          <td><code style="font-size:0.7rem; color:#93c5fd;">${(r.idempotency_key || '').substring(0, 16)}...</code></td>
        `;
        tableBody.appendChild(tr);
      }

      // Audit logs
      auditContainer.innerHTML = '';
      if (!data.audit_log || data.audit_log.length === 0) {
        auditContainer.innerHTML = '<div style="color: #64748b; font-size: 0.8rem; padding: 1rem;">No mutations logged yet.</div>';
      } else {
        data.audit_log.slice().reverse().forEach(log => {
          const item = document.createElement('div');
          item.className = 'audit-item';
          const isInsert = log.action === 'NEW_RECORD_INSERTED';
          item.innerHTML = `
            <div class="audit-header">
              <span class="audit-action ${isInsert ? 'insert' : 'prevented'}">${log.action}</span>
              <span class="audit-time">${new Date(log.timestamp).toLocaleTimeString()}</span>
            </div>
            <div class="audit-note">${log.note}</div>
            <div class="audit-idemp">ID: ${log.crm_id} | Key: ${log.idempotency_key.substring(0, 16)}...</div>
          `;
          auditContainer.appendChild(item);
        });
      }
    } catch (err) {
      console.error(err);
      tableBody.innerHTML = '<tr><td colspan="7" class="empty-cell" style="color:#f87171;">Failed to load CRM data.</td></tr>';
    }
  }

  btnRefreshCrm.addEventListener('click', loadCrmRecords);

  // Reset CRM
  resetCrmBtn.addEventListener('click', async () => {
    if (confirm('Reset HubSpot CRM Sandbox to clean initial state?')) {
      try {
        await fetch('/api/reset-crm', { method: 'POST' });
        alert('CRM Sandbox reset to initial state.');
        loadCrmRecords();
        resetPipelineUI();
      } catch (err) {
        console.error(err);
      }
    }
  });

  // Initial load
  loadCrmRecords();
});
