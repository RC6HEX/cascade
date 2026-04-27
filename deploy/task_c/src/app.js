import { fetchRates } from './api.js';
import { createConverterElement, calculateConversion, formatNumber } from './converter.js';

class CurrencyConverterApp {
    constructor(rootElement) {
        this.root = rootElement;
        this.ratesData = null;
        this.elements = {};
    }

    /**
     * Инициализация приложения: отрисовка UI и загрузка данных.
     * Реализует ФТ-01.
     */
    async init() {
        this.renderInitialUI();
        try {
            this.ratesData = await fetchRates();
            this.enableForm();
            this.setupEventListeners();
            this.updateConversion();
            if (this.ratesData.isStale) {
                this.showStaleDataWarning(this.ratesData.timestamp);
            }
        } catch (error) {
            this.showFatalError(error.message);
        }
    }

    /**
     * Отрисовывает начальный HTML-скелет приложения.
     */
    renderInitialUI() {
        const converterEl = createConverterElement();
        this.root.appendChild(converterEl);

        this.elements = {
            fromCurrency: document.getElementById('from-currency'),
            toCurrency: document.getElementById('to-currency'),
            fromAmount: document.getElementById('from-amount'),
            toAmount: document.getElementById('to-amount'),
            swapButton: document.getElementById('swap-button'),
            rateDisplay: document.getElementById('rate-display'),
            statusMessage: document.getElementById('status-message'),
            form: converterEl,
        };
        
        this.elements.statusMessage.textContent = 'Загрузка актуальных курсов...';
    }

    /**
     * Включает элементы формы после успешной загрузки данных.
     */
    enableForm() {
        const formElements = this.elements.form.querySelectorAll('input, select, button');
        formElements.forEach(el => el.disabled = false);
        this.elements.statusMessage.style.display = 'none';
    }

    /**
     * Устанавливает обработчики событий на элементы управления.
     */
    setupEventListeners() {
        this.elements.fromAmount.addEventListener('input', () => this.updateConversion());
        this.elements.fromCurrency.addEventListener('change', () => this.updateConversion());
        this.elements.toCurrency.addEventListener('change', () => this.updateConversion());
        this.elements.swapButton.addEventListener('click', () => this.swapCurrencies());
    }

    /**
     * Обновляет результат конвертации и отображаемый курс.
     * Реализует ФТ-02 и ФТ-03.
     */
    updateConversion() {
        const fromCurrency = this.elements.fromCurrency.value;
        const toCurrency = this.elements.toCurrency.value;
        
        // Обработка нечислового ввода (граничный случай ФТ-03)
        const fromAmountValue = this.elements.fromAmount.value.replace(',', '.');
        const fromAmount = Math.abs(parseFloat(fromAmountValue)) || 0;

        const convertedAmount = calculateConversion(fromAmount, fromCurrency, toCurrency, this.ratesData.rates);
        this.elements.toAmount.value = formatNumber(convertedAmount);

        this.updateRateDisplay(fromCurrency, toCurrency);
    }

    /**
     * Обновляет текстовое поле с текущим курсом обмена.
     * @param {string} from - Исходная валюта.
     * @param {string} to - Целевая валюта.
     */
    updateRateDisplay(from, to) {
        const rate = calculateConversion(1, from, to, this.ratesData.rates);
        this.elements.rateDisplay.textContent = `1 ${from} = ${formatNumber(rate)} ${to}`;
    }

    /**
     * Меняет местами исходную и целевую валюты.
     * Реализует ФТ-04.
     */
    swapCurrencies() {
        const fromValue = this.elements.fromCurrency.value;
        this.elements.fromCurrency.value = this.elements.toCurrency.value;
        this.elements.toCurrency.value = fromValue;
        this.updateConversion();
    }

    /**
     * Показывает предупреждение об использовании устаревших данных.
     * Реализует ФТ-05.
     * @param {number} timestamp - Временная метка кеша.
     */
    showStaleDataWarning(timestamp) {
        const date = new Date(timestamp).toLocaleString('ru-RU');
        this.elements.statusMessage.textContent = `Курс от ${date}. Актуальные данные временно недоступны.`;
        this.elements.statusMessage.className = 'status-message warning';
        this.elements.statusMessage.style.display = 'block';
    }

    /**
     * Показывает критическую ошибку (например, при первом запуске без сети).
     * Реализует ФТ-05 (граничный случай).
     * @param {string} message - Сообщение об ошибке.
     */
    showFatalError(message) {
        this.elements.statusMessage.textContent = message;
        this.elements.statusMessage.className = 'status-message error';
        this.elements.statusMessage.style.display = 'block';

        const formElements = this.elements.form.querySelectorAll('input, select, button');
        formElements.forEach(el => el.disabled = true);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const rootElement = document.getElementById('converter-root');
    if (rootElement) {
        const app = new CurrencyConverterApp(rootElement);
        app.init();
    } else {
        console.error('Root element #converter-root not found.');
    }
});
