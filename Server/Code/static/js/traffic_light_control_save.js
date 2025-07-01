// static/js/traffic_light_control.js
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const trafficLightSelect = document.getElementById('traffic-light-select');
    const modeToggle = document.getElementById('traffic-light-mode');
    const trafficLightContainer = document.getElementById('traffic-light-container');
    const statusMessage = document.getElementById('status-message');
    const currentState = document.getElementById('current-state');
    const lightElements = document.querySelectorAll('.light');

    // State
    let isManualMode = false;
    let currentColor = null;
    let selectedTrafficLight = trafficLightSelect.value;

    // Event Listeners
    modeToggle.addEventListener('change', handleModeToggle);
    trafficLightSelect.addEventListener('change', handleTrafficLightChange);

    // Set up light click events (only active in manual mode)
    lightElements.forEach(light => {
        light.addEventListener('click', function() {
            if (isManualMode) {
                const color = this.dataset.color;
                setLightColor(color);
                sendTrafficLightCommand(color);
            }
        });
    });

    // Functions
    function handleModeToggle(e) {
        isManualMode = e.target.checked;

        if (isManualMode) {
            enableManualControls();
            statusMessage.textContent = 'Manual Mode - Click a light to change';
            // Send command to switch to manual mode
            sendTrafficLightCommand('MANUAL');
        } else {
            disableManualControls();
            statusMessage.textContent = 'Automatic Mode';
            resetLights();
            // Send command to switch to automatic mode
            sendTrafficLightCommand('AUTO');
        }

        // Update current state display
        currentState.textContent = isManualMode ? 'Manual control active' : 'System controlled';
    }

    function handleTrafficLightChange() {
        selectedTrafficLight = trafficLightSelect.value;

        // Reset status when traffic light changes
        resetLights();

        if (isManualMode) {
            // If we're in manual mode, send command to switch the new light to manual mode
            sendTrafficLightCommand('MANUAL');
        }
    }

    function setLightColor(color) {
        // Reset all lights
        lightElements.forEach(light => {
            light.classList.remove('active');
        });

        // Activate the selected color
        const selectedLight = document.querySelector(`.light.${color}`);
        if (selectedLight) {
            selectedLight.classList.add('active');
            currentColor = color;
            currentState.textContent = `Current: ${color.toUpperCase()}`;
        }
    }

    function resetLights() {
        lightElements.forEach(light => {
            light.classList.remove('active');
        });
        currentColor = null;
        currentState.textContent = isManualMode ? 'No light selected' : 'System controlled';
    }

    function enableManualControls() {
        lightElements.forEach(light => {
            light.classList.add('clickable');
        });
        trafficLightContainer.classList.add('manual-mode');
    }

    function disableManualControls() {
        lightElements.forEach(light => {
            light.classList.remove('clickable');
        });
        trafficLightContainer.classList.remove('manual-mode');
    }

    function getSelectedTrafficLight() {
        return trafficLightSelect.value;
    }

    function sendTrafficLightCommand(command) {
        // Create request to send command to the server
        fetch('/send_command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: 'Publish',
                topic: getSelectedTrafficLight(),
                message: command,
                qos: 'At least once'  // Using QoS 1 for traffic light commands for better reliability
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status !== 'success') {
                console.error('Command failed:', data.message);
                statusMessage.textContent = `Error: ${data.message}`;
            }
        })
        .catch(error => {
            console.error('Error sending command:', error);
            statusMessage.textContent = 'Connection error';
        });
    }

    // Initialize - set to automatic mode
    disableManualControls();
});