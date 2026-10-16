const mobileLayout = window.matchMedia('(max-width: 880px)');

function readPreference(key) {
    try {
        return localStorage.getItem(key);
    } catch {
        return null;
    }
}

function savePreference(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch {
        /* Preferences remain optional. */
    }
}

function setMobileMenu(open) {
    const isOpen = open && mobileLayout.matches;
    document.body.classList.toggle('nav-open', isOpen);
    document.getElementById('sidebarOverlay').hidden = !isOpen;
    document.getElementById('mobileMenu').setAttribute('aria-expanded', String(isOpen));
    document.getElementById('workspace').inert = isOpen;
    document.getElementById('appSidebar').inert = mobileLayout.matches && !isOpen;
    if (isOpen) document.getElementById('mobileClose').focus();
}

function setSidebarCollapsed(collapsed) {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    const button = document.getElementById('sidebarCollapse');
    button.setAttribute('aria-expanded', String(!collapsed));
    button.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    button.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
    savePreference('caddy_sidebar_collapsed', collapsed);
}

function setSettingsOpen(open) {
    document.getElementById('viewSettings').hidden = !open;
    document.getElementById('settingsButton').setAttribute('aria-expanded', String(open));
    if (open) document.getElementById('settingsDomainFilter').focus();
}

function switchTab(tabId) {
    const page = document.getElementById('tab-' + tabId);
    if (!page) return;
    document.querySelectorAll('.tab-content').forEach(section => {
        const active = section === page;
        section.classList.toggle('active', active);
        section.hidden = !active;
    });
    document.querySelectorAll('.tab-btn').forEach(button => {
        const active = button.dataset.page === tabId;
        button.classList.toggle('active', active);
        if (active) button.setAttribute('aria-current', 'page');
        else button.removeAttribute('aria-current');
    });
    document.getElementById('pageTitle').textContent = {
        dashboard: 'System Dashboard',
        routes: 'Routes',
        domains: 'Base domains',
        activity: 'Activity'
    } [tabId];
    savePreference('active_tab', tabId);
    setSettingsOpen(false);
    if (tabId === 'activity' && !activityLoaded) loadActivity();
    if (tabId === 'dashboard') {
        if (initialChecksStarted && overviewLoaded) checkServices();
        else startInitialChecks();
    }
    if (mobileLayout.matches) {
        setMobileMenu(false);
        document.getElementById('pageTitle').focus();
    }
}

let metricsPending = false;

async function fetchMetrics() {
    if (metricsPending) return;
    metricsPending = true;
    try {
        const response = await fetch('/api/metrics');
        if (!response.ok) throw new Error('Metrics unavailable');
        const data = await response.json();
        document.getElementById('metric-cpu').textContent = data.cpu + '%';
        document.getElementById('metric-ram').textContent = data.ram_mb + ' MB';
        document.getElementById('resourceUpdated').textContent = 'Updated ' + new Date().toLocaleTimeString() + ' · Manager process only';
        resourceError = false;
    } catch {
        resourceError = true;
    } finally {
        metricsPending = false;
        renderSystemStatus();
    }
}

function toggleTargetVisibility() {
    const show = document.getElementById('toggleTargets').checked;
    document.getElementById('settingsToggleTargets').checked = show;
    savePreference('show_caddy_targets', show);
    document.querySelectorAll('.domain-target').forEach(target => {
        target.style.display = show ? 'block' : 'none';
    });
}

function filterDomains() {
    const selected = document.getElementById('domainFilter').value;
    document.getElementById('settingsDomainFilter').value = selected;
    savePreference('selected_domain_filter', selected);
    let visible = 0;
    document.querySelectorAll('.domain-item').forEach(item => {
        const matches = selected === 'all' || item.dataset.domain.endsWith('.' + selected);
        item.style.display = matches ? 'flex' : 'none';
        if (matches) visible += 1;
    });
    const empty = document.getElementById('filteredEmpty');
    if (empty) empty.hidden = visible !== 0;
}

document.addEventListener('DOMContentLoaded', () => {
    setSidebarCollapsed(readPreference('caddy_sidebar_collapsed') === 'true');
    const requestedPage = new URLSearchParams(window.location.search).get('page');
    switchTab(['dashboard', 'routes', 'domains', 'activity'].includes(requestedPage) ? requestedPage : (readPreference('active_tab') || 'dashboard'));
    if (requestedPage) window.history.replaceState(null, '', window.location.pathname);
    setMobileMenu(false);
    document.getElementById('sidebarCollapse').addEventListener('click', () => setSidebarCollapsed(!document.body.classList.contains('sidebar-collapsed')));
    document.getElementById('mobileMenu').addEventListener('click', () => setMobileMenu(true));
    document.getElementById('mobileClose').addEventListener('click', () => {
        setMobileMenu(false);
        document.getElementById('mobileMenu').focus();
    });
    document.getElementById('sidebarOverlay').addEventListener('click', () => {
        setMobileMenu(false);
        document.getElementById('mobileMenu').focus();
    });
    document.getElementById('settingsButton').addEventListener('click', () => setSettingsOpen(document.getElementById('viewSettings').hidden));
    document.addEventListener('click', event => {
        if (!event.target.closest('.settings-container')) setSettingsOpen(false);
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Tab' && document.body.classList.contains('nav-open')) {
            const controls = [...document.getElementById('appSidebar').querySelectorAll('a[href], button, input, select')]
                .filter(element => !element.disabled && element.getClientRects().length);
            const first = controls[0];
            const last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
        if (event.key === 'Escape') {
            if (!document.getElementById('viewSettings').hidden) {
                setSettingsOpen(false);
                document.getElementById('settingsButton').focus();
            } else if (document.body.classList.contains('nav-open')) {
                setMobileMenu(false);
                document.getElementById('mobileMenu').focus();
            }
        }
    });
    mobileLayout.addEventListener('change', () => setMobileMenu(false));
    document.getElementById('toggleTargets').checked = readPreference('show_caddy_targets') === 'true';
    toggleTargetVisibility();
    const filter = document.getElementById('domainFilter');
    const savedFilter = readPreference('selected_domain_filter');
    if ([...filter.options].some(option => option.value === savedFilter)) filter.value = savedFilter;
    filterDomains();
    document.getElementById('settingsToggleTargets').addEventListener('change', event => {
        document.getElementById('toggleTargets').checked = event.target.checked;
        toggleTargetVisibility();
    });
    document.getElementById('settingsDomainFilter').addEventListener('change', event => {
        filter.value = event.target.value;
        filterDomains();
    });
    const toast = document.getElementById('toastMessage');
    if (toast) {
        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
    document.getElementById('checkAllServices').addEventListener('click', () => checkServices());
    document.getElementById('serviceRows').addEventListener('click', event => {
        const button = event.target.closest('button[data-domain]');
        if (button) checkServices(button.dataset.domain);
    });
    document.getElementById('refreshActivity').addEventListener('click', () => loadActivity());
    document.getElementById('olderActivity').addEventListener('click', () => loadActivity(true));
    fetchMetrics();
    refreshOverview();
    setInterval(() => {
        if (!document.hidden) fetchMetrics();
    }, 3000);
    setInterval(() => {
        if (!document.hidden) refreshOverview();
    }, 10000);
    setInterval(() => {
        if (dashboardVisible()) checkServices();
    }, 60000);
});
