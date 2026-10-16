let serviceRoutes = [];
let healthResults = new Map();
let caddyState = null;
let managerConnected = null;
let overviewPending = false;
let overviewLoaded = false;
let healthBusy = false;
let checkingDomain = null;
let initialChecksStarted = false;
let healthError = '';
let resourceError = false;

async function dashboardResponse(response, fallback) {
    if (response.status === 401) throw new Error('Your session has expired. Sign in again.');
    if (response.status === 429) throw new Error('Too many requests. Wait a moment before trying again.');
    let data;
    try {
        data = await response.json();
    } catch {
        throw new Error(fallback + ' Refresh the page and try again.');
    }
    if (!response.ok) throw new Error(data.error || fallback);
    return data;
}

function textCell(value, tag = 'td') {
    const cell = document.createElement(tag);
    cell.textContent = value;
    if (tag === 'th') cell.scope = 'row';
    return cell;
}

function healthTotals() {
    const totals = {
        online: 0,
        down: 0,
        unchecked: 0,
        unconfigured: 0
    };
    for (const route of serviceRoutes) {
        const status = route.checkable ? (healthResults.get(route.domain)?.status || 'unchecked') : 'unconfigured';
        totals[status] += 1;
    }
    return totals;
}

function renderSystemStatus() {
    const totals = healthTotals();
    const warnings = [];
    document.getElementById('managerState').textContent = managerConnected === null ? 'Manager: checking' : managerConnected ? 'Manager: connected' : 'Manager: unavailable';
    const caddyLabels = {
        responding: 'responding',
        active: 'service active',
        inactive: 'service inactive',
        unavailable: 'unavailable',
        unknown: 'status unknown'
    };
    document.getElementById('caddyState').textContent = 'Caddy: ' + (caddyState ? caddyLabels[caddyState.state] : 'checking');
    document.getElementById('servicesState').textContent = overviewLoaded ? `Backends: ${totals.online} reachable, ${totals.down} unreachable` : 'Backends: not checked';
    document.getElementById('managerState').dataset.indicator = managerConnected === null ? 'pending' : managerConnected ? 'online' : 'down';
    document.getElementById('caddyState').dataset.indicator = !caddyState || caddyState.state === 'unknown' ? 'pending' : ['responding', 'active'].includes(caddyState.state) ? 'online' : 'down';
    document.getElementById('servicesState').dataset.indicator = healthError || totals.unchecked || !overviewLoaded || managerConnected === false ? 'pending' : totals.down ? 'down' : totals.online ? 'online' : 'neutral';
    if (managerConnected === false) warnings.push('Manager status could not be refreshed. Displayed information may be out of date; check the connection or sign in again.');
    if (caddyState && !['responding', 'active'].includes(caddyState.state)) warnings.push('Caddy status needs attention. Check the Caddy service and its connection to the manager.');
    if (totals.down) warnings.push(`${totals.down} ${totals.down === 1 ? 'route has an unreachable backend port.' : 'routes have unreachable backend ports.'}`);
    if (healthError) warnings.push(healthError);
    if (resourceError) warnings.push('Manager resource metrics are unavailable; previous values may be out of date.');
    const pending = managerConnected === null || !caddyState || !overviewLoaded || totals.unchecked > 0;
    const summary = warnings.length ? 'Attention needed' : pending ? 'Checks pending' : serviceRoutes.some(route => route.checkable) ? 'Checks passed' : 'Caddy available';
    document.getElementById('systemSummary').textContent = summary;
    const warning = document.getElementById('systemWarnings');
    const notes = [...warnings];
    if (totals.unconfigured) notes.push(`${totals.unconfigured} ${totals.unconfigured === 1 ? 'route has no usable proxy target and is excluded' : 'routes have no usable proxy target and are excluded'} from backend checks.`);
    warning.hidden = notes.length === 0;
    warning.textContent = notes.join(' ');
    warning.closest('.system-status').dataset.state = warnings.length ? 'warning' : pending ? 'pending' : 'ok';
    if (overviewLoaded) {
        for (const [name, value] of Object.entries(totals)) document.getElementById('total-' + name).textContent = value;
    }
}

