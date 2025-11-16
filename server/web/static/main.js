// ========================================
// Acoustic Drone Localization System
// Enhanced Web Interface JavaScript
// ========================================

const state = {
  history: [],
  maxHistory: 300,
  config: null,
  lastUpdate: null,
  nodeHealth: {},
};

const sceneElements = {
  renderer: null,
  scene: null,
  camera: null,
  drone: null,
  droneTrail: null,
  trueDrone: null, // True position marker for simulation mode
  trueDroneTrail: null,
  nodes: {},
  controls: null,
  gridBounds: null,
};

const calibrationState = {
  jobs: {},
  pollHandle: null,
  defaultDuration: 60,
  configDir: "configs",
  flashTimeout: null,
  sliderDirty: false,
};

// ========================================
// Configuration Loading
// ========================================

async function loadConfig() {
  try {
    const response = await fetch("/api/config");
    state.config = await response.json();
    console.log("Loaded configuration:", state.config);
  } catch (err) {
    console.error("Failed to load configuration:", err);
  }
}

// ========================================
// Tab + Health Utilities
// ========================================

function setupTabs() {
  const buttons = document.querySelectorAll("[data-tab-target]");
  const panels = document.querySelectorAll("[data-tab-panel]");
  if (!buttons.length || !panels.length) {
    return;
  }
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.tabTarget;
      buttons.forEach((btn) => btn.classList.toggle("active", btn === button));
      panels.forEach((panel) =>
        panel.classList.toggle("active", panel.dataset.tabPanel === target)
      );
    });
  });
}

function getNodeHealth(nodeId) {
  if (!state.nodeHealth) {
    return null;
  }
  return state.nodeHealth[nodeId] || state.nodeHealth[String(nodeId)] || null;
}

