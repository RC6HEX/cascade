import { addHistoryEntry } from './history.js';

let displayElement;
let buttonsContainer;
let onHistoryUpdate;

let firstOperand = null;
let secondOperand = null;
let currentOperation = null;
let shouldResetDisplay = false;
let isErrorState = false;

const operations = {
    '+': (a, b) => a + b,
    '−': (a, b) => a - b,
    '×': (a, b) => a * b,
    '÷': (a, b) => {
        if (b === 0) {
            return 'error';
        }
        return a / b;
    },
};

/**
 * @description Initializes the calculator module, sets up DOM elements and event listeners.
 * @param {HTMLElement} displayEl - The element to display output.
 * @param {HTMLElement} buttonsEl - The container for calculator buttons.
 * @param {Function} historyCallback - Callback to update history.
 */
export function initCalculator(displayEl, buttonsEl, historyCallback) {
    displayElement = displayEl;
    buttonsContainer = buttonsEl;
    onHistoryUpdate = historyCallback;

    buttonsContainer.addEventListener('click', handleButtonClick);
    document.addEventListener('keydown', handleKeyboardInput);
    resetCalculator();
}

/**
 * @description Handles clicks on calculator buttons using event delegation.
 * @param {Event} event - The click event.
 */
function handleButtonClick(event) {
    const button = event.target.closest('button');
    if (!button) return;

    const { action, value } = button.dataset;

    if (isErrorState && action !== 'clear') return;

    switch (action) {
        case 'number':
            appendNumber(value);
            break;
        case 'decimal':
            appendDecimal();
            break;
        case 'operator':
            setOperation(value);
            break;
        case 'equals':
            evaluate();
            break;
        case 'clear':
            resetCalculator();
            break;
        case 'toggle-sign':
            toggleSign();
            break;
        case 'percent':
            calculatePercent();
            break;
    }
}

/**
 * @description Handles keyboard input for calculator functionality.
 * Implements ФТ-09, ФТ-10.
 * @param {KeyboardEvent} event - The keydown event.
 */
function handleKeyboardInput(event) {
    if (isErrorState && event.key !== 'Escape') return;

    if (event.key >= '0' && event.key <= '9') {
        appendNumber(event.key);
    } else if (event.key === '.') {
        appendDecimal();
    } else if (event.key === 'Enter' || event.key === '=') {
        event.preventDefault();
        evaluate();
    } else if (event.key === 'Escape') {
        resetCalculator();
    } else if (event.key === 'Backspace') {
        deleteLastChar();
    } else if (['+', '-', '*', '/'].includes(event.key)) {
        event.preventDefault();
        const opMap = { '+': '+', '-': '−', '*': '×', '/': '÷' };
        setOperation(opMap[event.key]);
    }
}

/**
 * @description Appends a number to the current display value.
 * Implements ФТ-09.
 * @param {string} number - The number to append.
 */
function appendNumber(number) {
    if (displayElement.textContent === '0' || shouldResetDisplay) {
        displayElement.textContent = number;
        shouldResetDisplay = false;
    } else {
        displayElement.textContent += number;
    }
}

/**
 * @description Appends a decimal point if one doesn't already exist.
 */
function appendDecimal() {
    if (shouldResetDisplay) {
        displayElement.textContent = '0.';
        shouldResetDisplay = false;
        return;
    }
    if (!displayElement.textContent.includes('.')) {
        displayElement.textContent += '.';
    }
}

/**
 * @description Sets the arithmetic operation to be performed.
 * @param {string} op - The operator symbol ('+', '−', '×', '÷').
 */
function setOperation(op) {
    if (currentOperation !== null) {
        evaluate();
    }
    firstOperand = parseFloat(displayElement.textContent);
    currentOperation = op;
    shouldResetDisplay = true;
}

/**
 * @description Resets the calculator to its initial state.
 * Implements ФТ-06.
 */
function resetCalculator() {
    displayElement.textContent = '0';
    firstOperand = null;
    secondOperand = null;
    currentOperation = null;
    shouldResetDisplay = false;
    isErrorState = false;
    displayElement.classList.remove('error');
}

/**
 * @description Deletes the last character from the display.
 * Implements ФТ-10.
 */
function deleteLastChar() {
    if (shouldResetDisplay) return;
    displayElement.textContent = displayElement.textContent.slice(0, -1);
    if (displayElement.textContent === '' || displayElement.textContent === '-') {
        displayElement.textContent = '0';
    }
}

/**
 * @description Toggles the sign of the current number on the display.
 */
function toggleSign() {
    if (displayElement.textContent !== '0') {
        displayElement.textContent = (parseFloat(displayElement.textContent) * -1).toString();
    }
}

/**
 * @description Calculates the percentage of the current number.
 */
function calculatePercent() {
    displayElement.textContent = (parseFloat(displayElement.textContent) / 100).toString();
}

/**
 * @description Performs the calculation and updates the display.
 * Implements ФТ-01, ФТ-02, ФТ-03, ФТ-04, ФТ-05, ФТ-07.
 */
function evaluate() {
    if (currentOperation === null || shouldResetDisplay) return;
    
    secondOperand = parseFloat(displayElement.textContent);

    const result = performCalculation(firstOperand, secondOperand, currentOperation);

    if (result === 'error') {
        handleError();
        return;
    }

    const formattedResult = parseFloat(result.toPrecision(15));
    displayElement.textContent = formattedResult;
    
    const historyEntry = `${firstOperand} ${currentOperation} ${secondOperand} = ${formattedResult}`;
    onHistoryUpdate(historyEntry);

    firstOperand = formattedResult;
    currentOperation = null;
    shouldResetDisplay = true;
}

/**
 * @description Core calculation logic.
 * @param {number} a - First operand.
 * @param {number} b - Second operand.
 * @param {string} op - Operator.
 * @returns {number|string} The result or 'error'.
 */
function performCalculation(a, b, op) {
    if (op === '÷' && b === 0) {
        return 'error';
    }
    return operations[op](a, b);
}

/**
 * @description Handles the division by zero error state.
 * Implements ФТ-05.
 */
function handleError() {
    displayElement.textContent = 'Ошибка: деление на ноль';
    displayElement.classList.add('error');
    isErrorState = true;
    firstOperand = null;
    secondOperand = null;
    currentOperation = null;
}
