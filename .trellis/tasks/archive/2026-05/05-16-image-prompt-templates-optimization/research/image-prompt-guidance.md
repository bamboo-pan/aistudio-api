# Image Prompt Guidance Research

## Sources

- Google Gemini API Imagen guide (`https://ai.google.dev/gemini-api/docs/imagen`)
- OpenAI image generation guide (`https://developers.openai.com/api/docs/guides/image-generation`)

## Relevant Official Guidance

- Google recommends prompts that combine subject, context/background, and style, then iteratively refine with more details.
- Google lists broad style families and modifiers: photography, illustration/art, historical art references, materials/shapes, quality modifiers, camera position, lighting, lens, film type, and aspect ratio.
- Google examples explicitly include phrases like `A photo of...`, `A painting of...`, `A sketch of...`, `A digital art of...`, art movements such as impressionism/renaissance/pop art, and quality terms such as high-quality, 4K, HDR, studio photo, professional, detailed.
- OpenAI's image guide describes prompt revision as a supported image-generation concept: the model can revise prompts for improved performance and expose a `revised_prompt` field in image-generation calls.
- OpenAI recommends iterative image workflows and supports making follow-up style changes such as `Now make it look realistic`.

## Style Template Set For This Project

Use a compact, authoritative set that maps directly to official prompt families without pretending to be a model-native enum:

- `none`: No style template. Preserve the user's prompt as-is.
- `photorealistic`: Photography/realistic image. Emphasize photo, natural materials, lens/camera, lighting, depth of field, and realistic detail.
- `comic`: Comic / graphic illustration. Emphasize clean line art, bold readable shapes, panels or cover composition, controlled colors, and expressive character/action beats.
- `digital-art`: Digital art / concept illustration. Emphasize stylized rendering, cinematic mood, detailed environment, and polished art direction.
- `watercolor`: Watercolor / soft traditional media. Emphasize translucent washes, paper texture, soft edges, and organic color blending.
- `oil-painting`: Oil painting / classical painting. Emphasize brushwork, layered paint, rich values, and art historical composition.
- `anime`: Anime / cel animation. Emphasize cel shading, expressive characters, clean silhouettes, and animated-film lighting.
- `3d-render`: 3D render / product visualization. Emphasize physically based materials, studio lighting, clean geometry, and depth.
- `pixel-art`: Pixel art. Emphasize low-resolution pixel grid, limited palette, crisp silhouettes, and retro game readability.

## Prompt Optimization Behavior

- The optimizer should return exactly 3 options.
- Each option should include a short Chinese title, a special note explaining what differentiates it, and the optimized prompt text.
- The optimized prompt should be usable directly in image generation.
- The request should include the selected style template and optional reference-image/edit context so the optimizer can preserve user intent.
- The optimizer model should be selectable from text-capable non-image-output models.
- Thinking control should be passed through when the selected optimizer model supports it; the UI should disable or normalize it when unsupported.

## Repo Fit

- The static frontend already has image generation state, image model selection, custom select controls, and thinking controls in the chat sidebar.
- The backend already has `/v1/chat/completions`, model capability metadata, thinking normalization, and JSON response-format support.
- A dedicated image prompt optimization endpoint keeps the image page simple and testable while reusing `handle_chat` internally.