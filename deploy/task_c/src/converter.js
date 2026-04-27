export const SUPPORTED_CURRENCIES = ['USD', 'EUR', 'RUB', 'GBP', 'JPY', 'CNY', 'TRY', 'KZT', 'BYN', 'GEL', 'CHF', 'CAD'];

/**
 * Создает и возвращает HTML-структуру конвертера.
 * @returns {HTMLElement} Корневой элемент компонента конвертера.
 */
export function createConverterElement() {
    const container = document.createElement('div');
    container.className = 'converter-form';
    container.innerHTML = `
        <div class="status-message" id="status-message" role="alert"></div>
        
        <div class="currency-row">
            <div class="field-group">
                <label for="from-currency">У меня есть</label>
                <div class="input-wrapper">
                    <select id="from-currency" name="from-currency" aria-label="Исходная валюта"></select>
                    <input type="number" id="from-amount" name="from-amount" value="100" min="0" step="any" aria-label="Сумма в исходной валюте">
                </div>
            </div>
        </div>

        <div class="swap-container">
            <button id="swap-button" type="button" aria-label="Поменять валюты местами">⇄</button>
        </div>

        <div class="currency-row">
            <div class="field-group">
                <label for="to-currency">Хочу приобрести</label>
                <div class="input-wrapper">
                    <select id="to-currency" name="to-currency" aria-label="Целевая валюта"></select>
                    <input type="number" id="to-amount" name="to-amount" readonly aria-label="Сумма в целевой валюте" placeholder="Результат">
                </div>
            </div>
        </div>

        <div class="result-display">
            <p class="rate" id="rate-display"></p>
        </div>
    `;

    const fromSelect = container.querySelector('#from-currency');
    const toSelect = container.querySelector('#to-currency');

    SUPPORTED_CURRENCIES.forEach(currency => {
        const option1 = new Option(currency, currency);
        const option2 = new Option(currency, currency);
        fromSelect.add(option1);
        toSelect.add(option2);
    });

    fromSelect.value = 'USD';
    toSelect.value = 'EUR';

    return container;
}

/**
 * Рассчитывает результат конвертации.
 * Реализует ФТ-03.
 * @param {number} amount - Сумма для конвертации.
 * @param {string} fromCurrency - Код исходной валюты.
 * @param {string} toCurrency - Код целевой валюты.
 * @param {object} rates - Объект с курсами валют относительно USD.
 * @returns {number} Сконвертированная сумма.
 */
export function calculateConversion(amount, fromCurrency, toCurrency, rates) {
    // Граничные случаи ФТ-03
    if (!amount || amount < 0 || !fromCurrency || !toCurrency || !rates) {
        return 0;
    }
    if (fromCurrency === toCurrency) {
        return amount;
    }

    const fromRate = rates[fromCurrency];
    const toRate = rates[toCurrency];
    
    // Базовая валюта API - USD. Курс USD к USD равен 1.
    // Формула: (Сумма / Курс_исходной_валюты_к_базовой) * Курс_целевой_валюты_к_базовой
    const result = (amount / fromRate) * toRate;
    return result;
}

/**
 * Форматирует число для отображения.
 * @param {number} number - Число для форматирования.
 * @returns {string} Отформатированная строка.
 */
export function formatNumber(number) {
    if (number === 0) return '0';
    // Отображаем до 4 знаков после запятой для точности, но убираем незначащие нули
    return parseFloat(number.toFixed(4)).toLocaleString('ru-RU', {
        maximumFractionDigits: 4
    });
}
