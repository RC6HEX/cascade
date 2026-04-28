/**
 * Основной класс калькулятора, реализующий логику работы
 * @implements ФТ-01
 * @implements ФТ-02
 * @implements ФТ-03
 * @implements ФТ-04
 * @implements ФТ-06
 */
export class Calculator {
  constructor() {
    this.currentInput = '';
    this.previousInput = '';
    this.operation = null;
    this.shouldResetInput = false;
    this.history = [];
    this.maxHistoryItems = 10;
    
    this.inputElement = null;
    this.resultElement = null;
    this.historyListElement = null;
  }

  init() {
    this.cacheElements();
    this.setupEventListeners();
    this.updateDisplay();
  }

  /**
   * Кеширует DOM-элементы
   */
  cacheElements() {
    this.inputElement = document.querySelector('.calculator-input');
    this.resultElement = document.querySelector('.calculator-result');
    this.historyListElement = document.querySelector('.history-list');
  }

  /**
   * Настраивает обработчики событий для кнопок
   */
  setupEventListeners() {
    document.querySelector('.calculator-buttons').addEventListener('click', (e) => {
      const button = e.target.closest('.calculator-button');
      if (!button) return;

      const action = button.dataset.action;
      const value = button.dataset.value;

      switch (action) {
        case 'number':
          this.appendNumber(value);
          break;
        case 'decimal':
          this.appendDecimal();
          break;
        case 'add':
        case 'subtract':
        case 'multiply':
        case 'divide':
          this.setOperation(action);
          break;
        case 'equals':
          this.calculate();
          break;
        case 'clear':
          this.clear();
          break;
        case 'clear-all':
          this.clearAll();
          break;
        case 'backspace':
          this.backspace();
          break;
      }

      this.updateDisplay();
    });
  }

  /**
   * Добавляет цифру к текущему вводу
   * @param {string} number - Цифра для добавления
   */
  appendNumber(number) {
    if (this.shouldResetInput) {
      this.currentInput = '';
      this.shouldResetInput = false;
    }
    
    if (this.currentInput === '0') {
      this.currentInput = number;
    } else {
      this.currentInput += number;
    }
  }

  /**
   * Добавляет десятичную точку к текущему вводу
   */
  appendDecimal() {
    if (this.shouldResetInput) {
      this.currentInput = '0';
      this.shouldResetInput = false;
    }
    
    if (this.currentInput.includes('.')) return;
    
    if (this.currentInput === '') {
      this.currentInput = '0';
    }
    
    this.currentInput += '.';
  }

  /**
   * Устанавливает операцию для вычисления
   * @param {string} operation - Операция (add, subtract, multiply, divide)
   */
  setOperation(operation) {
    if (this.currentInput === '' && this.previousInput === '') return;
    
    if (this.previousInput !== '' && this.currentInput !== '') {
      this.calculate();
    }
    
    this.operation = operation;
    this.previousInput = this.currentInput || this.previousInput;
    this.currentInput = '';
  }

  /**
   * Выполняет вычисление
   */
  calculate() {
    if (this.operation === null || this.currentInput === '' || this.previousInput === '') return;
    
    const prev = parseFloat(this.previousInput);
    const current = parseFloat(this.currentInput);
    let result;
    
    try {
      switch (this.operation) {
        case 'add':
          result = prev + current;
          break;
        case 'subtract':
          result = prev - current;
          break;
        case 'multiply':
          result = prev * current;
          break;
        case 'divide':
          if (current === 0) {
            throw new Error('Деление на ноль');
          }
          result = prev / current;
          break;
        default:
          return;
      }
      
      this.addToHistory(prev, current, this.operation, result);
      this.currentInput = result.toString();
      this.operation = null;
      this.previousInput = '';
      this.shouldResetInput = true;
      this.clearError();
    } catch (error) {
      this.showError(error.message);
    }
  }

  /**
   * Очищает текущий ввод
   */
  clear() {
    this.currentInput = '';
    this.clearError();
  }

  /**
   * Полностью сбрасывает калькулятор
   */
  clearAll() {
    this.currentInput = '';
    this.previousInput = '';
    this.operation = null;
    this.clearError();
  }

  /**
   * Удаляет последний символ из текущего ввода
   */
  backspace() {
    this.currentInput = this.currentInput.slice(0, -1);
    if (this.currentInput === '') {
      this.clearError();
    }
  }

  /**
   * Добавляет операцию в историю
   * @param {number} num1 - Первое число
   * @param {number} num2 - Второе число
   * @param {string} operation - Операция
   * @param {number} result - Результат
   */
  addToHistory(num1, num2, operation, result) {
    const operationsMap = {
      'add': '+',
      'subtract': '−',
      'multiply': '×',
      'divide': '÷'
    };
    
    const operationSymbol = operationsMap[operation];
    const historyItem = {
      expression: `${num1} ${operationSymbol} ${num2}`,
      result: result
    };
    
    this.history.unshift(historyItem);
    
    if (this.history.length > this.maxHistoryItems) {
      this.history.pop();
    }
  }

  /**
   * Обновляет отображение калькулятора
   */
  updateDisplay() {
    this.inputElement.value = this.currentInput || '0';
    this.inputElement.classList.toggle('error', this.inputElement.classList.contains('error'));
    
    if (this.operation !== null) {
      const operationsMap = {
        'add': '+',
        'subtract': '−',
        'multiply': '×',
        'divide': '÷'
      };
      this.resultElement.textContent = `${this.previousInput} ${operationsMap[this.operation]}`;
    } else {
      this.resultElement.textContent = '';
    }
    
    this.updateHistoryDisplay();
  }

  /**
   * Обновляет отображение истории
   */
  updateHistoryDisplay() {
    this.historyListElement.innerHTML = '';
    
    this.history.forEach(item => {
      const li = document.createElement('li');
      li.className = 'history-item';
      
      const expressionSpan = document.createElement('span');
      expressionSpan.className = 'history-expression';
      expressionSpan.textContent = item.expression;
      
      const resultSpan = document.createElement('span');
      resultSpan.className = 'history-result';
      resultSpan.textContent = item.result.toLocaleString('ru-RU');
      
      li.appendChild(expressionSpan);
      li.appendChild(resultSpan);
      this.historyListElement.appendChild(li);
    });
  }

  /**
   * Показывает сообщение об ошибке
   * @param {string} message - Текст ошибки
   */
  showError(message) {
    this.currentInput = message;
    this.inputElement.classList.add('error');
    this.shouldResetInput = true;
  }

  /**
   * Сбрасывает состояние ошибки
   */
  clearError() {
    if (this.inputElement.classList.contains('error')) {
      this.inputElement.classList.remove('error');
      this.currentInput = '';
    }
  }
}
