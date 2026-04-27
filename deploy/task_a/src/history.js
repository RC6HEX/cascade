let historyListElement;
let historyItems = [];
const MAX_HISTORY_ITEMS = 10;

/**
 * @description Initializes the history module.
 * @param {HTMLElement} listEl - The <ul> element for displaying history.
 */
export function initHistory(listEl) {
    historyListElement = listEl;
    renderHistory();
}

/**
 * @description Adds a new entry to the history and re-renders the list.
 * Implements ФТ-07.
 * @param {string} entry - The string representation of the calculation.
 */
export function addHistoryEntry(entry) {
    if (!entry) return;
    historyItems.unshift(entry);

    if (historyItems.length > MAX_HISTORY_ITEMS) {
        historyItems.pop();
    }
    
    renderHistory();
}

/**
 * @description Renders the current history items to the DOM.
 * Implements ФТ-08.
 */
function renderHistory() {
    if (!historyListElement) return;
    
    historyListElement.innerHTML = '';

    for (const item of historyItems) {
        const li = document.createElement('li');
        li.className = 'history-item';
        li.textContent = item;
        historyListElement.appendChild(li);
    }
}
