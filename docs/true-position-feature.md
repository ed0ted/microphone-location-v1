# True Position Visualization Feature

## Overview

This development feature shows the actual drone position (ground truth) alongside the estimated position during audio simulation, allowing real-time visual comparison of localization accuracy.

## Implementation Summary

### Backend Changes

#### 1. State Store (`server/state_store.py`)
- Added `true_position: Optional[List[float]]` field to `FusionState`
- Added `simulation_mode: bool` field to track when running in simulation

#### 2. Localization Engine (`server/localization.py`)
- Added `simulation_state_file` parameter (defaults to `/tmp/drone_sim_state.json`)
- Implemented `_read_true_position()` method to read ground truth from simulation
- Updated `_localize()` to include true position in fusion state
- Automatically detects simulation mode when state file exists

### Frontend Changes

#### 1. HTML Template (`server/web/templates/index.html`)
- Added toggle checkbox: `<input type="checkbox" id="show-true-position" checked />`
- Positioned in view controls section
- Hidden by default, shown automatically in simulation mode

#### 2. CSS Styles (`server/web/static/styles.css`)
- Added `.toggle-label` styling for the checkbox control
- Hover effects and accent colors (green theme)
- Responsive sizing

#### 3. JavaScript (`server/web/static/main.js`)
- Created green true position marker (sphere + glow + trail)
- Added references to `sceneElements` object
- Updated `updateScene()` to:
  - Show/hide toggle based on simulation_mode
  - Position green marker at true_position
  - Update trail for ground truth path
  - Respect toggle checkbox state
- Added pulsing animation for green marker
- Added event listener for toggle changes

### Documentation Updates

#### `docs/audio-simulation.md`
- Added "Development Feature" section
- Documented visual markers (red vs green)
- Added troubleshooting for toggle visibility
- Explained automatic detection behavior

## Visual Design

### Colors
- **Red Sphere** 🔴: Estimated position (from fusion algorithm)
- **Green Sphere** 🟢: True position (from simulation)
- **Blue Spheres** 🔵: Node positions

### Transparency
- Green marker is slightly transparent (80% opacity) to see both markers when overlapping
- Both markers have pulsing glow effects with different frequencies

### Trails
- Both positions leave trails to show movement history
- Red trail: Estimated path
- Green trail: Actual path

## Usage

### Running the Feature

1. Start the fusion server:
   ```bash
   python -m server.run_all --config configs/server.yaml
   ```

2. Start the drone position simulator:
   ```bash
   python scripts/drone_position_sim.py --pattern circle --speed 2.0
   ```

3. Start node agents in simulator mode:
   ```bash
   python -m node.node_agent --config configs/node-1.yaml run
   python -m node.node_agent --config configs/node-2.yaml run
   python -m node.node_agent --config configs/node-3.yaml run
   ```

4. Open web interface: http://localhost:8080
   - The "Show True Position" toggle will appear automatically
   - Green marker shows actual drone position
   - Red marker shows estimated position

### Toggling Visibility

- Click the checkbox to show/hide the green marker
- Setting persists during the session
- Useful to focus on estimated position or compare both

## Technical Details

### Data Flow

```
drone_position_sim.py
        ↓
/tmp/drone_sim_state.json
        ↓
LocalizationEngine._read_true_position()
        ↓
FusionState.true_position
        ↓
WebSocket → fusion_update event
        ↓
main.js → updateScene()
        ↓
Three.js green sphere
```

### Automatic Detection

The feature automatically enables when:
1. `/tmp/drone_sim_state.json` file exists
2. File contains valid JSON with 'position' field
3. File is readable by fusion server

When any condition fails, the toggle is hidden and the feature is disabled.

### Performance Impact

- Minimal: Only reads state file once per localization cycle
- Cached with 50ms interval to avoid excessive file I/O
- No performance impact when not in simulation mode

## Benefits for Development

1. **Visual Debugging**: See localization errors in real-time
2. **Algorithm Tuning**: Adjust parameters while observing effect on accuracy
3. **Scenario Testing**: Test different drone patterns and observe performance
4. **Error Measurement**: Visually estimate position error distance
5. **Confidence Validation**: Correlate confidence scores with actual error

## Future Enhancements

Potential additions:
- Display numerical error distance between markers
- Plot error over time in charts
- Color-code estimated marker based on error magnitude
- Add error statistics (mean, max, RMS error)
- Export error data for analysis

## Notes

- Feature only active during simulation, invisible during real hardware operation
- No changes needed to simulation scripts or node configs
- Backward compatible: Works with existing simulation setup
- Toggle state not persisted between sessions

