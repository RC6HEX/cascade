/**
 * @typedef {'todo' | 'in-progress' | 'done'} TaskStatus
 */

/**
 * @typedef {object} Task
 * @property {string} id - Unique identifier for the task.
 * @property {string} title - The title of the task.
 * @property {string} description - The description of the task.
 * @property {TaskStatus} status - The current status of the task.
 */

/** @type {Task[]} */
let tasks = [];

/**
 * Initializes the in-memory task list.
 * @param {Task[]} initialTasks - Tasks loaded from storage.
 */
export function initializeTasks(initialTasks) {
    tasks = initialTasks;
}

/**
 * Gets the current list of all tasks.
 * @returns {Task[]} The array of tasks.
 */
export function getTasks() {
    return tasks;
}

/**
 * Creates and adds a new task to the list.
 * Implements ФТ-03.
 * @param {string} title - The title for the new task.
 * @param {string} description - The description for the new task.
 * @returns {Task} The newly created task object.
 */
export function addTask(title, description) {
    /** @type {Task} */
    const newTask = {
        id: Date.now().toString() + Math.random().toString(36).substring(2, 9),
        title,
        description,
        status: 'todo',
    };
    tasks.push(newTask);
    return newTask;
}

/**
 * Updates the status of an existing task.
 * Implements ФТ-05.
 * @param {string} taskId - The ID of the task to update.
 * @param {TaskStatus} newStatus - The new status for the task.
 */
export function updateTaskStatus(taskId, newStatus) {
    const task = tasks.find(t => t.id === taskId);
    if (task) {
        task.status = newStatus;
    }
}

/**
 * Deletes a task from the list.
 * Implements ФТ-06.
 * @param {string} taskId - The ID of the task to delete.
 */
export function deleteTask(taskId) {
    tasks = tasks.filter(t => t.id !== taskId);
}