function formatRelativeTime(epochSeconds) {
  if (!epochSeconds) {
    return "—";
  }
  const delta = Math.max(0, Date.now() / 1000 - epochSeconds);
  if (delta < 1) return "just now";
  if (delta < 60) return `${Math.round(delta)}s ago`;
  const minutes = Math.round(delta / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

async function fetchNodeHealth() {
  try {
    const response = await fetch("/api/nodes");
    if (!response.ok) {
      throw new Error("Failed to load node health");
    }
    const health = await response.json();
    state.nodeHealth = health || {};
    renderCalibrationCards();
  } catch (err) {
    console.warn("Node health fetch failed:", err);
  }
}

function startNodeHealthPolling() {
  fetchNodeHealth();
  setInterval(fetchNodeHealth, 3000);
}

// ========================================
// Calibration UI
// ========================================

function showCalibrationFlash(message, type = "info") {
  const flash = document.getElementById("calibration-flash");
  if (!flash) return;
  flash.textContent = message;
  flash.className = `calibration-flash ${type} visible`;
  if (calibrationState.flashTimeout) {
    clearTimeout(calibrationState.flashTimeout);
  }
  calibrationState.flashTimeout = setTimeout(() => {
    flash.className = "calibration-flash";
  }, 4000);
}

async function fetchCalibrationStatus() {
  try {
    const response = await fetch("/api/calibration");
    if (!response.ok) {
      throw new Error("Failed to load calibration status");
    }
    const data = await response.json();
    calibrationState.jobs = {};
    (data.jobs || []).forEach((job) => {
      calibrationState.jobs[job.node_id] = job;
    });
    if (data.config_dir) {
      calibrationState.configDir = data.config_dir;
    }
    if (
      data.defaults &&
      typeof data.defaults.duration === "number" &&
      !calibrationState.sliderDirty
    ) {
      calibrationState.defaultDuration = data.defaults.duration;
      const durationInput = document.getElementById("calibration-duration");
      const durationValue = document.getElementById(
        "calibration-duration-value"
      );
      if (durationInput) {
        durationInput.value = data.defaults.duration;
      }
      if (durationValue) {
        durationValue.textContent = `${Math.round(data.defaults.duration)}s`;
      }
    }
    renderCalibrationCards();
  } catch (err) {
    console.warn("Calibration status fetch failed:", err);
  }
}

function renderCalibrationCards() {
  const container = document.getElementById("calibration-cards");
  if (!container || !state.config || !state.config.nodes) {
    return;
  }
  const nodes = state.config.nodes;
  if (!nodes.length) {
    container.innerHTML =
      '<div class="glass-card subtle">No nodes configured yet.</div>';
    return;
  }

  const fragment = document.createDocumentFragment();
  const statusTextMap = {
    running: "Sampling",
    processing: "Processing",
    completed: "Calibrated",
    failed: "Failed",
    pending: "Pending",
    ready: "Ready",
    offline: "Offline",
  };
  const summary = { running: 0, completed: 0, failed: 0 };

  nodes.forEach((node) => {
    const job = calibrationState.jobs[node.id] || null;
    const health = getNodeHealth(node.id);
    const online = health ? !!health.online : false;
    const rawStatus = job ? job.status : online ? "ready" : "offline";
    if (rawStatus === "running" || rawStatus === "processing") {
      summary.running += 1;
    } else if (rawStatus === "completed") {
      summary.completed += 1;
    } else if (rawStatus === "failed") {
      summary.failed += 1;
    }
    let progress = job ? Math.round((job.progress || 0) * 100) : 0;
    if (rawStatus === "completed" || rawStatus === "failed") {
      progress = 100;
    }
    progress = Math.min(Math.max(progress, 0), 100);
    const statusClass = `status-${rawStatus === "processing" ? "running" : rawStatus}`;
    const statusText = statusTextMap[rawStatus] || rawStatus;
    const samples = job ? job.sample_count : 0;
    const resultText =
      job && Array.isArray(job.result)
        ? job.result.map((val) => Number(val).toFixed(3)).join(" · ")
        : "—";
    const lastSeen = health ? formatRelativeTime(health.last_seen) : "—";
    const message =
      job?.message ||
      (online ? "Ready for calibration" : "Waiting for heartbeat");
    const buttonDisabled =
      !online ||
      (job && (job.status === "running" || job.status === "processing"));
    const buttonLabel =
      job && job.status === "running" ? "Calibrating…" : "Calibrate";

    const card = document.createElement("div");
    card.className = "calibration-card glass-card";
    card.innerHTML = `
      <div class="card-header">
        <div>
          <strong>Node ${node.id}</strong>
          <div class="node-meta">${online ? "Online" : "Offline"} · Last seen ${lastSeen}</div>
        </div>
        <span class="status-pill ${statusClass}">${statusText}</span>
      </div>
      <div class="calibration-progress">
        <div class="calibration-progress-track">
          <div class="calibration-progress-value" style="width: ${progress}%;"></div>
        </div>
        <span>${progress}%</span>
      </div>
      <div class="card-stats">
        <div class="card-stat">
          <label>Samples</label>
          <strong>${samples}</strong>
        </div>
        <div class="card-stat">
          <label>Noise RMS</label>
          <strong>${resultText}</strong>
        </div>
      </div>
      <div class="card-footer">
        <span class="card-message">${message}</span>
        <button class="glass-btn" data-node="${node.id}" ${buttonDisabled ? "disabled" : ""}>${buttonLabel}</button>
      </div>
    `;
    const button = card.querySelector("button");
    if (button) {
      button.addEventListener("click", () => startCalibrationJob(node.id));
    }
    fragment.appendChild(card);
  });

  container.innerHTML = "";
  container.appendChild(fragment);

  const runningEl = document.getElementById("calibration-running-count");
  const completeEl = document.getElementById("calibration-complete-count");
  const failedEl = document.getElementById("calibration-failed-count");
  const configDirEl = document.getElementById("calibration-config-dir");
  if (runningEl) runningEl.textContent = summary.running;
  if (completeEl) completeEl.textContent = summary.completed;
  if (failedEl) failedEl.textContent = summary.failed;
  if (configDirEl) configDirEl.textContent = calibrationState.configDir;
}

async function startCalibrationJob(nodeId, options = {}) {
  const durationInput = document.getElementById("calibration-duration");
  let duration = durationInput
    ? parseFloat(durationInput.value)
    : calibrationState.defaultDuration;
  if (!Number.isFinite(duration) || duration <= 0) {
    duration = calibrationState.defaultDuration;
  }
  try {
    const response = await fetch("/api/calibration/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node_id: nodeId, duration }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error || "Unable to start calibration");
    }
    if (!options.silent) {
      showCalibrationFlash(`Node ${nodeId}: calibration started`, "success");
    }
    fetchCalibrationStatus();
    return true;
  } catch (err) {
    if (!options.silent) {
      showCalibrationFlash(`Node ${nodeId}: ${err.message}`, "error");
    }
    console.error("Calibration start failed", err);
    return false;
  }
}

async function handleCalibrateAll() {
  if (!state.config || !state.config.nodes) return;
  const button = document.getElementById("calibrate-all");
  if (button) {
    button.disabled = true;
  }
  let started = 0;
  for (const node of state.config.nodes) {
    const health = getNodeHealth(node.id);
    const job = calibrationState.jobs[node.id];
    if (
      !health ||
      !health.online ||
      (job && (job.status === "running" || job.status === "processing"))
    ) {
      continue;
    }
    const ok = await startCalibrationJob(node.id, { silent: true });
    if (ok) {
      started += 1;
    }
  }
  if (button) {
    button.disabled = false;
  }
  if (started === 0) {
    showCalibrationFlash("No ready nodes for calibration", "warning");
  } else {
    showCalibrationFlash(
      `Started calibration on ${started} node${started > 1 ? "s" : ""}`,
      "success"
    );
  }
}

function initCalibrationUI() {
  const durationInput = document.getElementById("calibration-duration");
  const durationValue = document.getElementById("calibration-duration-value");
  if (durationInput && durationValue) {
    durationInput.value = calibrationState.defaultDuration;
    durationValue.textContent = `${Math.round(calibrationState.defaultDuration)}s`;
    durationInput.addEventListener("input", () => {
      calibrationState.sliderDirty = true;
      calibrationState.defaultDuration = parseFloat(durationInput.value);
      durationValue.textContent = `${Math.round(calibrationState.defaultDuration)}s`;
    });
  }
  const allButton = document.getElementById("calibrate-all");
  if (allButton) {
    allButton.addEventListener("click", handleCalibrateAll);
  }
  renderCalibrationCards();
  fetchCalibrationStatus();
  if (!calibrationState.pollHandle) {
    calibrationState.pollHandle = setInterval(fetchCalibrationStatus, 3000);
  }
}

// ========================================
// Three.js 3D Scene Initialization
// ========================================

function initThree() {
  const container = document.getElementById("scene");
  const width = container.clientWidth;
  const height = container.clientHeight;

  // Renderer setup
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(width, height);
  renderer.setClearColor(0x000000, 1);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  // Scene setup
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x000000, 0.015);

  // Camera setup
  const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 500);
  camera.position.set(25, 25, 35);
  camera.lookAt(new THREE.Vector3(10, 10, 10));

  // Orbit controls
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.set(10, 10, 5);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.minDistance = 5;
  controls.maxDistance = 100;
  controls.maxPolarAngle = (Math.PI / 2) * 0.95;

  // Lighting
  const ambient = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambient);

  const directional = new THREE.DirectionalLight(0xffffff, 0.8);
  directional.position.set(30, 50, 40);
  directional.castShadow = true;
  directional.shadow.mapSize.width = 2048;
  directional.shadow.mapSize.height = 2048;
  directional.shadow.camera.near = 0.5;
  directional.shadow.camera.far = 200;
  directional.shadow.camera.left = -50;
  directional.shadow.camera.right = 50;
  directional.shadow.camera.top = 50;
  directional.shadow.camera.bottom = -50;
  scene.add(directional);

  // Hemisphere light for better ambient
  const hemiLight = new THREE.HemisphereLight(0x0077ff, 0x00ff00, 0.3);
  scene.add(hemiLight);

  // Ground plane
  const groundGeometry = new THREE.PlaneGeometry(50, 50);
  const groundMaterial = new THREE.MeshStandardMaterial({
    color: 0x0a0a0a,
    roughness: 0.8,
    metalness: 0.2,
  });
  const ground = new THREE.Mesh(groundGeometry, groundMaterial);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // Grid helper
  const gridHelper = new THREE.GridHelper(50, 25, 0x444444, 0x222222);
  scene.add(gridHelper);

  // Axes helper
  const axesHelper = new THREE.AxesHelper(15);
  axesHelper.position.set(0, 0.1, 0);
  scene.add(axesHelper);

  // Drone sphere (target)
  const droneGeometry = new THREE.SphereGeometry(0.8, 32, 32);
  const droneMaterial = new THREE.MeshStandardMaterial({
    color: 0xff3333,
    emissive: 0xff1111,
    emissiveIntensity: 0.5,
    roughness: 0.3,
    metalness: 0.7,
  });
  const drone = new THREE.Mesh(droneGeometry, droneMaterial);
  drone.castShadow = true;
  drone.position.set(0, 0, 0);
  scene.add(drone);

  // Drone glow effect
  const glowGeometry = new THREE.SphereGeometry(1.2, 16, 16);
  const glowMaterial = new THREE.MeshBasicMaterial({
    color: 0xff5555,
    transparent: true,
    opacity: 0.3,
  });
  const glow = new THREE.Mesh(glowGeometry, glowMaterial);
  drone.add(glow);

  // Drone trail
  const trailMaterial = new THREE.LineBasicMaterial({
    color: 0xff5555,
    transparent: true,
    opacity: 0.5,
  });
  const trailGeometry = new THREE.BufferGeometry();
  const trailPositions = new Float32Array(300 * 3);
  trailGeometry.setAttribute(
    "position",
    new THREE.BufferAttribute(trailPositions, 3)
  );
  const droneTrail = new THREE.Line(trailGeometry, trailMaterial);
  scene.add(droneTrail);

  // True drone position marker (for simulation mode) - GREEN
  const trueDroneGeometry = new THREE.SphereGeometry(0.6, 32, 32);
  const trueDroneMaterial = new THREE.MeshStandardMaterial({
    color: 0x33ff33,
    emissive: 0x11ff11,
    emissiveIntensity: 0.6,
    roughness: 0.3,
    metalness: 0.7,
    transparent: true,
    opacity: 0.8,
  });
  const trueDrone = new THREE.Mesh(trueDroneGeometry, trueDroneMaterial);
  trueDrone.castShadow = true;
  trueDrone.position.set(0, 0, 0);
  trueDrone.visible = false; // Hidden by default
  scene.add(trueDrone);

  // True drone glow effect
  const trueGlowGeometry = new THREE.SphereGeometry(0.9, 16, 16);
  const trueGlowMaterial = new THREE.MeshBasicMaterial({
    color: 0x55ff55,
    transparent: true,
    opacity: 0.3,
  });
  const trueGlow = new THREE.Mesh(trueGlowGeometry, trueGlowMaterial);
  trueDrone.add(trueGlow);

  // True drone trail
  const trueTrailMaterial = new THREE.LineBasicMaterial({
    color: 0x55ff55,
    transparent: true,
    opacity: 0.4,
  });
  const trueTrailGeometry = new THREE.BufferGeometry();
  const trueTrailPositions = new Float32Array(300 * 3);
  trueTrailGeometry.setAttribute(
    "position",
    new THREE.BufferAttribute(trueTrailPositions, 3)
  );
  const trueDroneTrail = new THREE.Line(trueTrailGeometry, trueTrailMaterial);
  trueDroneTrail.visible = false; // Hidden by default
  scene.add(trueDroneTrail);

  // Store references
  sceneElements.renderer = renderer;
  sceneElements.scene = scene;
  sceneElements.camera = camera;
  sceneElements.controls = controls;
  sceneElements.drone = drone;
  sceneElements.droneTrail = droneTrail;
  sceneElements.trueDrone = trueDrone;
  sceneElements.trueDroneTrail = trueDroneTrail;

  // Window resize handler
  window.addEventListener("resize", () => {
    const w = container.clientWidth;
    const h = container.clientHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  });

  // Animation loop
  function animate() {
    requestAnimationFrame(animate);
    controls.update();

    // Pulsing glow effect for estimated position
    if (glow) {
      glow.scale.set(
        1 + 0.1 * Math.sin(Date.now() * 0.003),
        1 + 0.1 * Math.sin(Date.now() * 0.003),
        1 + 0.1 * Math.sin(Date.now() * 0.003)
      );
    }

    // Pulsing glow effect for true position
    if (trueGlow && trueDrone.visible) {
      trueGlow.scale.set(
        1 + 0.1 * Math.sin(Date.now() * 0.004),
        1 + 0.1 * Math.sin(Date.now() * 0.004),
        1 + 0.1 * Math.sin(Date.now() * 0.004)
      );
    }

    renderer.render(scene, camera);
  }
  animate();

  console.log("3D scene initialized");
}

