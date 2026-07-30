# Infographic Renderer

This sub-app renders Muddy's Top 10 infographic assets.

- Keep rendering deterministic.
- Do not use generative image models for final PNG output.
- Do not fetch remote fonts, styles, images, or scripts at render time.
- Keep layout tokens centralised in `src/template/chart.css`.
- Treat `../info-graphic-example.png` as the source design reference, not a runtime dependency.
- Preserve the target output size: `1280x720` PNG.
- Prefer failing validation over inventing missing weekly chart data.

