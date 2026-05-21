# gpt-image-2 Size Options

## Source

OpenAI developer cookbook: GPT Image Generation Models Prompting Guide, section `gpt-image-2 size options` and `Popular gpt-image-2 sizes`.

## Constraints

`gpt-image-2` accepts any `size` value when all constraints are met:

- Maximum edge length is less than `3840px`.
- Both edges are multiples of `16`.
- Long-edge to short-edge ratio is no greater than `3:1`.
- Total pixels do not exceed `8,294,400`.
- Total pixels are not less than `655,360`.

Outputs above `2560x1440` (`3,686,400` pixels) should be treated as experimental because results can vary more at that size.

## UI Choices

Expose common sizes that satisfy the constraints:

- `1024x1024` square default.
- `1024x1536` HD portrait.
- `1536x1024` HD landscape.
- `1536x864` 16:9 HD landscape.
- `2560x1440` 2K/QHD reliability boundary.
- `3824x2144` near-4K/UHD option, rounded below the literal `< 3840` max-edge rule.

Do not present `3840x2160` as an enabled option because a literal implementation of the max-edge rule rejects `3840`.