// ========================================
// Node Visualization
// ========================================

function createNodeMarker(nodeId, position) {
  const group = new THREE.Group();

  // Node sphere
  const sphereGeometry = new THREE.SphereGeometry(0.6, 24, 24);
  const sphereMaterial = new THREE.MeshStandardMaterial({
    color: 0x4dabf7,
    emissive: 0x1e88e5,
    emissiveIntensity: 0.4,
    roughness: 0.4,
    metalness: 0.6,
  });
  const sphere = new THREE.Mesh(sphereGeometry, sphereMaterial);
  sphere.castShadow = true;
  group.add(sphere);

  // Node label
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  canvas.width = 128;
  canvas.height = 64;
  context.fillStyle = "#4dabf7";
  context.font = "bold 32px Arial";
  context.textAlign = "center";
  context.fillText(`Node ${nodeId}`, 64, 40);

  const texture = new THREE.CanvasTexture(canvas);
  const spriteMaterial = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
  });
  const sprite = new THREE.Sprite(spriteMaterial);
  sprite.scale.set(4, 2, 1);
  sprite.position.set(0, 2, 0);
  group.add(sprite);

  // Position indicator column
  const columnGeometry = new THREE.CylinderGeometry(0.1, 0.1, position[2], 8);
  const columnMaterial = new THREE.MeshStandardMaterial({
    color: 0x4dabf7,
    transparent: true,
    opacity: 0.4,
  });
  const column = new THREE.Mesh(columnGeometry, columnMaterial);
  column.position.set(0, -position[2] / 2, 0);
  group.add(column);

  group.position.set(position[0], position[2], position[1]);
  sceneElements.scene.add(group);
  sceneElements.nodes[nodeId] = group;

  console.log(`Created node ${nodeId} at position [${position}]`);
}

