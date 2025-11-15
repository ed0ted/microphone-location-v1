# Direction Estimation Algorithm

This document describes exactly how the direction estimation algorithm works in the acoustic drone localization system.

## Overview

The system uses an **energy-weighted vector sum** method to estimate the direction of arrival (DOA) of sound from a drone. This method leverages the spatial arrangement of microphones and their relative signal energy levels to determine direction.

---

## Algorithm Components

### 1. Microphone Array Configuration

Each node has a **triangle array** (3 microphones) or **tetrahedron array** (4 microphones) arranged in 3D space. Each microphone has an associated **directional vector** that indicates its primary sensitivity direction.

**Example: Triangle Array (Node 1)**
```
Mic 0: Position [0.15, 0.0, 0.0]   → Vector [0.0, 0.0, 1.0]    (Up)
Mic 1: Position [-0.075, 0.13, 0.0] → Vector [0.0, 0.0, 1.0]   (Up)
Mic 2: Position [-0.075, -0.13, 0.0] → Vector [0.0, 0.0, 1.0]  (Up)
```

**Note**: All microphones point directly upward `[0, 0, 1]` for optimal detection of elevated sound sources (drones).

The vectors are **normalized** (unit length) and stored in the `DirectionEstimator` class.

---

## 2. Signal Processing Pipeline

### Step 1: RMS Energy Calculation

For each time window (typically 1.6 seconds at 860 Hz sample rate):

```python
# Calculate RMS (Root Mean Square) energy for each microphone
rms[i] = sqrt(mean(window[i]^2))
```

This gives us the **signal strength** at each microphone: `rms = [rms_0, rms_1, rms_2, ...]`

### Step 2: Noise Floor Subtraction

The background noise level is tracked using an exponential moving average:

```python
# Noise tracker updates only when no signal is present
if not present:
    noise_level = (1 - α) * noise_level + α * rms
    # where α = 0.01 (slow adaptation rate)
```

The **signal above noise** is calculated:

```python
signal = max(rms - noise_level, 0.0)
```

This removes the baseline noise floor, leaving only the **signal energy** that represents the drone sound.

### Step 3: Energy-to-Weight Conversion

The `signal` array becomes the **weights** for direction estimation:

```python
weights = signal  # [weight_0, weight_1, weight_2, ...]
weights = max(weights, 0.0)  # Ensure non-negative
```

---

## 3. Direction Estimation Algorithm

### Core Formula: Weighted Vector Sum

The direction is estimated using a **weighted sum** of the microphone direction vectors:

```python
direction = Σ(weight[i] × mic_vector[i])  for all microphones i
direction = direction / ||direction||  # Normalize to unit vector
```

### Mathematical Details

1. **Initialization** (`DirectionEstimator.__init__`):
   ```python
   # Normalize all microphone direction vectors to unit length
   mic_vectors_normalized = mic_vectors / ||mic_vectors||
   ```

2. **Estimation** (`DirectionEstimator.estimate`):
   ```python
   def estimate(weights):
       # Ensure non-negative weights
       weights = max(weights, 0.0)
       
       # Calculate weighted sum
       direction = sum(weights[i] × mic_vectors_normalized[i])
       # This is a 3D vector: [x, y, z]
       
       # Normalize result to unit vector
       direction_normalized = direction / ||direction||
       
       # Calculate confidence (based on total signal energy)
       confidence = min(sum(weights), 1.0)
       
       return direction_normalized, confidence
   ```

### Example Calculation

**Scenario**: Drone is to the **right** and **above** the node.

**Microphone Vectors**:
- Mic 0: `[0.0, 0.0, 1.0]` → points Up
- Mic 1: `[0.0, 0.0, 1.0]` → points Up  
- Mic 2: `[0.0, 0.0, 1.0]` → points Up

**Signal Weights** (after noise subtraction):
- Mic 0: `0.8` (strong signal - closest to drone)
- Mic 1: `0.3` (moderate signal - medium distance)
- Mic 2: `0.5` (moderate-strong signal)

**Calculation**:
```
direction = 0.8 × [0.0, 0.0, 1.0] + 0.3 × [0.0, 0.0, 1.0] + 0.5 × [0.0, 0.0, 1.0]
         = [0.0, 0.0, 0.8] + [0.0, 0.0, 0.3] + [0.0, 0.0, 0.5]
         = [0.0, 0.0, 1.6]
         
||direction|| = sqrt(0.0² + 0.0² + 1.6²) = 1.6

direction_normalized = [0.0/1.6, 0.0/1.6, 1.6/1.6]
                      = [0.0, 0.0, 1.0]
```

**Result**: Direction vector `[0.0, 0.0, 1.0]` points **directly upward**, indicating the sound source is above the node. With all vectors pointing upward, the direction estimate is purely vertical, and horizontal direction information comes from the relative signal strengths at different microphone positions (spatial diversity).

---

## 4. Why This Works

### Physical Principle

When a sound source is closer to one microphone:
1. That microphone receives **higher signal energy** (inverse square law)
2. The microphone pointing toward the source may have **higher sensitivity** (directional response)
3. Other microphones receive **less energy** or **lower sensitivity**

The **weighted vector sum** naturally combines these effects:
- Strong signals from mics pointing toward the source **pull** the direction vector that way
- Weak signals from mics pointing away have **less influence**

### Geometric Interpretation

