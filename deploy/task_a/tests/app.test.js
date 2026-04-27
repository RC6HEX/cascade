import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { main } from '../src/app.js';
import * as calculatorModule from '../src/calculator.js';
import * as historyModule from '../src/history.js';

// @vitest-environment happy-dom

describe('app.js', () => {
    let appRoot;

    beforeEach(() => {
        // Create a root element for the app
        appRoot = document.createElement('div');
        appRoot.id = 'app-root';
        document.body.appendChild(appRoot);

        // Mock dependencies
        vi.spyOn(calculatorModule, 'initCalculator').mockImplementation(() => {});
        vi.spyOn(historyModule, 'initHistory').mockImplementation(() => {});
    });

    afterEach(() => {
        // Clean up the DOM
        document.body.removeChild(appRoot);
        vi.restoreAllMocks();
    });

    it('ФТ-11: отображает интерфейс калькулятора при загрузке', () => {
        main();

        // Check if the main container is rendered
        const appContainer = appRoot.querySelector('#app-container');
        expect(appContainer).not.toBeNull();

        // Check for calculator heading
        const calculatorHeading = appRoot.querySelector('#calculator-heading');
        expect(calculatorHeading).not.toBeNull();
        expect(calculatorHeading.textContent).toBe('QuickCalc');

        // Check for display element and its initial value
        const display = appRoot.querySelector('.display');
        expect(display).not.toBeNull();
        expect(display.textContent).toBe('0');

        // Check for buttons grid
        const buttonsGrid = appRoot.querySelector('.buttons-grid');
        expect(buttonsGrid).not.toBeNull();
        expect(buttonsGrid.children.length).toBeGreaterThan(0); // Ensure buttons are present

        // Check for history panel
        const historyPanel = appRoot.querySelector('.history-panel');
        expect(historyPanel).not.toBeNull();
        const historyHeading = historyPanel.querySelector('#history-heading');
        expect(historyHeading).not.toBeNull();
        expect(historyHeading.textContent).toBe('История');
        const historyList = historyPanel.querySelector('#history-list');
        expect(historyList).not.toBeNull();
        expect(historyList.children.length).toBe(0); // Should be empty initially

        // Verify that initCalculator and initHistory were called
        expect(calculatorModule.initCalculator).toHaveBeenCalledTimes(1);
        expect(historyModule.initHistory).toHaveBeenCalledTimes(1);

        // Check arguments passed to initCalculator
        const displayElementArg = calculatorModule.initCalculator.mock.calls[0][0];
        const buttonsContainerArg = calculatorModule.initCalculator.mock.calls[0][1];
        const historyCallbackArg = calculatorModule.initCalculator.mock.calls[0][2];
        expect(displayElementArg).toBe(display);
        expect(buttonsContainerArg).toBe(buttonsGrid);
        expect(historyCallbackArg).toBe(historyModule.addHistoryEntry);

        // Check arguments passed to initHistory
        const historyListElementArg = historyModule.initHistory.mock.calls[0][0];
        expect(historyListElementArg).toBe(historyList);
    });

    it('должен выводить ошибку, если #app-root не найден', () => {
        // Remove the appRoot to simulate it not being found
        document.body.removeChild(appRoot);

        const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

        main();

        expect(consoleErrorSpy).toHaveBeenCalledWith('Root element #app-root not found!');
        expect(calculatorModule.initCalculator).not.toHaveBeenCalled();
        expect(historyModule.initHistory).not.toHaveBeenCalled();

        consoleErrorSpy.mockRestore();
    });
});
