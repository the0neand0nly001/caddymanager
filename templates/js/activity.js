let activityLoaded = false;
let activityBusy = false;
let activityCursor = null;
let activityCount = 0;

async function loadActivity(older = false) {
    if (activityBusy) return;
    activityBusy = true;
    const message = document.getElementById('activityMessage');
    document.getElementById('refreshActivity').disabled = true;
    document.getElementById('olderActivity').disabled = true;
    message.textContent = 'Loading audit log...';
    try {
        const url = '/api/activity' + (older && activityCursor !== null ? '?before=' + activityCursor : '');
        const response = await fetch(url);
        const data = await dashboardResponse(response, 'Audit log could not be loaded.');
        const body = document.getElementById('activityRows');
        if (!older || !activityCount) {
            body.replaceChildren();
            activityCount = 0;
        }
        for (const entry of data.entries) {
            const row = document.createElement('tr');
            row.append(textCell(entry.timestamp || '—'), textCell(entry.action), textCell(entry.ip || '—'), textCell(entry.details));
            row.cells[1].className = 'audit-action';
            if (/(?:FAIL|ERROR|CSRF)/.test(entry.action)) row.cells[1].dataset.severity = 'warning';
            body.append(row);
        }
        activityCount += data.entries.length;
        activityCursor = data.next_cursor;
        activityLoaded = true;
        if (!activityCount) {
            const row = document.createElement('tr');
            const cell = textCell('No audit entries recorded.');
            cell.colSpan = 4;
            cell.className = 'empty-state';
            row.append(cell);
            body.append(row);
        }
        message.textContent = `${activityCount} recorded entries shown. ` + (activityCursor === null ? 'End of available log.' : 'Load older entries for more.') + (data.truncated ? ' An oversized log line was omitted.' : '');
        document.getElementById('olderActivity').hidden = activityCursor === null;
    } catch (error) {
        message.textContent = (error instanceof TypeError ? 'Could not reach the manager. Check your connection and retry.' : error.message) + (activityCount ? ' Previously loaded entries are retained.' : '');
    } finally {
        activityBusy = false;
        document.getElementById('refreshActivity').disabled = false;
        document.getElementById('olderActivity').disabled = false;
    }
}
