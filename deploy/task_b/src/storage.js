const STORAGE_KEY = 'taskboardData';

/**
 * Loads tasks from localStorage. Handles missing data or parsing errors.
 * Implements ФТ-01.
 * @returns {import('./task.js').Task[]} An array of tasks.
 */
export function loadTasks() {
    try {
        const storedData = localStorage.getItem(STORAGE_KEY);
        if (!storedData) {
            return [];
        }
        const tasks = JSON.parse(storedData);
        // Basic validation to ensure it's an array
        return Array.isArray(tasks) ? tasks : [];
    } catch (error) {
        console.error('Failed to load or parse tasks from localStorage:', error);
        // In case of corruption, clear the invalid data
        localStorage.removeItem(STORAGE_KEY);
        return [];
    }
}

/**
 * Saves an array of tasks to localStorage.
 * Implements parts of ФТ-03, ФТ-05, ФТ-06.
 * @param {import('./task.js').Task[]} tasks - The array of tasks to save.
 */
export function saveTasks(tasks) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
    } catch (error) {
        console.error('Failed to save tasks to localStorage:', error);
    }
}
