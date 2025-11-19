# Tool: image_generation

Description (FR): Génère des images via l’API WaveSpeed (modèles SeeDance et NanoBanana) pour des visuels marketing, maquettes et bannières. Le tool lit sa configuration depuis Settings > Image Generation et accepte des overrides dans `tool_args`.

Description (EN): Generates images using WaveSpeed API (SeeDance and NanoBanana models) for marketing visuals, mockups and banners. Reads defaults from Settings > Image Generation and supports per-call overrides in `tool_args`.

Arguments:
- prompt (string, required): Detailed description in English for best results.
- negative_prompt (string, optional): Undesired elements (e.g. "blurry, watermark, text errors").
- width (int, optional): Pixels. Default from settings. Range typically 512–2048.
- height (int, optional): Pixels. Default from settings. Range typically 512–2048.
- steps (int, optional): 10–100. Higher = better quality but slower. Default from settings.
- batch_size (int, optional): 1–5. Default from settings. Clamped to max 5.
- model (string, optional): Overrides default settings ("seedance" | "nanobanana").

Behavior:
- Uses WaveSpeed endpoint POST https://api.wavespeed.ai/v1/generate with Authorization: Bearer <api_key>.
- Returns local paths to saved images and metadata.

Examples:

```json
{
  "thoughts": ["User needs 5 professional Instagram posts"],
  "headline": "Génération de visuels pour posts sociaux",
  "tool_name": "image_generation",
  "tool_args": {
    "prompt": "Instagram post design for tech startup, modern gradient background with abstract geometric shapes, professional typography space, vibrant blue and purple colors, 4K quality",
    "negative_prompt": "text, watermark, blurry, low quality",
    "width": 1080,
    "height": 1080,
    "batch_size": 5
  }
}
```

```json
{
  "thoughts": ["Créer une maquette de carte de visite élégante"],
  "headline": "Business card mockup",
  "tool_name": "image_generation",
  "tool_args": {
    "prompt": "elegant business card mockup, minimalist design, gold foil accents on white background, luxury brand aesthetic, high-end photography",
    "width": 1024,
    "height": 768,
    "steps": 40,
    "batch_size": 3
  }
}
```

```json
{
  "thoughts": ["Bannière Web héro pour landing page"],
  "headline": "Web Banner",
  "tool_name": "image_generation",
  "tool_args": {
    "prompt": "website hero banner, clean modern layout, abstract tech background, ample whitespace for headline and CTA, blue and white color scheme, high contrast, professional style",
    "width": 1200,
    "height": 628,
    "steps": 30,
    "batch_size": 2
  }
}
```

Bonnes pratiques / Best practices:
- Détailler le style, la palette, l’ambiance et l’usage.
- Écrire les prompts en anglais pour des résultats plus prévisibles.
- Utiliser negative_prompt pour éviter les défauts (blurry, watermark, distorted text).
- Dimensions typiques: Instagram 1080x1080; Facebook 1200x628; Twitter/X 1024x512.
- steps: 30 par défaut; 40–50 pour qualité finale; baisser pour itérations rapides.
- batch_size: 5 pour variantes, 1–2 pour itérations rapides.

Erreurs courantes / Common errors:
- "Missing WaveSpeed API key" → Configurez la clé dans Settings > Image Generation.
- "WaveSpeed image generation is disabled" → Activez l’intégration dans Settings.
- 401 Unauthorized → Clé API invalide.
- 429 Rate limit exceeded → Attendre avant de réessayer.
- 5xx Server error → Réessaie plus tard ou réduire batch/steps.
