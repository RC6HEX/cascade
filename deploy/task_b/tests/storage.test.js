// @vitest-environment happy-dom

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadTasks, saveTasks } from '../src/storage.js';

const STORAGE_KEY = 'taskboardData';

describe('storage.js', () => {
    beforeEach(() => {
        localStorage.clear();
        vi.spyOn(console, 'error').mockImplementation(() => {}); // Suppress console.error for expected errors
    });

    // ФТ-01: Загрузка задач из локального хранилища
    describe('loadTasks', () => {
        it('ФТ-01: должен загружать задачи из localStorage, если они существуют и валидны', () => {
            const mockTasks = [
                { id: '1', title: 'Task 1', description: 'Desc 1', status: 'todo' },
                { id: '2', title: 'Task 2', description: 'Desc 2', status: 'done' },
            ];
            localStorage.setItem(STORAGE_KEY, JSON.stringify(mockTasks));

            const loadedTasks = loadTasks();
            expect(loadedTasks).toEqual(mockTasks);
            expect(console.error).not.toHaveBeenCalled();
        });

        it('ФТ-01: должен возвращать пустой массив, если localStorage пуст', () => {
            const loadedTasks = loadTasks();
            expect(loadedTasks).toEqual([]);
            expect(console.error).not.toHaveBeenCalled();
        });

        it('ФТ-01: должен возвращать пустой массив, если ключ с задачами отсутствует в localStorage', () => {
            localStorage.removeItem(STORAGE_KEY); // Ensure it's absent
            const loadedTasks = loadTasks();
            expect(loadedTasks).toEqual([]);
            expect(console.error).not.toHaveBeenCalled();
        });

        it('ФТ-01: должен возвращать пустой массив и очищать localStorage, если данные имеют невалидный JSON формат', () => {
            localStorage.setItem(STORAGE_KEY, 'not a valid json');
            const loadedTasks = loadTasks();
            expect(loadedTasks).toEqual([]);
            expect(localStorage.getItem(STORAGE_KEY)).toBeNull(); // Should clear invalid data
            expect(console.error).toHaveBeenCalledOnce();
        });

        it('ФТ-01: должен возвращать пустой массив и очищать localStorage, если данные являются валидным JSON, но не массивом', () => {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ id: '1', title: 'Task 1' }));
            const loadedTasks = loadTasks();
            expect(loadedTasks).toEqual([]);
            expect(localStorage.getItem(STORAGE_KEY)).toBeNull(); // Should clear invalid data
            expect(console.error).not.toHaveBeenCalled(); // No error for non-array, just returns empty
        });
    });

    // ФТ-03, ФТ-05, ФТ-06: Сохранение задач в локальное хранилище
    describe('saveTasks', () => {
        it('ФТ-03, ФТ-05, ФТ-06: должен сохранять массив задач в localStorage', () => {
            const mockTasks = [
                { id: '1', title: 'Task 1', description: 'Desc 1', status: 'todo' },
                { id: '2', title: 'Task 2', description: 'Desc 2', status: 'in-progress' },
            ];
            saveTasks(mockTasks);
            expect(localStorage.getItem(STORAGE_KEY)).toEqual(JSON.stringify(mockTasks));
            expect(console.error).not.toHaveBeenCalled();
        });

        it('ФТ-03, ФТ-05, ФТ-06: должен сохранять пустой массив задач в localStorage', () => {
            const mockTasks = [];
            saveTasks(mockTasks);
            expect(localStorage.getItem(STORAGE_KEY)).toEqual(JSON.stringify(mockTasks));
            expect(console.error).not.toHaveBeenCalled();
        });

        it('должен обрабатывать ошибки при сохранении в localStorage', () => {
            // Simulate localStorage quota exceeded error
            vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
                throw new Error('Quota exceeded');
            });

            const mockTasks = [{ id: '1', title: 'Task 1', description: 'Desc 1', status: 'todo' }];
            saveTasks(mockTasks);
            expect(console.error).toHaveBeenCalledOnce();
            expect(console.error).toHaveBeenCalledWith('Failed to save tasks to localStorage:', expect.any(Error));
        });
    });
});