// ========================================
// Camera View Controls
// ========================================

function setupViewControls() {
  const btnTop = document.getElementById("view-top");
  const btnSide = document.getElementById("view-side");
  const btnReset = document.getElementById("view-reset");

  btnTop.addEventListener("click", () => {
    animateCamera(10, 40, 10, 10, 0, 10);
    setActiveButton(btnTop);
  });

  btnSide.addEventListener("click", () => {
    animateCamera(40, 10, 10, 10, 10, 10);
    setActiveButton(btnSide);
  });

  btnReset.addEventListener("click", () => {
    animateCamera(25, 25, 35, 10, 10, 5);
    setActiveButton(btnReset);
  });
}

function setActiveButton(activeBtn) {
  document
    .querySelectorAll(".view-btn")
    .forEach((btn) => btn.classList.remove("active"));
  activeBtn.classList.add("active");
}

function animateCamera(x, y, z, targetX, targetY, targetZ) {
  const camera = sceneElements.camera;
  const controls = sceneElements.controls;

  const startPos = camera.position.clone();
  const endPos = new THREE.Vector3(x, y, z);
  const startTarget = controls.target.clone();
  const endTarget = new THREE.Vector3(targetX, targetY, targetZ);

  const duration = 1000;
  const startTime = Date.now();

  function animate() {
    const elapsed = Date.now() - startTime;
    const t = Math.min(elapsed / duration, 1);
    const eased = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; // easeInOutQuad

    camera.position.lerpVectors(startPos, endPos, eased);
    controls.target.lerpVectors(startTarget, endTarget, eased);

    if (t < 1) {
      requestAnimationFrame(animate);
    }
  }

  animate();
}

