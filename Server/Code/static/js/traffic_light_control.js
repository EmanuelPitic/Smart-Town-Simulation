// static/js/traffic_light_control.js

document.addEventListener('DOMContentLoaded', function() {
  // ----- 1) DOM Elements -----
  const trafficLightSelect = document.getElementById('traffic-light-select');
  const modeToggle        = document.getElementById('traffic-light-mode');
  const directionSelect   = document.getElementById('direction-select');
  const sequentialSettings   = document.getElementById('sequential-settings');
  const intelligentSettings  = document.getElementById('intelligent-settings');
  const applySequentialBtn   = document.getElementById('apply-sequential');
  const applyIntelligentBtn  = document.getElementById('apply-intelligent');

  const statusMessage = document.getElementById('status-message');
  const currentState  = document.getElementById('current-state');
  const lightElements = document.querySelectorAll('.light');

  // ----- 2) State Variables -----
  let isManualMode      = false;
  let isSequentialMode  = false;
  let isIntelligentMode = false;
  let selectedTopic     = trafficLightSelect.value;

  // Default timer values (read from inputs when needed)
  let redTime        = parseInt(document.getElementById('red-time').value, 10);
  let yellowTime     = parseInt(document.getElementById('yellow-time').value, 10);
  let greenTime      = parseInt(document.getElementById('green-time').value, 10);
  let greenTimeSmart = parseInt(document.getElementById('green-time-smart').value, 10);

  // ----- 3) Helper: send command via Flask endpoint (/send_command) -----
  function sendTrafficLightCommand(command) {
    // Append a space to the end of each sent message
    const fullCommand = command + ' ';
    fetch('/send_command', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type:  'Publish',
        topic: selectedTopic,
        message: fullCommand,
        qos:   'At least once'     // QoS 1
      })
    })
    .then(response => response.json())
    .then(data => {
      if (data.status !== 'success') {
        console.error('Command failed:', data.message);
        statusMessage.textContent = `Error: ${data.message}`;
      }
    })
    .catch(err => {
      console.error('Error sending command:', err);
      statusMessage.textContent = 'Connection error';
    });
  }

  // ----- 4) Utility: update the "Current State" display -----
  function updateCurrentStateLabel() {
    if (isManualMode) {
      currentState.textContent = `Manual ▶ ${directionSelect.value}`;
    }
    else if (isSequentialMode) {
      currentState.textContent =
        `Sequential ▶ ${directionSelect.value} | r=${redTime}s, y=${yellowTime}s, g=${greenTime}s`;
    }
    else if (isIntelligentMode) {
      currentState.textContent = `Intelligent ▶ green=${greenTimeSmart}s`;
    }
    else {
      currentState.textContent = 'System controlled';
    }
  }

  // ----- 5) Mode Toggle Handler -----
  modeToggle.addEventListener('change', function(e) {
    isManualMode = e.target.checked;

    if (isManualMode) {
      // Hide automatic mode settings
      sequentialSettings.style.display   = 'none';
      intelligentSettings.style.display  = 'none';
      isSequentialMode  = false;
      isIntelligentMode = false;

      statusMessage.textContent = 'Manual Mode – click "Direction" to send';
      // Immediately send "m <dir>" with trailing space
      const dir = directionSelect.value;
      sendTrafficLightCommand(`m ${dir}`);
    }
    else {
      // Switching OFF manual → show both automatic options
      sequentialSettings.style.display   = 'block';
      intelligentSettings.style.display  = 'block';
      
      // Default to Sequential when switching from manual
      isSequentialMode  = true;
      isIntelligentMode = false;

      // Read the latest inputs:
      redTime    = parseInt(document.getElementById('red-time').value, 10);
      yellowTime = parseInt(document.getElementById('yellow-time').value, 10);
      greenTime  = parseInt(document.getElementById('green-time').value, 10);
      const dir = directionSelect.value;

      statusMessage.textContent = 'Automatic Mode - Choose Sequential or Intelligent';
      // Immediately send "s <dir> r <r> y <y> g <g>" with trailing space
      sendTrafficLightCommand(`s ${dir} r ${redTime} y ${yellowTime} g ${greenTime}`);
    }

    updateCurrentStateLabel();
  });

  // ----- 6) Traffic Light Select Changed -----
  trafficLightSelect.addEventListener('change', function() {
    selectedTopic = trafficLightSelect.value;

    // Reset UI to "Sequential" by default
    modeToggle.checked      = false;
    isManualMode            = false;
    isSequentialMode        = true;
    isIntelligentMode       = false;
    sequentialSettings.style.display   = 'block';
    intelligentSettings.style.display  = 'block';

    // Read the latest inputs:
    redTime    = parseInt(document.getElementById('red-time').value, 10);
    yellowTime = parseInt(document.getElementById('yellow-time').value, 10);
    greenTime  = parseInt(document.getElementById('green-time').value, 10);
    const dir = directionSelect.value;

    statusMessage.textContent = 'Automatic Mode - Choose Sequential or Intelligent';
    // Send default sequential for the new topic with trailing space
    sendTrafficLightCommand(`s ${dir} r ${redTime} y ${yellowTime} g ${greenTime}`);
    updateCurrentStateLabel();
  });

  // ----- 7) Direction Changed -----
  directionSelect.addEventListener('change', function() {
    const dir = directionSelect.value;

    if (isManualMode) {
      // Re‐send "m <dir>" with trailing space
      sendTrafficLightCommand(`m ${dir}`);
    }
    else if (isSequentialMode) {
      // Read current timing inputs and re‐send "s <dir> r <r> y <y> g <g>" with trailing space
      redTime    = parseInt(document.getElementById('red-time').value, 10);
      yellowTime = parseInt(document.getElementById('yellow-time').value, 10);
      greenTime  = parseInt(document.getElementById('green-time').value, 10);
      sendTrafficLightCommand(`s ${dir} r ${redTime} y ${yellowTime} g ${greenTime}`);
    }
    else if (isIntelligentMode) {
      // Read current "green‐time‐smart" and re‐send "i <greenTimeSmart>" with trailing space
      greenTimeSmart = parseInt(document.getElementById('green-time-smart').value, 10);
      sendTrafficLightCommand(`i ${greenTimeSmart}`);
    }

    updateCurrentStateLabel();
  });

  // ----- 8) Apply Sequential Button -----
  applySequentialBtn.addEventListener('click', function() {
    isManualMode      = false;
    isSequentialMode  = true;
    isIntelligentMode = false;
    modeToggle.checked = false;

    // Read timing inputs:
    redTime    = parseInt(document.getElementById('red-time').value, 10);
    yellowTime = parseInt(document.getElementById('yellow-time').value, 10);
    greenTime  = parseInt(document.getElementById('green-time').value, 10);
    const dir = directionSelect.value;

    // Publish "s <dir> r <r> y <y> g <g>" with trailing space
    sendTrafficLightCommand(`s ${dir} r ${redTime} y ${yellowTime} g ${greenTime}`);
    statusMessage.textContent = 'Sequential Mode Applied';
    updateCurrentStateLabel();
  });

  // ----- 9) Apply Intelligent Button -----
  applyIntelligentBtn.addEventListener('click', function() {
    isManualMode      = false;
    isSequentialMode  = false;
    isIntelligentMode = true;
    modeToggle.checked = false;

    greenTimeSmart = parseInt(document.getElementById('green-time-smart').value, 10);
    // Publish "i <greenTimeSmart>" with trailing space
    sendTrafficLightCommand(`i ${greenTimeSmart}`);
    statusMessage.textContent = 'Intelligent Mode Applied';
    updateCurrentStateLabel();
  });

  // ----- 10) Cosmetic: Light Click (UI only) -----
  lightElements.forEach(light => {
    light.addEventListener('click', function() {
      // Only a CSS highlight effect—no new MQTT payload is sent on color‐circle clicks.
      lightElements.forEach(l => l.classList.remove('active'));
      this.classList.add('active');
      currentState.textContent = `Current: ${this.dataset.color.toUpperCase()}`;
    });
  });

  // ----- 11) Initialize on Page Load -----
  // Default to "Sequential" (manual toggle unchecked), but show both automatic options
  sequentialSettings.style.display  = 'block';
  intelligentSettings.style.display = 'block';
  isSequentialMode = true;
  
  redTime    = parseInt(document.getElementById('red-time').value, 10);
  yellowTime = parseInt(document.getElementById('yellow-time').value, 10);
  greenTime  = parseInt(document.getElementById('green-time').value, 10);

  statusMessage.textContent = 'Automatic Mode - Choose Sequential or Intelligent';
  currentState.textContent  = `Sequential ▶ ${directionSelect.value} | r=${redTime}s, y=${yellowTime}s, g=${greenTime}s`;
});