```
     Drone
      ✈️
       \
        \
         \
          \  High energy → Strong weight
           \
            \
             Mic 0 (vector points this way)
            /
           /  Low energy → Weak weight
          /
         /
        /
       Mic 1 (vector points away)
```

The **resultant vector** (weighted sum) points toward the direction where the **strongest signals** originate, which is where the drone is located.

---

## 5. Confidence Calculation

The **direction confidence** is calculated as:

```python
confidence = min(sum(weights), 1.0)
```

**Meaning**:
- **High confidence** (near 1.0): Strong signal on multiple mics → clear direction
- **Low confidence** (near 0.0): Weak or uniform signals → ambiguous direction

**Typical values**:
- No drone: confidence = 0.0
- Weak drone (distant): confidence ≈ 0.1-0.3
- Strong drone (close): confidence ≈ 0.5-1.0

---

## 6. Coordinate System

The direction vector is in the **local node coordinate system**:
- **X-axis**: East (positive) / West (negative)
- **Y-axis**: North (positive) / South (negative)  
- **Z-axis**: Up (positive) / Down (negative)

This local direction must be transformed to the **global coordinate system** for fusion at the server. The server uses the node's `global_position` and orientation to perform this transformation.

---

## 7. Algorithm Limitations

### Assumptions

1. **Single source**: Works best with one dominant sound source
2. **Far-field approximation**: Sound source is far enough that wavefront is approximately planar
3. **Energy-based**: Relies on relative signal strengths, not phase/time differences

### Limitations

1. **Ambiguity**: For symmetric microphone arrangements, front/back ambiguity may exist
2. **Distance dependency**: Accuracy decreases with distance (weaker signals)
3. **Noise sensitivity**: High background noise reduces accuracy
4. **Multi-path**: Reflections can confuse direction estimation

### Why Not TDoA?

The system uses **energy-based** direction estimation rather than **Time Difference of Arrival (TDoA)** because:

1. **Hardware constraints**: ADS1115 ADC samples sequentially (not simultaneously), making accurate timing difficult
2. **Low sample rate**: 860 Hz sample rate limits time resolution (~1.16 ms)
3. **Simplicity**: Energy-based method is simpler and more robust to noise
4. **Acceptable accuracy**: For coarse localization (meter-level), energy-based method is sufficient

---

## 8. Code Flow

### Complete Pipeline

```
Audio Samples (3 channels × N samples)
        ↓
[RingBuffer] Accumulate 1.6 seconds of samples
        ↓
[RMS Calculation] rms = sqrt(mean(samples²))
        ↓
[Noise Subtraction] signal = max(rms - noise_floor, 0)
        ↓
[DirectionEstimator.estimate] weights = signal
        ↓
[Weighted Vector Sum] direction = Σ(weights[i] × mic_vectors[i])
        ↓
[Normalize] direction = direction / ||direction||
        ↓
[Calculate Confidence] confidence = min(sum(weights), 1.0)
        ↓
Direction Vector [x, y, z] + Confidence
```

### Key Code Locations

- **DirectionEstimator**: `node/dsp.py` lines 72-87
- **Weighted Sum**: `node/dsp.py` line 83: `direction = (weights[:, None] * self.vecs).sum(axis=0)`
- **Signal Processing**: `node/dsp.py` lines 137-168 (`_emit_frame` method)
- **Microphone Vectors**: Defined in `configs/node-*.yaml` (`triangle_vectors` or `tetrahedron_vectors`)

---

## 9. Parameter Tuning

### Microphone Vector Configuration

The microphone vectors determine the **directionality** of the estimate:

- **Wide vectors**: More sensitive to horizontal direction
- **Upward bias**: All vectors have positive Z-component (pointing up) for detecting elevated sources

**Default configuration (all pointing upward)**:
```yaml
triangle_vectors:
  - [0.0, 0.0, 1.0]      # All microphones point directly upward
  - [0.0, 0.0, 1.0]      # Optimal for detecting elevated sources (drones)
  - [0.0, 0.0, 1.0]      # Horizontal direction inferred from mic positions
```

**Note**: With all vectors pointing upward, the direction estimate will always have a strong vertical component. Horizontal direction information comes from the relative signal strengths at different microphone positions rather than directional sensitivity.

### Noise Floor Parameters

- **α (alpha)**: Noise adaptation rate (default: 0.01)
  - Lower = slower adaptation, more stable
  - Higher = faster adaptation, more sensitive to environment changes

---

## 10. Testing and Validation

To validate direction estimation:

1. **Known source test**: Place speaker at known position, verify estimated direction
2. **Symmetry test**: Rotate speaker around node, check if direction follows
3. **Distance test**: Vary distance, check if direction remains consistent
4. **Multi-source test**: Multiple speakers, verify system handles ambiguity

The direction estimation accuracy is validated at the **fusion server** level, where multiple nodes' direction estimates are combined with their positions to triangulate the 3D location.

---

## Summary

The direction estimation algorithm is a **simple but effective** energy-weighted vector sum method that:

1. ✅ Leverages microphone array geometry
2. ✅ Uses relative signal strengths (not timing)
3. ✅ Works with sequential ADC sampling
4. ✅ Provides reasonable accuracy for coarse localization
5. ✅ Computationally efficient (real-time on Pi Zero)

The estimated direction vector is used by the fusion server to refine the 3D position estimate using a grid search algorithm that minimizes both energy distribution errors and direction alignment errors.

