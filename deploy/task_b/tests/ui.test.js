// @vitest-environment happy-dom

import { describe, it, expect, vi } from 'vitest';
import { createTaskElement } from '../src/ui.js';

// Mock DOM elements that ui.js expects to exist
beforeEach(() => {
    document.body.innerHTML = `
        <div id="task-modal"></div>
        <div id="modal-overlay"></div>
        <form id="task-form"></form>
        <div id="title-error"></div>
        <div id="task-board"></div>
        <div id="filters-container"></div>
        <div id="counter-todo"></div>
        <div id="counter-in-progress"></div>
        <div id="counter-done"></div>
    `;
});

// Helper function to access the internal sanitizeHTML for testing (if not exported)
// Since sanitizeHTML is not exported, we'll test its effect via createTaskElement
function getSanitizeHTML(str) {
    const temp = document.createElement('div');
    temp.textContent = str;
    return temp.innerHTML;
}

describe('ui.js', () => {
    // НФТ-06: Санитизация HTML (тестируется косвенно через createTaskElement)
    describe('sanitizeHTML (internal function)', () => {
        it('НФТ-06: должен санитизировать HTML-теги в строке', () => {
            const unsafeString = '<script>alert("XSS")</script><h1>Hello</h1>';
            const sanitized = getSanitizeHTML(unsafeString);
            expect(sanitized).toBe('&lt;script&gt;alert("XSS")&lt;/script&gt;&lt;h1&gt;Hello&lt;/h1&gt;');
        });

        it('НФТ-06: должен санитизировать HTML-сущности', () => {
            const stringWithEntities = 'Text with & < > " \' characters.';
            const sanitized = getSanitizeHTML(stringWithEntities);
            expect(sanitized).toBe('Text with &amp; &lt; &gt; &quot; &#39; characters.');
        });

        it('НФТ-06: должен возвращать исходную строку, если нет HTML', () => {
            const plainString = 'Just plain text.';
            const sanitized = getSanitizeHTML(plainString);
            expect(sanitized).toBe(plainString);
        });

        it('НФТ-06: должен обрабатывать пустую строку', () => {
            const emptyString = '';
            const sanitized = getSanitizeHTML(emptyString);
            expect(sanitized).toBe('');
        });
    });

    // ФТ-03: Создание новой задачи (отображение)
    describe('createTaskElement', () => {
        it('ФТ-03: должен создавать элемент карточки задачи с названием и описанием', () => {
            const task = {
                id: 'task-123',
                title: 'Test Task',
                description: 'This is a test description.',
                status: 'todo',
            };
            const taskElement = createTaskElement(task);

            expect(taskElement.tagName).toBe('DIV');
            expect(taskElement.className).toBe('task-card');
            expect(taskElement.dataset.taskId).toBe(task.id);
            expect(taskElement.draggable).toBe(true);

            expect(taskElement.querySelector('.task-title').textContent).toBe(task.title);
            expect(taskElement.querySelector('.task-description').textContent).toBe(task.description);
            expect(taskElement.querySelector('.delete-task-btn')).not.toBeNull();
        });

        it('ФТ-03: должен создавать элемент карточки задачи без описания, если оно пустое', () => {
            const task = {
                id: 'task-456',
                title: 'Task without description',
                description: '',
                status: 'todo',
            };
            const taskElement = createTaskElement(task);

            expect(taskElement.querySelector('.task-title').textContent).toBe(task.title);
            expect(taskElement.querySelector('.task-description')).toBeNull(); // No description paragraph
        });

        it('ФТ-03: должен санитизировать название и описание задачи для предотвращения XSS', () => {
            const task = {
                id: 'task-789',
                title: 'Malicious <script>alert("XSS")</script> Title',
                description: 'Description with <b>bold</b> text and <img src="x" onerror="alert(\'XSS\')">',
                status: 'todo',
            };
            const taskElement = createTaskElement(task);

            // Check innerHTML to ensure tags are escaped, not rendered
            expect(taskElement.querySelector('.task-title').innerHTML).not.toContain('<script>');
            expect(taskElement.querySelector('.task-title').innerHTML).toContain('&lt;script&gt;');
            expect(taskElement.querySelector('.task-title').textContent).toBe('Malicious <script>alert("XSS")</script> Title'); // textContent gives the unescaped text

            expect(taskElement.querySelector('.task-description').innerHTML).not.toContain('<b>');
            expect(taskElement.querySelector('.task-description').innerHTML).toContain('&lt;b&gt;bold&lt;/b&gt;');
            expect(taskElement.querySelector('.task-description').textContent).toBe('Description with <b>bold</b> text and <img src="x" onerror="alert(\'XSS\')">');
        });

        it('должен содержать кнопку удаления задачи', () => {
            const task = { id: 'task-1', title: 'Task', description: '', status: 'todo' };
            const taskElement = createTaskElement(task);
            const deleteButton = taskElement.querySelector('.delete-task-btn');
            expect(deleteButton).not.toBeNull();
            expect(deleteButton.getAttribute('aria-label')).toBe('Удалить задачу');
            expect(deleteButton.textContent).toBe('×');
        });
    });

    // Note: Functions like renderBoard, showValidationError, hideValidationError, hideModal,
    // updateTaskCounters, filterTasksByStatus are not provided in the `src/ui.js` snippet,
    // so they cannot be tested here.
});
