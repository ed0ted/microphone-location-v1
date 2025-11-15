# Testing True Position Visualization Feature

## Quick Test Guide

### Prerequisites
- All dependencies installed
- Server and node configs properly set up
- Ports available (8080 for web, 5005 for UDP)

### Test 1: Basic Functionality

**Steps:**
1. Start fusion server:
   ```bash
   cd ~/projects/microphone-location-v2
   source venv-server/bin/activate
   python -m server.run_all --config configs/server.yaml --verbose
   ```

2. Verify server starts without errors
3. Open http://localhost:8080 in browser
4. Verify toggle is NOT visible (simulation not running yet)

**Expected Result:**
✅ Web interface loads
✅ No green marker visible
✅ No "Show True Position" toggle visible

### Test 2: Enable Simulation Mode

**Steps:**
1. In a new terminal, start drone simulator:
   ```bash
   source venv-server/bin/activate
   python scripts/drone_position_sim.py --pattern circle --speed 2.0 --height 5.0
   ```

2. Check that state file is created:
   ```bash
   cat /tmp/drone_sim_state.json
   # Should show: {"position": [x, y, z], "timestamp": ...}
   ```

3. Start node agents (3 terminals):
   ```bash
   # Terminal 1
   source venv-node/bin/activate
   python -m node.node_agent --config configs/node-1.yaml --verbose run
   
   # Terminal 2
   source venv-node/bin/activate
   python -m node.node_agent --config configs/node-2.yaml --verbose run
   
   # Terminal 3
   source venv-node/bin/activate
   python -m node.node_agent --config configs/node-3.yaml --verbose run
   ```

4. Return to browser (http://localhost:8080)

**Expected Result:**
✅ "Show True Position" toggle appears in 3D view controls
✅ Green sphere visible (true position)
✅ Red sphere visible (estimated position)
✅ Both markers moving
✅ Both trails rendering

### Test 3: Toggle Functionality

**Steps:**
1. With simulation running, click "Show True Position" checkbox to uncheck it
2. Observe the scene
3. Click checkbox again to check it
4. Observe the scene

**Expected Result:**
✅ Green marker disappears when unchecked
✅ Green trail disappears when unchecked
✅ Green marker reappears when checked
✅ Red marker always visible (unaffected)

### Test 4: Visual Comparison

**Steps:**
1. With both markers visible, observe their positions
2. Watch them move over time
3. Note the distance between red and green markers

**Expected Result:**
✅ Green marker follows a smooth circle path
✅ Red marker follows approximately the same path
✅ Some offset visible (localization error)
✅ Markers maintain consistent visual appearance
✅ Glow effects pulsing at different rates

### Test 5: Simulation Stop Behavior

**Steps:**
1. Stop the drone simulator (Ctrl+C in its terminal)
2. Wait ~5 seconds
3. Observe the web interface

**Expected Result:**
✅ Toggle control remains visible initially
✅ Green marker stops updating (frozen at last position)
✅ Red marker continues updating (from node data)

### Test 6: Restart Simulation

**Steps:**
1. Restart drone simulator:
   ```bash
   python scripts/drone_position_sim.py --pattern figure8 --speed 3.0
   ```

2. Observe the web interface

**Expected Result:**
✅ Green marker resumes movement
✅ New pattern visible (figure-8)
✅ Both markers tracking new path
✅ Toggle remains functional

### Test 7: Pattern Verification

**Steps:**
1. Stop drone simulator
2. Restart with hover pattern:
   ```bash
   python scripts/drone_position_sim.py --pattern hover --height 3.0
   ```

**Expected Result:**
✅ Green marker stationary at hover position
✅ Red marker may jitter slightly (noise in estimation)
✅ Both markers at approximately same Z height (3m)

### Test 8: Browser Console Check

**Steps:**
1. Open browser developer tools (F12)
2. Go to Console tab
3. Watch for messages while simulation running

**Expected Result:**
✅ No JavaScript errors
✅ WebSocket "fusion_update" events received
✅ No warnings about missing data fields

### Test 9: Different Browsers

**Steps:**
1. Test in Chrome/Edge
2. Test in Firefox
3. Test in Safari (if available)

**Expected Result:**
✅ Feature works consistently across browsers
✅ Toggle styling appears correct
✅ 3D rendering performs smoothly

### Test 10: Node Shutdown Behavior

**Steps:**
1. With all nodes running and markers visible
2. Stop one node (Ctrl+C)
3. Wait for detection timeout (~2 seconds)
4. Observe markers

**Expected Result:**
✅ Green marker continues (from simulation file)
✅ Red marker may become less accurate (fewer inputs)
✅ Confidence score decreases
✅ System continues functioning

## Troubleshooting

### Toggle Not Appearing

**Check:**
```bash
# Verify state file exists
ls -la /tmp/drone_sim_state.json

# Check file contents
cat /tmp/drone_sim_state.json

# Check permissions
ls -l /tmp/drone_sim_state.json

# Should be readable by your user
```

**Server Logs:**
```bash
# Look for simulation_mode in server logs
# Should see true_position data in fusion updates
```

### Green Marker Not Moving

**Check:**
1. Is `drone_position_sim.py` still running?
2. Check simulator terminal for errors
3. Verify state file is being updated:
   ```bash
   watch -n 0.5 cat /tmp/drone_sim_state.json
   ```

### Markers Far Apart

This is expected! The localization algorithm has inherent error due to:
- Inverse square law approximation
- Limited node count
- Audio noise
- Direction estimation accuracy

Typical error: 3-8 meters horizontally, 5-10 meters vertically

### Performance Issues

If rendering is slow:
1. Reduce simulator rate: `--rate 10.0`
2. Reduce trail length (edit main.js: change 300 to 100)
3. Close other browser tabs
4. Check CPU usage of all processes

## Success Criteria

Feature is working correctly if:
- ✅ Toggle appears only in simulation mode
- ✅ Green marker tracks simulator position
- ✅ Toggle controls visibility
- ✅ Both trails render smoothly
- ✅ No JavaScript errors
- ✅ No Python exceptions in server logs
- ✅ Feature auto-disables when simulation stops

## Performance Benchmarks

Expected metrics:
- WebSocket latency: < 50ms
- Frame rate: 30-60 FPS
- Server CPU: 10-20% per core
- Memory: < 200MB for server process
- File read overhead: negligible (cached)

## Known Issues

1. **Initial Position Jump**: Green marker may jump on first update - this is normal as it starts at origin
2. **Trail Reset**: Trails don't persist across page reloads
3. **Toggle State**: Not saved between sessions (intentional)

## Reporting Issues

If tests fail, please report:
1. Which test failed
2. Error messages (console and terminal)
3. Browser and version
4. System OS and Python version
5. Relevant log excerpts

