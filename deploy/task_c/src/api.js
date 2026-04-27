const API_URL = 'https://open.er-api.com/v6/latest/USD';
const CACHE_KEY = 'currencyX_cache';
const CACHE_TTL_MS = 3600 * 1000; // 1 час

/**
 * @typedef {object} RatesData
 * @property {object} rates - Объект с курсами валют.
 * @property {number} timestamp - Временная метка сохранения данных.
 * @property {boolean} [isStale] - Флаг, указывающий, что данные устарели, но используются из-за ошибки API.
 */

/**
 * Получает курсы валют из API или кеша.
 * Реализует ФТ-01, ФТ-05, ФТ-06.
 * @returns {Promise<RatesData>} Объект с данными о курсах.
 * @throws {Error} Если не удалось получить данные ни из API, ни из кеша.
 */
export async function fetchRates() {
    const cachedData = getFromCache();

    if (cachedData && Date.now() - cachedData.timestamp < CACHE_TTL_MS) {
        console.log('Using fresh data from cache.');
        return cachedData;
    }

    try {
        console.log('Fetching new data from API...');
        const response = await fetch(API_URL);
        if (!response.ok) {
            throw new Error(`API request failed with status ${response.status}`);
        }
        const data = await response.json();
        if (data.result !== 'success') {
            throw new Error('API returned an error.');
        }

        const ratesData = {
            rates: data.rates,
            timestamp: new Date(data.time_last_update_utc).getTime(),
        };

        saveToCache(ratesData);
        return ratesData;
    } catch (error) {
        console.error('Failed to fetch from API:', error);
        if (cachedData) {
            console.log('API failed, using stale data from cache.');
            return { ...cachedData, isStale: true };
        }
        throw new Error('Не удалось загрузить курсы валют. Проверьте подключение к сети.');
    }
}

/**
 * Получает данные из localStorage.
 * @returns {RatesData | null}
 */
function getFromCache() {
    try {
        const cached = localStorage.getItem(CACHE_KEY);
        return cached ? JSON.parse(cached) : null;
    } catch (e) {
        console.warn('Could not read from localStorage:', e);
        return null;
    }
}

/**
 * Сохраняет данные в localStorage.
 * Реализует часть ФТ-06.
 * @param {RatesData} data - Данные для сохранения.
 */
function saveToCache(data) {
    try {
        localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    } catch (e) {
        console.warn('Could not write to localStorage:', e);
    }
}
