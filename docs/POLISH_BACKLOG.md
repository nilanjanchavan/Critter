# Critter Polish Backlog (Phase 7 Polish Tracking)

This document tracks visual, animation, and motion quality improvements scheduled for the Phase 7 Polish milestone.

---

## 1. Dog Animation & Asset Articulation
- [ ] **Seamless Joint Blending**:
  - Eliminate visual cutting/seams at the leg-to-body shoulder and hip junction when legs rotate during walking strides.
  - Apply soft alpha blending or an underbody skin layer so leg sockets stay seamlessly attached.
- [ ] **Stride & Frame Rate Interpolation**:
  - Add intermediate tweening frames (increase from 4-frame stride to 6-8 frames) for a silkier walking gait.
  - Implement a subtle turn-around / transitional frame when switching directions between left and right.
- [ ] **Handcrafted Spritesheet Import**:
  - Replace procedurally articulated 2D cutout parts with a dedicated multi-frame frame-by-frame spritesheet once a full sprite sheet is designed or selected.

---

## 2. Motion & Physics Polish
- [ ] **Smooth Acceleration / Deceleration**:
  - Introduce easing curves (ease-in / ease-out) when the pet starts and stops walking instead of instantaneous velocity jumps.
- [ ] **Ground Physics & Screen Edges**:
  - Add optional floor/dock snapping or resting against window edges/top bars.