function buildServiceRows() {
    const body = document.getElementById('serviceRows');
    body.replaceChildren();
    for (const route of serviceRoutes) {
        const row = document.createElement('tr');
        row.append(textCell(route.domain, 'th'));
        const target = textCell(route.target);
        target.className = 'mono';
        row.append(target, textCell(''), textCell(''));
        const controls = textCell('');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'button button-quiet';
        button.textContent = 'Check';
        button.dataset.domain = route.domain;
        button.setAttribute('aria-label', 'Check backend for ' + route.domain);
        controls.append(button);
        row.append(controls);
        body.append(row);
    }
    if (!serviceRoutes.length) {
        const row = document.createElement('tr');
        const cell = textCell('No routes configured. Add a route from Routes.');
        cell.colSpan = 5;
        cell.className = 'empty-state';
        row.append(cell);
        body.append(row);
    }
}

function renderServiceHealth() {
    const rows = document.getElementById('serviceRows').rows;
    serviceRoutes.forEach((route, index) => {
        const result = healthResults.get(route.domain);
        const checking = healthBusy && route.checkable && (!checkingDomain || checkingDomain === route.domain);
        const state = checking ? 'checking' : !route.checkable ? 'unconfigured' : result?.status || 'unchecked';
        const labels = {
            online: 'Reachable',
            down: 'Unreachable',
            unchecked: 'Not checked',
            unconfigured: 'No target',
            checking: 'Checking...'
        };
        rows[index].cells[2].textContent = labels[state];
        rows[index].cells[2].dataset.health = state;
        rows[index].cells[2].classList.add('health-indicator');
        const timestamp = result?.checked_at;
        rows[index].cells[3].textContent = timestamp ? new Date(timestamp).toLocaleTimeString() : '—';
        rows[index].cells[3].title = timestamp ? new Date(timestamp).toLocaleString() : 'No check completed';
        rows[index].querySelector('button').disabled = healthBusy || !route.checkable;
    });
    const button = document.getElementById('checkAllServices');
    button.disabled = healthBusy || !serviceRoutes.some(route => route.checkable);
    button.textContent = healthBusy && !checkingDomain ? 'Checking...' : 'Check all';
    renderSystemStatus();
}

async function refreshOverview() {
    if (overviewPending) return;
    overviewPending = true;
    try {
        const response = await fetch('/api/overview');
        if (!response.ok) throw new Error('Overview unavailable');
        const data = await response.json();
        managerConnected = true;
        caddyState = data.caddy;
        const changed = JSON.stringify(serviceRoutes) !== JSON.stringify(data.services);
        if (changed || !overviewLoaded) {
            for (const [domain, result] of healthResults) {
                if (!data.services.some(route => route.domain === domain && route.target === result.target)) healthResults.delete(domain);
            }
            serviceRoutes = data.services;
            buildServiceRows();
        }
        overviewLoaded = true;
        document.getElementById('metric-routes').textContent = data.totals.routes;
        document.getElementById('total-domains').textContent = data.totals.domains;
        document.getElementById('overviewUpdated').textContent = 'Configuration read ' + new Date(data.observed_at).toLocaleTimeString();
        renderServiceHealth();
        startInitialChecks();
    } catch {
        managerConnected = false;
        renderSystemStatus();
    } finally {
        overviewPending = false;
    }
}

function dashboardVisible() {
    return !document.hidden && !document.getElementById('tab-dashboard').hidden;
}

function startInitialChecks() {
    if (overviewLoaded && !initialChecksStarted && dashboardVisible()) {
        initialChecksStarted = true;
        checkServices();
    }
}

async function checkServices(domain = null) {
    if (healthBusy || !overviewLoaded) return;
    healthBusy = true;
    checkingDomain = domain;
    healthError = '';
    renderServiceHealth();
    try {
        const response = await fetch('/api/services/check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': {{ csrf_token() | tojson }}
            },
            body: JSON.stringify(domain ? {
                domain
            } : {})
        });
        const data = await dashboardResponse(response, 'Health checks could not be completed.');
        for (const result of data.services) {
            if (serviceRoutes.some(route => route.domain === result.domain && route.target === result.target)) healthResults.set(result.domain, result);
        }
    } catch (error) {
        healthError = (error instanceof TypeError ? 'Could not reach the manager. Check your connection and retry.' : error.message) + ' Previous health results may be out of date.';
    } finally {
        healthBusy = false;
        checkingDomain = null;
        renderServiceHealth();
    }
}
