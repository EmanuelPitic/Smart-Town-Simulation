// static/js/car_control.js
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const carSelect = document.getElementById('car-select');
    const powerToggle = document.getElementById('car-power');
    const messageRateInput = document.getElementById('message-rate');
    const controlsContainer = document.getElementById('controls-container');
    const statusMessage = document.getElementById('status-message');
    const lastCommand = document.getElementById('last-command');
    const controlButtons = document.querySelectorAll('.control-btn');

    // State
    let isPoweredOn = false;
    let activeCommands = new Set(); // Track multiple active commands
    let commandIntervals = {}; // Store intervals for each command
    let messageRate = parseInt(messageRateInput.value);

    // Button color mapping
    const buttonColorClasses = {
        'w': 'forward-active',
        'a': 'left-active',
        's': 'backward-active',
        'd': 'right-active',
        // Add any other commands and their corresponding color classes here
    };

    // Event Listeners
    powerToggle.addEventListener('change', handlePowerToggle);
    messageRateInput.addEventListener('change', handleRateChange);
    carSelect.addEventListener('change', handleCarChange);

    // Setup control buttons with touch/mouse events for continuous sending
    controlButtons.forEach(button => {
        // Mouse events
        button.addEventListener('mousedown', startCommand);

        // Touch events
        button.addEventListener('touchstart', (e) => {
            e.preventDefault(); // Prevent scrolling
            startCommand(e);
        });
    });

    // Global document events to stop commands
    document.addEventListener('mouseup', function(e) {
        // Find the button that was released (if any)
        const button = e.target.closest('.control-btn');
        if (button) {
            const command = button.dataset.command;
            stopSpecificCommand(command);
        }
    });

    document.addEventListener('touchend', function(e) {
        // Find the button that was released (if any)
        const button = e.target.closest('.control-btn');
        if (button) {
            const command = button.dataset.command;
            stopSpecificCommand(command);
        }
    });

    // Functions
    function handlePowerToggle(e) {
        isPoweredOn = e.target.checked;

        if (isPoweredOn) {
            sendMQTTCommand('Publish', getSelectedCar(), 'ON', 'At most once');
            statusMessage.textContent = 'Car powered ON';
            enableControls();
        } else {
            sendMQTTCommand('Publish', getSelectedCar(), 'OFF', 'At most once');
            statusMessage.textContent = 'Car powered OFF';
            disableControls();
            stopAllCommands();
        }
    }

    function handleRateChange(e) {
        messageRate = parseInt(e.target.value);

        // If commands are currently active, update their intervals
        activeCommands.forEach(command => {
            if (commandIntervals[command]) {
                clearInterval(commandIntervals[command]);
                sendCommandContinuously(command);
            }
        });
    }

    function handleCarChange() {
        // Reset power state when car changes
        if (isPoweredOn) {
            sendMQTTCommand('Publish', getSelectedCar(), 'ON', 'At most once');
            statusMessage.textContent = `Connected to ${getSelectedCar()}`;
        }
    }

    function startCommand(e) {
        if (!isPoweredOn) return;

        // Get the target button or find it from the touch event
        const target = e.target.closest('.control-btn');
        if (!target) return;

        const command = target.dataset.command;
        
        // Check if command is already active
        if (activeCommands.has(command)) return;
        
        // Add to active commands
        activeCommands.add(command);
        
        // Update UI
        activateButtonUI(command);
        updateLastCommandDisplay();

        // Send immediately and then start interval
        sendMQTTCommand('Publish', getSelectedCar(), command, 'At most once');
        sendCommandContinuously(command);
    }

    function activateButtonUI(command) {
        // Update UI - find the button that corresponds to this command
        const buttonToActivate = findButtonByCommand(command);
        if (buttonToActivate) {
            // Add the general active class
            buttonToActivate.classList.add('active');
            
            // Add the specific color class for this command
            if (buttonColorClasses[command]) {
                buttonToActivate.classList.add(buttonColorClasses[command]);
            }
        }
    }

    function deactivateButtonUI(command) {
        // Find the button that corresponds to this command
        const buttonToDeactivate = findButtonByCommand(command);
        if (buttonToDeactivate) {
            // Remove the active class
            buttonToDeactivate.classList.remove('active');
            
            // Remove the specific color class
            if (buttonColorClasses[command]) {
                buttonToDeactivate.classList.remove(buttonColorClasses[command]);
            }
        }
    }

    function updateLastCommandDisplay() {
        if (activeCommands.size === 0) {
            lastCommand.textContent = 'No active commands';
        } else {
            const commandList = Array.from(activeCommands).join(' + ');
            lastCommand.textContent = `Sending: ${commandList}`;
        }
    }

    function findButtonByCommand(command) {
        return Array.from(controlButtons).find(btn => btn.dataset.command === command);
    }

    function stopSpecificCommand(command) {
        if (!activeCommands.has(command)) return;

        // Stop the interval for this specific command
        if (commandIntervals[command]) {
            clearInterval(commandIntervals[command]);
            delete commandIntervals[command];
        }
        
        // Remove from active commands
        activeCommands.delete(command);
        
        // Update UI
        deactivateButtonUI(command);
        updateLastCommandDisplay();
    }

    function stopAllCommands() {
        // Clear all intervals
        Object.keys(commandIntervals).forEach(command => {
            clearInterval(commandIntervals[command]);
            delete commandIntervals[command];
        });
        
        // Clear active commands set
        activeCommands.clear();
        
        // Update UI - deactivate all buttons
        controlButtons.forEach(btn => {
            btn.classList.remove('active');
            Object.values(buttonColorClasses).forEach(colorClass => {
                btn.classList.remove(colorClass);
            });
        });
        
        lastCommand.textContent = 'All commands stopped';
        
        // Send stop command
        sendMQTTCommand('Publish', getSelectedCar(), 'STOP', 'At most once');
    }

    function sendCommandContinuously(command) {
        // Create new interval based on current message rate
        commandIntervals[command] = setInterval(() => {
            sendMQTTCommand('Publish', getSelectedCar(), command, 'At most once');
        }, messageRate);
    }

    function getSelectedCar() {
        return carSelect.value;
    }

    function enableControls() {
        controlButtons.forEach(btn => {
            btn.disabled = false;
            btn.classList.remove('disabled');
        });
        controlsContainer.classList.remove('disabled');
    }

    function disableControls() {
        controlButtons.forEach(btn => {
            btn.disabled = true;
            btn.classList.add('disabled');
        });
        controlsContainer.classList.add('disabled');
    }

    function sendMQTTCommand(operation, topic, payload, qos) {
        // Create AJAX request to send MQTT command
        fetch('/send_command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: operation,
                topic: topic,
                message: payload,
                qos: qos
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status !== 'success') {
                console.error('MQTT command failed:', data.message);
                statusMessage.textContent = `Error: ${data.message}`;
            }
        })
        .catch(error => {
            console.error('Error sending MQTT command:', error);
            statusMessage.textContent = 'Connection error';
        });
    }

    // Initialize - disable controls on load
    disableControls();

    // Keyboard control
    const keyCommandMap = {
        'W': 'w',
        'A': 'a',
        'S': 's',
        'D': 'd'
    };

    // Track which keys are currently pressed
    const pressedKeys = new Set();

    document.addEventListener('keydown', (event) => {
        if (!isPoweredOn) return;
        
        const key = event.key.toLowerCase();
        if (key in keyCommandMap && !pressedKeys.has(key)) {
            pressedKeys.add(key);
            const command = keyCommandMap[key];
            
            // Add to active commands if not already active
            if (!activeCommands.has(command)) {
                activeCommands.add(command);
                
                // Update UI
                activateButtonUI(command);
                updateLastCommandDisplay();
                
                // Send command immediately and continuously
                sendMQTTCommand('Publish', getSelectedCar(), command, 'At most once');
                sendCommandContinuously(command);
            }
        }
    });

    document.addEventListener('keyup', (event) => {
        const key = event.key.toLowerCase();
        if (key in keyCommandMap) {
            pressedKeys.delete(key);
            const command = keyCommandMap[key];
            stopSpecificCommand(command);
        }
    });

    // Clean up when window loses focus
    window.addEventListener('blur', () => {
        stopAllCommands();
        pressedKeys.clear();
    });
});
