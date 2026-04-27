import { describe, it, expect, beforeEach, vi } from 'vitest';
import { fetchRates } from '../src/api.js';

// Mock localStorage
const localStorageMock = (() => {
    let store = {};
    return {
        getItem: vi.fn((key) => store[key] || null),
        setItem: vi.fn((key, value) => { store[key] = value; }),
        removeItem: vi.fn((key) => { delete store[key]; }),
        clear: vi.fn(() => { store = {}; }),
    };
})();

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock });

// Mock global fetch
const mockFetchSuccess = (data, status = 200) =>
    Promise.resolve({
        ok: status >= 200 && status < 300,
        status: status,
        json: () => Promise.resolve(data),
    });

const mockFetchError = (status = 500) =>
    Promise.resolve({
        ok: false,
        status: status,
        json: () => Promise.resolve({ error: 'API error' }),
    });

const mockFetchNetworkError = () => Promise.reject(new TypeError('Network error'));

const MOCK_API_RESPONSE = {
    result: 'success',
    time_last_update_utc: 'Mon, 01 Jan 2024 00:00:00 +0000',
    rates: {
        USD: 1,
        EUR: 0.9,
        GBP: 0.8,
    },
};

const MOCK_CACHED_DATA = {
    rates: {
        USD: 1,
        EUR: 0.95, // Slightly different to distinguish from API
        GBP: 0.85,
    },
    timestamp: new Date('2023-12-31T23:00:00Z').getTime(), // 1 hour before API response
};

