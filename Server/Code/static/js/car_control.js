document.addEventListener('DOMContentLoaded', function() {
    // ─── DOM ELEMENTS ────────────────────────────────────────────────────────────
    const carSelect        = document.getElementById('car-select');
    const powerToggle      = document.getElementById('car-power');
    const messageRateInput = document.getElementById('message-rate');
    const emergencyToggle  = document.getElementById('emergency-toggle');
    const modeToggle       = document.getElementById('mode-toggle');
    const controlsContainer= document.getElementById('controls-container');
    const statusMessage    = document.getElementById('status-message');
    const lastCommand      = document.getElementById('last-command');
    const controlButtons   = document.querySelectorAll('.control-btn');

    // New diagnostic buttons
    const d1Btn            = document.getElementById('btn-d1');
    const d2Btn            = document.getElementById('btn-d2');

    // ─── STATE FLAGS ─────────────────────────────────────────────────────────────
    let isPoweredOn = false;
    let isEmergency = false;   // true if currently in “E” position
    let isManual    = false;   // true if “M” (manual) is selected
    let lastCmdText = '';      // to display last sent command

    // ─── BUTTON COLOR MAPPING ────────────────────────────────────────────────────
    const buttonColorClasses = {
        'w': 'forward-active',
        'a': 'left-active',
        's': 'backward-active',
        'd': 'right-active'
    };

    // ─── COMMAND MAPPING ──────────────────────────────────────────────────────────
    // Whenever we see 'w','a','s','d', translate into 'f','l','b','r'
    const cmdMapping = {
        'w': 'f',   // forward
        'a': 'l',   // left
        's': 'b',   // back
        'd': 'r'    // right
    };

    // ─── INITIAL SETUP ─────────────────────────────────────────────────────────────
    disableControls();
    hideWASDBtns();

    // ─── EVENT LISTENERS ───────────────────────────────────────────────────────────
    powerToggle.addEventListener('change', handlePowerToggle);
    messageRateInput.addEventListener('change', handleRateChange);
    carSelect.addEventListener('change', handleCarChange);

    emergencyToggle.addEventListener('change', function(e) {
        if (!isPoweredOn) {
            emergencyToggle.checked = false;
            return;
        }
        if (emergencyToggle.checked) {
            isEmergency = true;
            sendMQTTCommand('Publish', getSelectedCar(), 'e', 'At most once');
            statusMessage.textContent = 'Emergency ON';
        } else {
            isEmergency = false;
            sendMQTTCommand('Publish', getSelectedCar(), 'n', 'At most once');
            statusMessage.textContent = 'Emergency OFF';
        }
    });

    modeToggle.addEventListener('change', function(e) {
        if (!isPoweredOn) {
            modeToggle.checked = false;
            isManual = false;
            hideWASDBtns();
            return;
        }
        if (modeToggle.checked) {
            isManual = true;
            showWASDBtns();
            sendMQTTCommand('Publish', getSelectedCar(), 'm', 'At most once');
            statusMessage.textContent = 'Mode: MANUAL';
        } else {
            isManual = false;
            hideWASDBtns();
            sendMQTTCommand('Publish', getSelectedCar(), 'a', 'At most once');
            statusMessage.textContent = 'Mode: AUTOMATIC';
            clearLastCommand();
        }
    });

    controlButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!isPoweredOn || !isManual) return;
            const cmd = button.dataset.command;   // 'w','a','s','d'
            sendOneWASD(cmd);
        });
    });

    document.addEventListener('keydown', function(event) {
        if (!isPoweredOn || !isManual) return;
        const key = event.key.toLowerCase();
        if (['w','a','s','d'].includes(key)) {
            sendOneWASD(key);
        }
    });

    // Diagnostic buttons
    [d1Btn, d2Btn].forEach(btn => {
        btn.addEventListener('click', () => {
            if (!isPoweredOn) return;
            const cmd = btn.id === 'btn-d1' ? 'd1' : 'd2';
            sendMQTTCommand('Publish', getSelectedCar(), cmd, 'At most once');
            statusMessage.textContent = `Sent ${cmd.toUpperCase()}`;
            lastCommand.textContent  = `CMD: "${cmd.toUpperCase()}"`;
        });
    });

    // ─── CORE FUNCTIONS ────────────────────────────────────────────────────────────
    function handlePowerToggle(e) {
        isPoweredOn = e.target.checked;
        if (isPoweredOn) {
            sendMQTTCommand('Publish', getSelectedCar(), 'ON', 'At most once');
            statusMessage.textContent = 'Car powered ON';

            if (emergencyToggle.checked) {
                emergencyToggle.checked = false;
                isEmergency = false;
            }
            if (modeToggle.checked) {
                modeToggle.checked = false;
                isManual = false;
            }
            hideWASDBtns();
            enableControls();
        } else {
            sendMQTTCommand('Publish', getSelectedCar(), 'OFF', 'At most once');
            statusMessage.textContent = 'Car powered OFF';
            disableControls();

            if (emergencyToggle.checked) {
                emergencyToggle.checked = false;
                isEmergency = false;
            }
            if (modeToggle.checked) {
                modeToggle.checked = false;
                isManual = false;
            }
            hideWASDBtns();
            clearLastCommand();
        }
    }

    function handleRateChange(e) {
        // reserved for future use
    }

    function handleCarChange() {
        if (isPoweredOn) {
            sendMQTTCommand('Publish', getSelectedCar(), 'ON', 'At most once');
            statusMessage.textContent = `Connected to ${getSelectedCar()}`;
        }
    }

    function sendOneWASD(command) {
        const payload = cmdMapping[command] || command;
        highlightButton(command);
        sendMQTTCommand('Publish', getSelectedCar(), payload, 'At most once');
        lastCmdText = `CMD: "${payload.toUpperCase()}"`;
        lastCommand.textContent = lastCmdText;
    }

    function highlightButton(command) {
        const btn = Array.from(controlButtons).find(b => b.dataset.command === command);
        if (!btn) return;
        btn.classList.add('active');
        if (buttonColorClasses[command]) {
            btn.classList.add(buttonColorClasses[command]);
        }
        setTimeout(() => {
            btn.classList.remove('active');
            if (buttonColorClasses[command]) {
                btn.classList.remove(buttonColorClasses[command]);
            }
        }, 200);
    }

    function clearLastCommand() {
        lastCmdText = '';
        lastCommand.textContent = '-';
    }

    function getSelectedCar() {
        return carSelect.value;
    }

    function enableControls() {
        powerToggle.disabled      = false;
        emergencyToggle.disabled  = false;
        modeToggle.disabled       = false;
        messageRateInput.disabled = false;
        d1Btn.disabled            = false;
        d2Btn.disabled            = false;
    }

    function disableControls() {
        emergencyToggle.disabled  = true;
        modeToggle.disabled       = true;
        messageRateInput.disabled = true;
        d1Btn.disabled            = true;
        d2Btn.disabled            = true;
        hideWASDBtns();
    }

    function showWASDBtns() {
        controlsContainer.style.display = 'block';
    }

    function hideWASDBtns() {
        controlsContainer.style.display = 'none';
    }

    function sendMQTTCommand(operation, topic, payload, qos) {
        fetch('/send_command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: operation, topic, message: payload, qos })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status !== 'success') {
                console.error('MQTT command failed:', data.message);
                statusMessage.textContent = `Error: ${data.message}`;
            }
        })
        .catch(err => {
            console.error('Error sending MQTT command:', err);
            statusMessage.textContent = 'Connection error';
        });
    }
});