// ========================================
// Node Table Update
// ========================================

function updateNodesTable(nodeDetails) {
  const tbody = document.getElementById("node-table");
  if (!tbody) return;
  tbody.innerHTML = "";

  const configNodes =
    state.config && state.config.nodes ? state.config.nodes : [];
  if (!configNodes.length) {
    tbody.innerHTML =
      '<tr><td colspan="4" style="text-align: center;">No nodes configured</td></tr>';
    return;
  }

  const detailMap = {};
  (nodeDetails || []).forEach((detail) => {
    detailMap[detail.id] = detail;
  });

  configNodes.forEach((node) => {
    const detail = detailMap[node.id] || {};
    const health = getNodeHealth(node.id);
    const online = health ? !!health.online : !!detail.online;
    const energy =
      detail.energy != null ? `${(detail.energy * 100).toFixed(1)}%` : "—";
    const dir = detail.dir || [];
    const dirStr = dir.length
      ? `(${dir.map((v) => v.toFixed(2)).join(", ")})`
      : "—";
    const statusClass = online ? "online" : "offline";
    const statusLabel = online ? "Online" : "Offline";
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>Node ${node.id}</td>
      <td>${energy}</td>
      <td style="font-family: monospace; font-size: 0.85em;">${dirStr}</td>
      <td class="${statusClass}">${statusLabel}</td>
    `;
    tbody.appendChild(row);
  });
}

// ========================================
// Charts Update
// ========================================

function updateCharts(totalEnergy, confidence) {
  const now = Date.now();
  state.history.push({ energy: totalEnergy, confidence, ts: now });

  if (state.history.length > state.maxHistory) {
    state.history.shift();
  }

  const times = state.history.map((item) => new Date(item.ts));

  // Energy chart
  Plotly.react(
    "energy-chart",
    [
      {
        x: times,
        y: state.history.map((item) => item.energy),
        type: "scatter",
        mode: "lines",
        line: { color: "#3fb950", width: 2 },
        fill: "tozeroy",
        fillcolor: "rgba(63, 185, 80, 0.2)",
      },
    ],
    {
      margin: { t: 10, b: 30, l: 40, r: 10 },
      paper_bgcolor: "#21262d",
      plot_bgcolor: "#0d1117",
      font: { color: "#c9d1d9", size: 11 },
      xaxis: { showgrid: false, color: "#8b949e" },
      yaxis: { showgrid: true, gridcolor: "#30363d", color: "#8b949e" },
    },
    { responsive: true, displayModeBar: false }
  );

  // Confidence chart
  Plotly.react(
    "confidence-chart",
    [
      {
        x: times,
        y: state.history.map((item) => item.confidence),
        type: "scatter",
        mode: "lines",
        line: { color: "#d29922", width: 2 },
        fill: "tozeroy",
        fillcolor: "rgba(210, 153, 34, 0.2)",
      },
    ],
    {
      margin: { t: 10, b: 30, l: 40, r: 10 },
      paper_bgcolor: "#21262d",
      plot_bgcolor: "#0d1117",
      font: { color: "#c9d1d9", size: 11 },
      xaxis: { showgrid: false, color: "#8b949e" },
      yaxis: {
        range: [0, 1],
        showgrid: true,
        gridcolor: "#30363d",
        color: "#8b949e",
      },
    },
    { responsive: true, displayModeBar: false }
  );
}

// ========================================
// Scene Update
// ========================================

function updateScene(data) {
  if (!sceneElements.drone || !data) return;

  const position = data.position || [0, 0, 0];
  const nodeDetails = data.node_details || [];
  const truePosition = data.true_position;
  const simulationMode = data.simulation_mode || false;

  // Update drone position (estimated)
  sceneElements.drone.position.set(position[0], position[2], position[1]);

  // Update drone trail
  if (sceneElements.droneTrail && data.present) {
    const trailPositions =
      sceneElements.droneTrail.geometry.attributes.position.array;
    for (let i = trailPositions.length - 3; i >= 3; i -= 3) {
      trailPositions[i] = trailPositions[i - 3];
      trailPositions[i + 1] = trailPositions[i - 2];
      trailPositions[i + 2] = trailPositions[i - 1];
    }
    trailPositions[0] = position[0];
    trailPositions[1] = position[2];
    trailPositions[2] = position[1];
    sceneElements.droneTrail.geometry.attributes.position.needsUpdate = true;
  }

  // Update true position (simulation mode)
  if (simulationMode && truePosition) {
    // Show toggle control
    const toggleContainer = document.getElementById(
      "true-pos-toggle-container"
    );
    if (toggleContainer) {
      toggleContainer.style.display = "flex";
    }

    // Update true position marker
    const checkbox = document.getElementById("show-true-position");
    const showTrue = checkbox ? checkbox.checked : true;

    if (sceneElements.trueDrone && sceneElements.trueDroneTrail) {
      sceneElements.trueDrone.position.set(
        truePosition[0],
        truePosition[2],
        truePosition[1]
      );
      sceneElements.trueDrone.visible = showTrue;
      sceneElements.trueDroneTrail.visible = showTrue;

      // Update true drone trail
      if (showTrue && data.present) {
        const trueTrailPositions =
          sceneElements.trueDroneTrail.geometry.attributes.position.array;
        for (let i = trueTrailPositions.length - 3; i >= 3; i -= 3) {
          trueTrailPositions[i] = trueTrailPositions[i - 3];
          trueTrailPositions[i + 1] = trueTrailPositions[i - 2];
          trueTrailPositions[i + 2] = trueTrailPositions[i - 1];
        }
        trueTrailPositions[0] = truePosition[0];
        trueTrailPositions[1] = truePosition[2];
        trueTrailPositions[2] = truePosition[1];
        sceneElements.trueDroneTrail.geometry.attributes.position.needsUpdate = true;
      }
    }
  } else {
    // Hide toggle control when not in simulation mode
    const toggleContainer = document.getElementById(
      "true-pos-toggle-container"
    );
    if (toggleContainer) {
      toggleContainer.style.display = "none";
    }

    // Hide true position marker
    if (sceneElements.trueDrone && sceneElements.trueDroneTrail) {
      sceneElements.trueDrone.visible = false;
      sceneElements.trueDroneTrail.visible = false;
    }
  }

  // Update drone visibility/opacity based on confidence
  const confidence = data.confidence || 0;
  sceneElements.drone.material.opacity = 0.3 + confidence * 0.7;
  sceneElements.drone.material.transparent = confidence < 0.8;

  // Create nodes if they don't exist
  if (state.config && state.config.nodes) {
    state.config.nodes.forEach((nodeConfig) => {
      if (!sceneElements.nodes[nodeConfig.id]) {
        createNodeMarker(nodeConfig.id, nodeConfig.position);
      }
    });
  }

  // Update info displays
  document.getElementById("pos-text").textContent =
    `X: ${position[0].toFixed(1)}m, Y: ${position[1].toFixed(1)}m, Z: ${position[2].toFixed(1)}m`;
  document.getElementById("conf-text").textContent =
    `${(confidence * 100).toFixed(1)}%`;
}

// ========================================
// Socket.IO Connection
// ========================================

function initSocket() {
  const socket = io();

  socket.on("connect", () => {
    console.log("Socket.IO connected");
    const statusEl = document.getElementById("status");
    statusEl.textContent = "Connected";
    statusEl.classList.add("connected");
    statusEl.classList.remove("disconnected");
  });

  socket.on("fusion_update", (data) => {
    if (!data) return;

    state.lastUpdate = new Date();
    document.getElementById("update-time").textContent =
      `Last update: ${state.lastUpdate.toLocaleTimeString()}`;

    updateScene(data);
    updateNodesTable(data.node_details || []);

    const totalEnergy = (data.node_details || []).reduce(
      (acc, node) => acc + (node.energy || 0),
      0
    );
    updateCharts(totalEnergy, data.confidence || 0);
  });

  socket.on("disconnect", () => {
    console.log("Socket.IO disconnected");
    const statusEl = document.getElementById("status");
    statusEl.textContent = "Disconnected";
    statusEl.classList.add("disconnected");
    statusEl.classList.remove("connected");
  });
}

// ========================================
// Initialization
// ========================================

window.addEventListener("DOMContentLoaded", async () => {
  console.log("Initializing Acoustic Drone Localization System...");

  await loadConfig();
  setupTabs();
  initCalibrationUI();
  startNodeHealthPolling();
  initThree();
  setupViewControls();

  // Setup true position toggle handler
  const truePositionToggle = document.getElementById("show-true-position");
  if (truePositionToggle) {
    truePositionToggle.addEventListener("change", (e) => {
      if (sceneElements.trueDrone && sceneElements.trueDroneTrail) {
        sceneElements.trueDrone.visible = e.target.checked;
        sceneElements.trueDroneTrail.visible = e.target.checked;
      }
    });
  }

  // Initialize empty charts
  Plotly.newPlot("energy-chart", [{ x: [], y: [] }], {
    margin: { t: 10, b: 30, l: 40, r: 10 },
    paper_bgcolor: "#21262d",
    plot_bgcolor: "#0d1117",
  });

  Plotly.newPlot("confidence-chart", [{ x: [], y: [] }], {
    margin: { t: 10, b: 30, l: 40, r: 10 },
    paper_bgcolor: "#21262d",
    plot_bgcolor: "#0d1117",
    yaxis: { range: [0, 1] },
  });

  initSocket();

  console.log("System initialized successfully");
});
