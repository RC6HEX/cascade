/**
 * Настраивает поддержку клавиатуры для калькулятора
 * @implements ФТ-05
 * @param {Calculator} calculator - Экземпляр калькулятора
 */
export function setupKeyboardSupport(calculator) {
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' && e.target !== calculator.inputElement) return;
    
    const keyActions = {
      '0': () => calculator.appendNumber('0'),
      '1': () => calculator.appendNumber('1'),
      '2': () => calculator.appendNumber('2'),
      '3': () => calculator.appendNumber('3'),
      '4': () => calculator.appendNumber('4'),
      '5': () => calculator.appendNumber('5'),
      '6': () => calculator.appendNumber('6'),
      '7': () => calculator.appendNumber('7'),
      '8': () => calculator.appendNumber('8'),
      '9': () => calculator.appendNumber('9'),
      '.': () => calculator.appendDecimal(),
      ',': () => calculator.appendDecimal(),
      '+': () => calculator.setOperation('add'),
      '-': () => calculator.setOperation('subtract'),
      '*': () => calculator.setOperation('multiply'),
      '/': () => calculator.setOperation('divide'),
      'Enter': () => calculator.calculate(),
      '=': () => calculator.calculate(),
      'Escape': () => calculator.clearAll(),
      'Backspace': () => calculator.backspace(),
      'Delete': () => calculator.clear()
    };
    
    const action = keyActions[e.key];
    if (action) {
      e.preventDefault();
      action();
      calculator.updateDisplay();
    }
  });
}
