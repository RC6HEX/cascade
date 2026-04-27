import { loadTasks, saveTasks } from './storage.js';
import * as TaskManager from './task.js';
import * as UI from './ui.js';
import { initDragAndDrop } from './dragDrop.js';

/**
 * @typedef {import('./task.js').Task} Task
 * @typedef {import('./task.js').TaskStatus} TaskStatus
 */

const DOM = {
    addTaskBtn: document.getElementById('add-task-btn'),
    modal: document.getElementById('task-modal'),
    modalOverlay: document.getElementById('modal-overlay'),
    closeModalBtn: document.getElementById('close-modal-btn'),
    taskForm: document.getElementById('task-form'),
    taskBoard: document.getElementById('task-board'),
    filtersContainer: document.getElementById('filters-container'),
};

/**
 * Saves the current state of tasks to localStorage and re-renders the board.
 * This function serves as a central point for updating the application state.
 * Implements parts of ФТ-03, ФТ-05, ФТ-06.
 */
function saveAndRerender() {
    const tasks = TaskManager.getTasks();
    saveTasks(tasks);
    UI.renderBoard(tasks);
}

/**
 * Handles the form submission for creating a new task.
 * Implements ФТ-03 and ФТ-04.
 * @param {Event} event - The form submission event.
 */
function handleCreateTask(event) {
    event.preventDefault();
    const formData = new FormData(DOM.taskForm);
    const title = formData.get('title').trim();
    const description = formData.get('description').trim();

    if (!title) {
        UI.showValidationError('Название задачи обязательно');
        return;
    }

    UI.hideValidationError();
    TaskManager.addTask(title, description);
    saveAndRerender();
    UI.hideModal();
}

/**
 * Handles clicks on the delete button of a task card.
 * Implements ФТ-06.
 * @param {Event} event - The click event.
 */
function handleDeleteClick(event) {
    const deleteButton = event.target.closest('.delete-task-btn');
    if (!deleteButton) return;

    const taskCard = deleteButton.closest('.task-card');
    const taskId = taskCard.dataset.taskId;

    if (confirm('Вы уверены, что хотите удалить эту задачу?')) {
        TaskManager.deleteTask(taskId);
        saveAndRerender();
    }
}

/**
 * Handles clicks on filter buttons.
 * Implements ФТ-07.
 * @param {Event} event - The click event.
 */
function handleFilterClick(event) {
    const filterButton = event.target.closest('.filter-btn');
    if (!filterButton) return;

    const filter = filterButton.dataset.filter;
    UI.applyFilter(filter);
}

/**
 * Initializes all event listeners for the application.
 */
function setupEventListeners() {
    DOM.addTaskBtn.addEventListener('click', UI.showModal);
    DOM.closeModalBtn.addEventListener('click', UI.hideModal);
    DOM.modalOverlay.addEventListener('click', UI.hideModal);
    DOM.taskForm.addEventListener('submit', handleCreateTask);
    DOM.taskBoard.addEventListener('click', handleDeleteClick);
    DOM.filtersContainer.addEventListener('click', handleFilterClick);
}

/**
 * Main application initialization function.
 * Implements ФТ-01.
 */
function init() {
    const initialTasks = loadTasks();
    TaskManager.initializeTasks(initialTasks);
    UI.renderBoard(TaskManager.getTasks());
    setupEventListeners();
    initDragAndDrop(saveAndRerender);
}

document.addEventListener('DOMContentLoaded', init);
