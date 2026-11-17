"""
Renderer script to generate a high-definition terminal demo GIF for GlueHealer.
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 980, 620
LINE_H = 21
TOP_MARGIN = 50
LEFT_MARGIN = 24

font = ImageFont.truetype("C:\\Windows\\Fonts\\consola.ttf", 15)
font_bold = ImageFont.truetype("C:\\Windows\\Fonts\\consolab.ttf", 15)
title_font = ImageFont.truetype("C:\\Windows\\Fonts\\consola.ttf", 13)

BG_COLOR = (24, 25, 38)
HEADER_COLOR = (18, 19, 29)
BORDER_COLOR = (49, 50, 68)
TEXT_COLOR = (205, 214, 244)
DIM_COLOR = (147, 154, 183)
GREEN = (166, 227, 161)
RED = (243, 139, 168)
YELLOW = (249, 226, 175)
BLUE = (137, 180, 250)
PURPLE = (203, 166, 247)

def create_base_canvas():
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    # Header bar
    draw.rectangle([0, 0, W, 36], fill=HEADER_COLOR)
    draw.line([0, 36, W, 36], fill=BORDER_COLOR, width=1)
    # Window controls
    draw.ellipse([14, 12, 26, 24], fill=(237, 106, 94))
    draw.ellipse([34, 12, 46, 24], fill=(245, 191, 79))
    draw.ellipse([54, 12, 66, 24], fill=(98, 197, 84))
    draw.text((W // 2 - 100, 10), "gluehealer — zsh — 980x620", fill=DIM_COLOR, font=title_font)
    return img, draw

# Content definition: (text, color, is_bold)
STEPS = [
    # Step 1: Prompt
    [
        ("swaraj@dataops:~/GlueHealer$ ", BLUE, True),
        ("python -m gluehealer demo --auto-approve", TEXT_COLOR, False),
    ],
    # Step 2: Running & failure
    [
        ("🎭 Running GlueHealer in OFFLINE DEMO mode (Zero API keys needed)", PURPLE, False),
        ("🔍 Running job 'broken_etl' to check for failures...", DIM_COLOR, False),
        ("   Script: sample_jobs/broken_etl.py", DIM_COLOR, False),
        ("", TEXT_COLOR, False),
        ("❌ Job 'broken_etl' failed. Starting healing pipeline...", RED, True),
        ("Traceback (most recent call last):", RED, False),
        ("  File \"sample_jobs/broken_etl.py\", line 30, in transform_data", RED, False),
        ("    \"total\": int(record[\"quantity\"]) * float(record[\"unit_price\"])", RED, False),
        ("KeyError: 'unit_price'", RED, True),
    ],
    # Step 3: Context & RCA
    [
        ("", TEXT_COLOR, False),
        ("📋 Context Builder: read script (1769 chars)", BLUE, False),
        ("🔍 RCA Analyzer: calling LLM for root cause analysis...", BLUE, False),
        ("   ✅ RCA complete: Column 'unit_price' renamed to 'price' in source", GREEN, True),
    ],
    # Step 4: Patch Generator & Diff
    [
        ("🩹 Patch Generator: generating corrected script & diff...", YELLOW, False),
        ("   ✅ Patch generated (unified diff):", GREEN, True),
        ("--- original", DIM_COLOR, False),
        ("+++ patched", DIM_COLOR, False),
        ("@@ -30,1 +30,1 @@", BLUE, False),
        ("-   \"total\": int(record[\"quantity\"]) * float(record[\"unit_price\"]),", RED, False),
        ("+   \"total\": int(record[\"quantity\"]) * float(record[\"price\"]),", GREEN, True),
        ("  ⚡ Auto-approving patch (--auto-approve enabled)", PURPLE, False),
    ],
    # Step 5: Versioned Apply & Retry
    [
        ("", TEXT_COLOR, False),
        ("📦 Apply Patch: versioned copy → job_versions/broken_etl/v1.py", BLUE, False),
        ("🔄 Retry Runner: executing 'broken_etl' (attempt 1/3)...", YELLOW, False),
        ("   ✅ Job succeeded! Transformed 5 records to sales_transformed.json", GREEN, True),
    ],
    # Step 6: Summary banner
    [
        ("", TEXT_COLOR, False),
        ("=" * 68, DIM_COLOR, False),
        ("🎉 JOB HEALED SUCCESSFULLY", GREEN, True),
        ("   Attempts needed:  1", TEXT_COLOR, False),
        ("   Patches applied:  1", TEXT_COLOR, False),
        ("   Healed script:    job_versions/broken_etl/v1.py", BLUE, True),
        ("   Original script:  sample_jobs/broken_etl.py (unchanged / zero overwrite)", GREEN, False),
        ("=" * 68, DIM_COLOR, False),
    ]
]

frames = []
durations = [1200, 1800, 1800, 2200, 1800, 4500]

accumulated_lines = []
for idx, step_lines in enumerate(STEPS):
    accumulated_lines.extend(step_lines)
    img, draw = create_base_canvas()

    y = TOP_MARGIN
    for item in accumulated_lines:
        text, color, is_bold = item
        f = font_bold if is_bold else font
        draw.text((LEFT_MARGIN, y), text, fill=color, font=f)
        y += LINE_H

    # Add cursor on active frame if not last
    if idx < len(STEPS) - 1:
        draw.rectangle([LEFT_MARGIN, y, LEFT_MARGIN + 9, y + 15], fill=TEXT_COLOR)

    frames.append(img)

# Save animated GIF
os.makedirs("assets", exist_ok=True)
out_path = os.path.join("assets", "demo.gif")
frames[0].save(
    out_path,
    save_all=True,
    append_images=frames[1:],
    duration=durations,
    loop=0,
    optimize=True,
)
print(f"✅ Generated {out_path} ({os.path.getsize(out_path)} bytes)")