describe('fetchRates', () => {
    const CACHE_TTL_MS = 3600 * 1000; // 1 hour

    beforeEach(() => {
        localStorageMock.clear();
        vi.restoreAllMocks(); // Restore all mocks before each test
        vi.useFakeTimers(); // Use fake timers to control Date.now()
        globalThis.fetch = vi.fn(); // Mock fetch for each test
    });

    afterEach(() => {
        vi.useRealTimers(); // Restore real timers after each test
    });

    // ФТ-01: Загрузка и отображение курсов валют при открытии страницы
    it('ФТ-01: Загружает курсы из API и сохраняет в кеш, если кеш отсутствует', async () => {
        vi.setSystemTime(new Date('2024-01-01T00:00:00Z')); // Set current time
        globalThis.fetch.mockImplementation(() => mockFetchSuccess(MOCK_API_RESPONSE));

        const rates = await fetchRates();

        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        expect(globalThis.fetch).toHaveBeenCalledWith('https://open.er-api.com/v6/latest/USD');
        expect(localStorageMock.setItem).toHaveBeenCalledTimes(1);
        expect(localStorageMock.setItem).toHaveBeenCalledWith(
            'currencyX_cache',
            JSON.stringify({
                rates: MOCK_API_RESPONSE.rates,
                timestamp: new Date(MOCK_API_RESPONSE.time_last_update_utc).getTime(),
            })
        );
        expect(rates).toEqual({
            rates: MOCK_API_RESPONSE.rates,
            timestamp: new Date(MOCK_API_RESPONSE.time_last_update_utc).getTime(),
        });
        expect(rates.isStale).toBeUndefined();
    });

    // ФТ-06: Управление кешем курсов валют (свежий кеш)
    it('ФТ-06: Использует свежие данные из кеша, если они не устарели', async () => {
        const freshTimestamp = Date.now(); // Current time
        localStorageMock.setItem('currencyX_cache', JSON.stringify({ ...MOCK_CACHED_DATA, timestamp: freshTimestamp }));
        vi.setSystemTime(freshTimestamp + CACHE_TTL_MS - 1000); // Just before cache expires

        const rates = await fetchRates();

        expect(localStorageMock.getItem).toHaveBeenCalledTimes(1);
        expect(globalThis.fetch).not.toHaveBeenCalled(); // API should not be called
        expect(rates).toEqual({ ...MOCK_CACHED_DATA, timestamp: freshTimestamp });
        expect(rates.isStale).toBeUndefined();
    });

    // ФТ-06: Управление кешем курсов валют (устаревший кеш)
    it('ФТ-06: Загружает новые данные из API, если кеш устарел', async () => {
        const staleTimestamp = Date.now() - CACHE_TTL_MS - 1000; // Cache expired
        localStorageMock.setItem('currencyX_cache', JSON.stringify({ ...MOCK_CACHED_DATA, timestamp: staleTimestamp }));
        globalThis.fetch.mockImplementation(() => mockFetchSuccess(MOCK_API_RESPONSE));
        vi.setSystemTime(Date.now()); // Set current time

        const rates = await fetchRates();

        expect(localStorageMock.getItem).toHaveBeenCalledTimes(1);
        expect(globalThis.fetch).toHaveBeenCalledTimes(1); // API should be called
        expect(localStorageMock.setItem).toHaveBeenCalledTimes(1); // Cache should be updated
        expect(rates).toEqual({
            rates: MOCK_API_RESPONSE.rates,
            timestamp: new Date(MOCK_API_RESPONSE.time_last_update_utc).getTime(),
        });
        expect(rates.isStale).toBeUndefined();
    });

    // ФТ-05: Обработка недоступности API и отсутствия сети (API ошибка, есть устаревший кеш)
    it('ФТ-05: Использует устаревшие данные из кеша и помечает их как isStale при ошибке API', async () => {
        const staleTimestamp = Date.now() - CACHE_TTL_MS - 1000; // Cache expired
        localStorageMock.setItem('currencyX_cache', JSON.stringify({ ...MOCK_CACHED_DATA, timestamp: staleTimestamp }));
        globalThis.fetch.mockImplementation(() => mockFetchError(500)); // Simulate API error
        vi.setSystemTime(Date.now());

        const rates = await fetchRates();

        expect(localStorageMock.getItem).toHaveBeenCalledTimes(1);
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        expect(localStorageMock.setItem).not.toHaveBeenCalled(); // Cache should not be updated on API error
        expect(rates).toEqual({ ...MOCK_CACHED_DATA, timestamp: staleTimestamp, isStale: true });
    });

    // ФТ-05: Обработка недоступности API и отсутствия сети (API ошибка, нет кеша)
    it('ФТ-05: Выбрасывает ошибку, если API недоступен и нет кеша', async () => {
        globalThis.fetch.mockImplementation(() => mockFetchError(500)); // Simulate API error
        vi.setSystemTime(Date.now());

        await expect(fetchRates()).rejects.toThrow('Не удалось загрузить курсы валют. Проверьте подключение к сети.');
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        expect(localStorageMock.getItem).toHaveBeenCalledTimes(1);
        expect(localStorageMock.setItem).not.toHaveBeenCalled();
    });

    // ФТ-05: Обработка недоступности API и отсутствия сети (сетевая ошибка, нет кеша)
    it('ФТ-05: Выбрасывает ошибку при сетевой ошибке и отсутствии кеша', async () => {
        globalThis.fetch.mockImplementation(() => mockFetchNetworkError()); // Simulate network error
        vi.setSystemTime(Date.now());

        await expect(fetchRates()).rejects.toThrow('Не удалось загрузить курсы валют. Проверьте подключение к сети.');
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        expect(localStorageMock.getItem).toHaveBeenCalledTimes(1);
        expect(localStorageMock.setItem).not.toHaveBeenCalled();
    });

    // ФТ-06: Граничный случай - localStorage недоступен (getItem выбрасывает ошибку)
    it('ФТ-06: Работает без кеширования, если localStorage.getItem недоступен', async () => {
        localStorageMock.getItem.mockImplementation(() => { throw new Error('localStorage error'); });
        globalThis.fetch.mockImplementation(() => mockFetchSuccess(MOCK_API_RESPONSE));
        vi.setSystemTime(new Date('2024-01-01T00:00:00Z'));

        const rates = await fetchRates();

        expect(localStorageMock.getItem).toHaveBeenCalledTimes(1);
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        expect(localStorageMock.setItem).not.toHaveBeenCalled(); // Should not try to set if get failed
        expect(rates).toEqual({
            rates: MOCK_API_RESPONSE.rates,
            timestamp: new Date(MOCK_API_RESPONSE.time_last_update_utc).getTime(),
        });
    });

    // ФТ-06: Граничный случай - localStorage недоступен (setItem выбрасывает ошибку)
    it('ФТ-06: Работает без кеширования, если localStorage.setItem недоступен', async () => {
        localStorageMock.setItem.mockImplementation(() => { throw new Error('localStorage error'); });
        globalThis.fetch.mockImplementation(() => mockFetchSuccess(MOCK_API_RESPONSE));
        vi.setSystemTime(new Date('2024-01-01T00:00:00Z'));

        const rates = await fetchRates();

        expect(localStorageMock.getItem).toHaveBeenCalledTimes(1);
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
        expect(localStorageMock.setItem).toHaveBeenCalledTimes(1); // It tries to set, but fails
        expect(rates).toEqual({
            rates: MOCK_API_RESPONSE.rates,
            timestamp: new Date(MOCK_API_RESPONSE.time_last_update_utc).getTime(),
        });
    });

    it('Should throw error if API response result is not "success"', async () => {
        globalThis.fetch.mockImplementation(() => mockFetchSuccess({ result: 'error' }));
        vi.setSystemTime(Date.now());

        await expect(fetchRates()).rejects.toThrow('API returned an error.');
        expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });
});
