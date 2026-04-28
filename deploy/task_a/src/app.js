import { Calculator } from './calculator.js';
import { setupKeyboardSupport } from './keyboard.js';

document.addEventListener('DOMContentLoaded', () => {
  const calculator = new Calculator();
  calculator.init();
  setupKeyboardSupport(calculator);
});
