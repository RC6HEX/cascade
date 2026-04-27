import { describe, it, expect, beforeEach } from 'vitest';
import { initializeTasks, getTasks, addTask, updateTaskStatus } from '../src/task.js';

describe('task.js', () => {
    beforeEach(() => {
        // Reset tasks before each test
        initializeTasks([]);
    });

    describe('initializeTasks', () => {
        it('должен инициализировать список задач', () => {
            const initial = [{ id: 'a', title: 'Initial Task', description: '', status: 'todo' }];
            initializeTasks(initial);
            expect(getTasks()).toEqual(initial);
        });
    });

    describe('getTasks', () => {
        it('должен возвращать текущий список задач', () => {
            const task1 = addTask('Task 1', 'Description 1');
            const task2 = addTask('Task 2', '');
            expect(getTasks()).toEqual([task1, task2]);
        });

        it('должен возвращать пустой массив, если задач нет', () => {
            expect(getTasks()).toEqual([]);
        });
    });

    // ФТ-03: Создание новой задачи
    describe('addTask', () => {
        it('ФТ-03: должен создавать и добавлять новую задачу со статусом "К выполнению"', () => {
            const title = 'New Task';
            const description = 'This is a new task description.';
            const newTask = addTask(title, description);

            expect(newTask).toHaveProperty('id');
            expect(typeof newTask.id).toBe('string');
            expect(newTask.title).toBe(title);
            expect(newTask.description).toBe(description);
            expect(newTask.status).toBe('todo'); // New tasks always start as 'todo'

            const tasks = getTasks();
            expect(tasks).toHaveLength(1);
            expect(tasks[0]).toEqual(newTask);
        });

        it('ФТ-03: должен создавать задачу с пустым описанием', () => {
            const title = 'Task without description';
            const description = '';
            const newTask = addTask(title, description);

            expect(newTask.title).toBe(title);
            expect(newTask.description).toBe('');
            expect(newTask.status).toBe('todo');
            expect(getTasks()).toHaveLength(1);
        });

        it('ФТ-03: должен корректно обрабатывать название и описание со спецсимволами и HTML-тегами', () => {
            const title = 'Task with <script>alert("XSS")</script> & special chars!';
            const description = 'Description with <b>bold</b> and &amp; entities.';
            const newTask = addTask(title, description);

            expect(newTask.title).toBe(title);
            expect(newTask.description).toBe(description);
            expect(newTask.status).toBe('todo');
            expect(getTasks()).toHaveLength(1);
        });

        it('должен генерировать уникальные ID для задач', () => {
            const task1 = addTask('Task 1', '');
            const task2 = addTask('Task 2', '');
            expect(task1.id).not.toBe(task2.id);
        });
    });

    // ФТ-05: Изменение статуса задачи
    describe('updateTaskStatus', () => {
        it('ФТ-05: должен обновлять статус существующей задачи', () => {
            const task = addTask('Task to update', '');
            const taskId = task.id;

            updateTaskStatus(taskId, 'in-progress');
            expect(getTasks()[0].status).toBe('in-progress');

            updateTaskStatus(taskId, 'done');
            expect(getTasks()[0].status).toBe('done');
        });

        it('ФТ-05: не должен изменять статус, если задача с указанным ID не найдена', () => {
            addTask('Existing Task', '');
            const initialTasks = getTasks();
            const nonExistentId = 'non-existent-id';

            updateTaskStatus(nonExistentId, 'done');
            expect(getTasks()).toEqual(initialTasks); // Tasks array should remain unchanged
        });
    });
});
