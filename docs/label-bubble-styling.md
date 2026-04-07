# MapLibre Overlay Styling Documentation

This document explains the technical implementation of label backgrounds (bubbles) using non-SDF 9-slice sprites in our modular build pipeline.

## 1. Sprite Generation (`scripts/generate_sdf_icon.py`)
Although named "SDF", we now generate a standard **RGBA PNG** for the label background because MapLibre has known scaling bugs when combining `icon-text-fit` with `sdf: true`.

*   **Source:** `assets/sprites/sdf/label-bubble.png`
*   **Dimensions:** 64x64 pixels.
*   **Radius:** 5.0 pixels (defined in `scripts/generate_sdf_icon.py`).
*   **Color:** White (`#ffffff`) with a slight transparency (managed via `icon-opacity` in the style).

## 2. Sprite Metadata (`scripts/build_sprites.py`)
To allow the bubble to stretch without distorting the rounded corners, we use 9-slice metadata in the `sprite.json`.

*   **`stretchX` / `stretchY`:** `[[5, 59]]`. This tells MapLibre that the area between pixel 5 and 59 is "stretchy". The first 5 pixels and the last 5 pixels (the corners) remain at a 1:1 scale.
*   **`content`:** `[5, 5, 59, 59]`. This defines the "safe zone" where the text is placed. MapLibre ensures the text (plus padding) fits inside this box.
*   **`sdf`:** `false`. Mandatory to avoid the "bloating" bug in MapLibre GL JS.

## 3. Style Configuration (`scripts/style_builders/build_rd.py`)
The visual appearance is controlled via the Symbol Layer layout and paint properties.

### Layout Properties
*   **`icon-image`:** `"label-bubble"`
*   **`icon-text-fit`:** `"both"`. Scales the icon to fit the text width and height.
*   **`icon-text-fit-padding`:** `[1, 3, 1, 3]`. (Top, Right, Bottom, Left). This is the space between the text and the start of the "stretchy" zone of the bubble.
*   **`text-variable-anchor`:** `["top"]`.
*   **`text-radial-offset`:** `1.5`. Moves the text (and thus the bubble) away from the anchor point (the pin).
*   **`icon-size`:** **OMITTED**. Setting `icon-size` conflicts with `icon-text-fit` and causes incorrect scaling.

### Paint Properties
*   **`text-color`:** `#111827` (Dark grey/black for contrast).
*   **`icon-opacity`:** `0.95`. Provides slight transparency to the background.

## 4. Calculation Formula
The final size of a rendered bubble on the map is:

*   **Width:** `TextWidth + (2 × PaddingRight) + (2 × Radius)`
*   **Height:** `TextHeight + (2 × PaddingTop) + (2 × Radius)`

With current settings (Radius 5px, Padding 3px horizontal, 1px vertical):
*   **Total width overhead:** `6px (padding) + 10px (corners) = 16px`
*   **Total height overhead:** `2px (padding) + 10px (corners) = 12px`
