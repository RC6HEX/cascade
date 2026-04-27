import { initCalculator } from './calculator.js';
import { initHistory, addHistoryEntry } from './history.js';

/**
 * @description Renders the initial UI and initializes modules when the DOM is ready.
 * Implements ФТ-11.
 */
function main() {
    const appRoot = document.getElementById('app-root');
    if (!appRoot) {
        console.error('Root element #app-root not found!');
        return;
    }

    appRoot.innerHTML = `
        <div id="app-container">
            <section class="calculator" aria-labelledby="calculator-heading">
                <h1 id="calculator-heading" class="calculator-header">QuickCalc</h1>
                <div class="display" role="status" aria-live="polite">0</div>
                <div class="buttons-grid">
                    <button class="btn utility" data-action="clear">C</button>
                    <button class="btn utility" data-action="toggle-sign">+/-</button>
                    <button class="btn utility" data-action="percent">%</button>
                    <button class="btn operator" data-action="operator" data-value="÷" aria-label="Деление">÷</button>
                    
                    <button class="btn" data-action="number" data-value="7">7</button>
                    <button class="btn" data-action="number" data-value="8">8</button>
                    <button class="btn" data-action="number" data-value="9">9</button>
                    <button class="btn operator" data-action="operator" data-value="×" aria-label="Умножение">×</button>

                    <button class="btn" data-action="number" data-value="4">4</button>
                    <button class="btn" data-action="number" data-value="5">5</button>
                    <button class="btn" data-action="number" data-value="6">6</button>
                    <button class="btn operator" data-action="operator" data-value="−" aria-label="Вычитание">−</button>

                    <button class="btn" data-action="number" data-value="1">1</button>
                    <button class="btn" data-action="number" data-value="2">2</button>
                    <button class="btn" data-action="number" data-value="3">3</button>
                    <button class="btn operator" data-action="operator" data-value="+" aria-label="Сложение">+</button>

                    <button class="btn span-two" data-action="number" data-value="0">0</button>
                    <button class="btn" data-action="decimal" data-value=".">.</button>
                    <button class="btn operator" data-action="equals" aria-label="Равно">=</button>
                </div>
            </section>
            <section class="history-panel" aria-labelledby="history-heading">
                <h2 id="history-heading" class="history-header">История</h2>
                <ul id="history-list"></ul>
            </section>
        </div>
    `;

    const displayElement = document.querySelector('.display');
    const buttonsContainer = document.querySelector('.buttons-grid');
    const historyListElement = document.getElementById('history-list');

    initHistory(historyListElement);
    initCalculator(displayElement, buttonsContainer, addHistoryEntry);
}

document.addEventListener('DOMContentLoaded', main);
