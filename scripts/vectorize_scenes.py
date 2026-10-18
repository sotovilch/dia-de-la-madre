#!/usr/bin/env python3
"""
Enhanced Multi-Layer Vectorizer (Octree + Cumulative Masking + Organic Foreground Separation)
Eliminates rectangular bounding-box seams and produces rich, 24-color Rockstar-grade pure SVG vectors.
"""
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from PIL import Image, ImageFilter
import numpy as np

def trace_mask_to_paths(mask_bool: np.ndarray, turdsize: int = 10, alphamax: float = 1.0, opttolerance: float = 0.35) -> list[tuple[str, str]]:
    img_arr = np.where(mask_bool, 0, 255).astype(np.uint8)
    pil_img = Image.fromarray(img_arr, mode='L')
    
    with tempfile.NamedTemporaryFile(suffix=".pgm", delete=False) as tmp_pgm:
        pgm_path = tmp_pgm.name
    svg_path = pgm_path + ".svg"
    
    try:
        pil_img.save(pgm_path)
        cmd = [
            "potrace",
            pgm_path,
            "-s",
            "-o", svg_path,
            "-t", str(turdsize),
            "-a", str(alphamax),
            "-O", str(opttolerance),
            "--flat"
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        tree = ET.parse(svg_path)
        root = tree.getroot()
        ns = {"svg": "http://www.w3.org/2000/svg"}
        g = root.find("svg:g", ns)
        paths = []
        if g is not None:
            transform = g.attrib.get("transform", "")
            for p in g.findall("svg:path", ns):
                d = p.attrib.get("d", "")
                if d:
                    paths.append((transform, d))
        return paths
    finally:
        if os.path.exists(pgm_path):
            os.remove(pgm_path)
        if os.path.exists(svg_path):
            os.remove(svg_path)


def vectorize_scene(
    scene_id: str,
    input_path: str,
    output_svg_path: str,
    target_width: int = 860,
    n_colors: int = 24,
    turdsize: int = 8
):
    im = Image.open(input_path).convert("RGB")
    orig_w, orig_h = im.size
    scale = target_width / float(orig_w)
    w = target_width
    h = int(round(orig_h * scale))
    
    im_resized = im.resize((w, h), Image.Resampling.LANCZOS)
    im_clean = im_resized.filter(ImageFilter.MedianFilter(size=3))
    arr = np.array(im_clean)
    
    # FASTOCTREE preserves vibrant pastel violets, magentas, and golden sunset tones much better than MEDIANCUT
    quantized = im_clean.quantize(colors=n_colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    palette_raw = quantized.getpalette()[:n_colors * 3]
    palette = [
        (palette_raw[i*3], palette_raw[i*3+1], palette_raw[i*3+2])
        for i in range(n_colors)
    ]
    q_arr = np.array(quantized)
    
    luminance = [0.299*r + 0.587*g + 0.114*b for (r, g, b) in palette]
    sorted_indices = sorted(range(n_colors), key=lambda idx: luminance[idx], reverse=True)
    
    # Group by luminance into 3 depth planes (sky/light, midtones, deep shadows + ink)
    # Without artificial rectangular crop boxes so NO seams ever appear!
    sky_paths = []
    mid_paths = []
    fg_paths = []
    
    for rank, idx in enumerate(sorted_indices):
        r, g, b = palette[idx]
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        lum = luminance[idx]
        
        if lum < 30:
            # Handled by high-precision ink pass
            continue
            
        mask = (q_arr == idx)
        if int(np.sum(mask)) < 35:
            continue
            
        traced = trace_mask_to_paths(mask, turdsize=turdsize, opttolerance=0.35)
        if rank < 6:
            for tr, d in traced:
                sky_paths.append((hex_color, tr, d))
        elif rank < 16:
            for tr, d in traced:
                mid_paths.append((hex_color, tr, d))
        else:
            for tr, d in traced:
                fg_paths.append((hex_color, tr, d))
                
    # High-detail comic ink pass directly from original luminance
    gray = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
    ink_mask = gray < 44
    ink_traced = trace_mask_to_paths(ink_mask, turdsize=4, opttolerance=0.22)
    
    base_r, base_g, base_b = palette[sorted_indices[0]]
    base_hex = f"#{base_r:02x}{base_g:02x}{base_b:02x}"
    
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%" class="gta-scene-svg {scene_id}" preserveAspectRatio="xMidYMid slice">',
        '  <defs>',
        f'    <linearGradient id="grad-{scene_id}" x1="0%" y1="0%" x2="0%" y2="100%">',
        '      <stop offset="0%" stop-color="#5e338c" />',
        '      <stop offset="40%" stop-color="#b96ea8" />',
        '      <stop offset="78%" stop-color="#f6ae65" />',
        f'      <stop offset="100%" stop-color="{base_hex}" />',
        '    </linearGradient>',
        '  </defs>',
        '  <!-- Layer 1: Sunset & Highlights -->',
        '  <g class="svg-layer-sky">',
        f'    <rect width="{w}" height="{h}" fill="url(#grad-{scene_id})" />'
    ]
    
    for color, tr, d in sky_paths:
        svg_lines.append(f'    <g transform="{tr}" fill="{color}" stroke="{color}" stroke-width="5" stroke-linejoin="round"><path d="{d}"/></g>')
    svg_lines.append('  </g>')
    
    svg_lines.append('  <!-- Layer 2: Rich Midtones & Palette -->')
    svg_lines.append('  <g class="svg-layer-mid">')
    for color, tr, d in mid_paths:
        svg_lines.append(f'    <g transform="{tr}" fill="{color}" stroke="{color}" stroke-width="4" stroke-linejoin="round"><path d="{d}"/></g>')
    svg_lines.append('  </g>')
    
    svg_lines.append('  <!-- Layer 3: Deep Cel-Shading & Rockstar Ink Outlines -->')
    svg_lines.append('  <g class="svg-layer-fg">')
    for color, tr, d in fg_paths:
        svg_lines.append(f'    <g transform="{tr}" fill="{color}" stroke="{color}" stroke-width="3" stroke-linejoin="round"><path d="{d}"/></g>')
    for tr, d in ink_traced:
        svg_lines.append(f'    <g transform="{tr}" fill="#12071c"><path d="{d}"/></g>')
    svg_lines.append('  </g>')
    
    svg_lines.append('</svg>')
    
    os.makedirs(os.path.dirname(output_svg_path), exist_ok=True)
    with open(output_svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))
    size_kb = os.path.getsize(output_svg_path) / 1024.0
    print(f"Generated {output_svg_path} ({w}x{h}) -> {size_kb:.1f} KB")

