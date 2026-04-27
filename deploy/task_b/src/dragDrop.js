import * as TaskManager from './task.js';

let draggedTaskId = null;

/**
 * Handles the start of a drag operation.
 * @param {DragEvent} event
 */
function handleDragStart(event) {
    const taskCard = event.target.closest('.task-card');
    if (!taskCard) return;

    // Prevent dragging if a filter is active
    if (document.getElementById('task-board').classList.contains('filtered')) {
        event.preventDefault();
        return;
    }

    draggedTaskId = taskCard.dataset.taskId;
    event.dataTransfer.setData('text/plain', draggedTaskId);
    // Timeout to allow the browser to create the drag image before applying the class
    setTimeout(() => {
        taskCard.classList.add('dragging');
    }, 0);
}

/**
 * Handles the end of a drag operation (success or failure).
 * @param {DragEvent} event
 */
function handleDragEnd(event) {
    const taskCard = event.target.closest('.task-card');
    if (taskCard) {
        taskCard.classList.remove('dragging');
    }
    draggedTaskId = null;
}

/**
 * Handles a dragged item over a valid drop target.
 * @param {DragEvent} event
 */
function handleDragOver(event) {
    event.preventDefault();
    const columnContainer = event.target.closest('.tasks-container');
    if (columnContainer) {
        columnContainer.classList.add('drag-over');
    }
}

/**
 * Handles a dragged item leaving a valid drop target.
 * @param {DragEvent} event
 */
function handleDragLeave(event) {
    const columnContainer = event.target.closest('.tasks-container');
    if (columnContainer) {
        columnContainer.classList.remove('drag-over');
    }
}

/**
 * Handles dropping a dragged item onto a valid drop target.
 * Implements ФТ-05.
 * @param {DragEvent} event
 * @param {Function} onUpdate - Callback function to execute after updating the task status.
 */
function handleDrop(event, onUpdate) {
    event.preventDefault();
    const columnContainer = event.target.closest('.tasks-container');
    if (!columnContainer) return;

    columnContainer.classList.remove('drag-over');
    const taskId = event.dataTransfer.getData('text/plain');
    const newStatus = columnContainer.dataset.statusContainer;

    const task = TaskManager.getTasks().find(t => t.id === taskId);
    if (task && task.status !== newStatus) {
        TaskManager.updateTaskStatus(taskId, newStatus);
        onUpdate();
    }
}

/**
 * Initializes drag and drop functionality for the task board.
 * @param {Function} onUpdate - The callback function to run after a successful drop and state update.
 */
export function initDragAndDrop(onUpdate) {
    const board = document.getElementById('task-board');

    board.addEventListener('dragstart', handleDragStart);
    board.addEventListener('dragend', handleDragEnd);

    const columns = board.querySelectorAll('.tasks-container');
    columns.forEach(column => {
        column.addEventListener('dragover', handleDragOver);
        column.addEventListener('dragleave', handleDragLeave);
        column.addEventListener('drop', (event) => handleDrop(event, onUpdate));
    });
}
