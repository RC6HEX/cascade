/**
 * @typedef {import('./task.js').Task} Task
 * @typedef {import('./task.js').TaskStatus} TaskStatus
 */

const DOM = {
    modal: document.getElementById('task-modal'),
    modalOverlay: document.getElementById('modal-overlay'),
    taskForm: document.getElementById('task-form'),
    titleError: document.getElementById('title-error'),
    taskBoard: document.getElementById('task-board'),
    filtersContainer: document.getElementById('filters-container'),
    counters: {
        todo: document.getElementById('counter-todo'),
        'in-progress': document.getElementById('counter-in-progress'),
        done: document.getElementById('counter-done'),
    },
};

/**
 * Sanitizes a string to prevent XSS by replacing HTML special characters.
 * Implements part of НФТ-06.
 * @param {string} str - The input string.
 * @returns {string} The sanitized string.
 */
function sanitizeHTML(str) {
    const temp = document.createElement('div');
    temp.textContent = str;
    return temp.innerHTML;
}

/**
 * Creates a DOM element for a single task.
 * Implements part of ФТ-03.
 * @param {Task} task - The task object.
 * @returns {HTMLElement} The created task card element.
 */
export function createTaskElement(task) {
    const card = document.createElement('div');
    card.className = 'task-card';
    card.dataset.taskId = task.id;
    card.draggable = true;

    // Sanitize user input to prevent XSS (НФТ-06)
    const sanitizedTitle = sanitizeHTML(task.title);
    const sanitizedDescription = sanitizeHTML(task.description);

    card.innerHTML = `
        <div class="task-card-header">
            <h4 class="task-title">${sanitizedTitle}</h4>
            <button class="delete-task-btn" aria-label="Удалить задачу">&times;</button>
        </div>
        ${task.description ? `<p class="task-description">${sanitizedDescription}</p>` : ''}
    `;
    return card;
}

/**
 * Updates the task counters in the filter buttons.
 * Implements part of ФТ-07.
 * @param {Task[]} tasks - The list of all tasks.
 */
export function updateCounters(tasks) {
    const counts = {
        todo: 0,
        'in-progress': 0,
        done: 0,
    };

    for (const task of tasks) {
        if (counts[task.status] !== undefined) {
            counts[task.status]++;
        }
    }

    DOM.counters.todo.textContent = counts.todo;
    DOM.counters['in-progress'].textContent = counts['in-progress'];
    DOM.counters.done.textContent = counts.done;
}

/**
 * Renders the entire task board, clearing existing tasks and adding new ones.
 * Implements ФТ-02.
 * @param {Task[]} tasks - The array of tasks to render.
 */
export function renderBoard(tasks) {
    const containers = {
        todo: document.querySelector('.tasks-container[data-status-container="todo"]'),
        'in-progress': document.querySelector('.tasks-container[data-status-container="in-progress"]'),
        done: document.querySelector('.tasks-container[data-status-container="done"]'),
    };

    // Clear all columns
    Object.values(containers).forEach(container => container.innerHTML = '');

    // Populate columns with tasks
    for (const task of tasks) {
        const taskElement = createTaskElement(task);
        containers[task.status].appendChild(taskElement);
    }

    updateCounters(tasks);
}

/**
 * Shows the task creation modal.
 */
export function showModal() {
    DOM.taskForm.reset();
    hideValidationError();
    DOM.modal.classList.remove('hidden');
    DOM.modalOverlay.classList.remove('hidden');
    DOM.taskForm.querySelector('input').focus();
}

/**
 * Hides the task creation modal.
 */
export function hideModal() {
    DOM.modal.classList.add('hidden');
    DOM.modalOverlay.classList.add('hidden');
}

/**
 * Displays a validation error message in the form.
 * Implements part of ФТ-04.
 * @param {string} message - The error message to display.
 */
export function showValidationError(message) {
    DOM.titleError.textContent = message;
}

/**
 * Hides the validation error message in the form.
 */
export function hideValidationError() {
    DOM.titleError.textContent = '';
}

/**
 * Applies a filter to the board, showing only columns of a specific status.
 * Implements ФТ-07.
 * @param {string} filter - The status to filter by ('all', 'todo', 'in-progress', 'done').
 */
export function applyFilter(filter) {
    DOM.taskBoard.className = 'board'; // Reset classes
    if (filter !== 'all') {
        DOM.taskBoard.classList.add('filtered', `filtered-${filter}`);
    }

    const buttons = DOM.filtersContainer.querySelectorAll('.filter-btn');
    buttons.forEach(btn => {
        if (btn.dataset.filter === filter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}