if __name__ == "__main__":
    scenes = [
        ("scene-01", "reference_images/IA - 01 Intro - GTA MAMÁ (Edición Leyenda).jpg", "src/assets/svg/scene-01-intro.svg", 820, 24, 8),
        ("scene-02", "reference_images/IA - 02 Acto I - Nadie se queda atrás.jpg", "src/assets/svg/scene-02-acto1.svg", 820, 24, 8),
        ("scene-03", "reference_images/IA - 03 Acto II - Salto sin red.jpg", "src/assets/svg/scene-03-acto2.svg", 820, 24, 8),
        ("scene-04", "reference_images/IA - 04 Acto III - Inquebrantable.jpg", "src/assets/svg/scene-04-acto3.svg", 820, 24, 8),
        ("scene-05", "reference_images/IA - 05 Acto IV - Level 58: Creando Vida con Hilos.jpg", "src/assets/svg/scene-05-acto4.svg", 800, 24, 6),
        ("scene-06", "reference_images/IA - 06 Outro - Misión de Mañana_ Celebrar.jpg", "src/assets/svg/scene-06-outro.svg", 920, 24, 8),
    ]
    for sid, inp, outp, tw, nc, ts in scenes:
        vectorize_scene(sid, inp, outp, target_width=tw, n_colors=nc, turdsize=ts)
