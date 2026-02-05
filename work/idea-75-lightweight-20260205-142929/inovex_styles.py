"""
inovex Illustration Style Templates for Gemini Imagen

Provides inovex corporate brand-aligned prompt templates and style guidance
for generating professional illustrations using the nano-banana MCP server.

Brand Colors (from inovex corporate identity):
  - inovex-blue: #2C5DFF (primary)
  - inovex-green: #7DF381 (accent)
  - inovex-navy: #061B59 (dark background)
  - inovex-cyan: #0AAFE8 (highlight)
  - inovex-teal: #41E8E0 (secondary accent)
  - inovex-white: #FFFFFF
  - inovex-light-gray: #F5F5F5
  - inovex-dark-gray: #333333
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class IllustrationCategory(str, Enum):
    """Categories of illustrations with optimized prompts."""
    HERO = "hero"           # Large banner/hero images
    ICON = "icon"           # Simple iconic illustrations
    DIAGRAM = "diagram"     # Technical diagrams
    ABSTRACT = "abstract"   # Abstract geometric backgrounds
    ISOMETRIC = "isometric" # Isometric 3D style
    CONCEPT = "concept"     # Conceptual illustrations
    DATA = "data"           # Data visualization decorations
    PERSON = "person"       # Stylized person illustrations


@dataclass
class InovexStyle:
    """Style configuration for inovex illustrations."""
    name: str
    description: str
    style_prompt: str
    negative_prompt: str
    recommended_resolution: str = "1024x1024"
    recommended_model: str = "gemini-2.5-flash-image"


# inovex brand color palette for prompt engineering
INOVEX_COLORS = {
    "blue": "#2C5DFF",
    "green": "#7DF381",
    "navy": "#061B59",
    "cyan": "#0AAFE8",
    "teal": "#41E8E0",
    "white": "#FFFFFF",
    "light_gray": "#F5F5F5",
    "dark_gray": "#333333",
}

# Color palette description for prompts
INOVEX_COLOR_PROMPT = (
    "corporate color palette of vibrant electric blue (#2C5DFF), "
    "bright mint green (#7DF381), deep navy (#061B59), "
    "cyan highlights (#0AAFE8), and teal accents (#41E8E0)"
)


# Pre-defined illustration styles
ILLUSTRATION_STYLES = {
    IllustrationCategory.HERO: InovexStyle(
        name="Hero Banner",
        description="Large banner images for presentations, websites, and marketing materials",
        style_prompt=(
            f"Modern corporate illustration style, clean geometric shapes, "
            f"{INOVEX_COLOR_PROMPT}, "
            f"gradient backgrounds from navy to blue, subtle tech patterns, "
            f"professional business aesthetic, minimalist design, "
            f"high contrast, vector-like quality, no text"
        ),
        negative_prompt=(
            "text, watermark, logo, busy background, photorealistic, "
            "cluttered, low quality, blurry, amateur, generic stock photo"
        ),
        recommended_resolution="2048x2048",
        recommended_model="flux-1.1-pro",
    ),

    IllustrationCategory.ICON: InovexStyle(
        name="Icon",
        description="Simple iconic illustrations for UI, slides, and documentation",
        style_prompt=(
            f"Minimalist icon style, flat design, single concept visualization, "
            f"{INOVEX_COLOR_PROMPT}, "
            f"clean lines, geometric simplicity, professional tech aesthetic, "
            f"white or transparent background, centered composition"
        ),
        negative_prompt=(
            "text, watermark, complex details, photorealistic, 3D realistic, "
            "gradients, shadows, multiple objects, busy, cluttered"
        ),
        recommended_resolution="1024x1024",
        recommended_model="gemini-2.5-flash-image",
    ),

    IllustrationCategory.DIAGRAM: InovexStyle(
        name="Technical Diagram",
        description="Technical diagram backgrounds and decorative elements",
        style_prompt=(
            f"Technical diagram style, blueprint aesthetic, "
            f"{INOVEX_COLOR_PROMPT}, "
            f"circuit board patterns, network nodes and connections, "
            f"clean grid layout, professional engineering look, "
            f"subtle tech elements, dark background with bright accents"
        ),
        negative_prompt=(
            "text, labels, numbers, photorealistic, organic shapes, "
            "people, faces, cluttered, low quality"
        ),
        recommended_resolution="1536x1536",
        recommended_model="gemini-2.5-flash-image",
    ),

    IllustrationCategory.ABSTRACT: InovexStyle(
        name="Abstract Background",
        description="Abstract geometric backgrounds for slides and banners",
        style_prompt=(
            f"Abstract geometric background, flowing gradient shapes, "
            f"{INOVEX_COLOR_PROMPT}, "
            f"smooth color transitions from navy to blue to cyan, "
            f"subtle mesh gradient, corporate modern aesthetic, "
            f"diagonal composition, professional and elegant"
        ),
        negative_prompt=(
            "text, watermark, objects, people, photorealistic, "
            "sharp edges only, noisy texture, low quality, busy patterns"
        ),
        recommended_resolution="2048x2048",
        recommended_model="flux-1.1-pro",
    ),

    IllustrationCategory.ISOMETRIC: InovexStyle(
        name="Isometric",
        description="Isometric 3D style illustrations for tech concepts",
        style_prompt=(
            f"Isometric 3D illustration, clean geometric blocks, "
            f"{INOVEX_COLOR_PROMPT}, "
            f"tech/data center theme, servers, clouds, networks, "
            f"soft shadows, professional corporate style, "
            f"minimalist composition, high quality render look"
        ),
        negative_prompt=(
            "text, labels, photorealistic, messy, low quality, "
            "people faces, cluttered, wrong perspective, 2D flat"
        ),
        recommended_resolution="1536x1536",
        recommended_model="flux-1.1-pro",
    ),

    IllustrationCategory.CONCEPT: InovexStyle(
        name="Concept",
        description="Conceptual illustrations for ideas and processes",
        style_prompt=(
            f"Conceptual illustration, symbolic representation, "
            f"{INOVEX_COLOR_PROMPT}, "
            f"modern corporate art style, metaphorical imagery, "
            f"clean composition, professional business aesthetic, "
            f"thought-provoking visual, innovation theme"
        ),
        negative_prompt=(
            "text, watermark, photorealistic, cluttered, "
            "amateur, generic, low quality, cartoon, childish"
        ),
        recommended_resolution="1536x1536",
        recommended_model="flux-1.1-pro",
    ),

    IllustrationCategory.DATA: InovexStyle(
        name="Data Visualization",
        description="Decorative elements for data visualizations and dashboards",
        style_prompt=(
            f"Data visualization aesthetic, abstract chart elements, "
            f"{INOVEX_COLOR_PROMPT}, "
            f"glowing data points, flowing lines, modern dashboard style, "
            f"dark background with bright data accents, futuristic analytics look"
        ),
        negative_prompt=(
            "actual numbers, readable text, specific data values, "
            "photorealistic, people, faces, low quality, cluttered"
        ),
        recommended_resolution="1536x1536",
        recommended_model="gemini-2.5-flash-image",
    ),

    IllustrationCategory.PERSON: InovexStyle(
        name="Stylized Person",
        description="Stylized illustrations of people for presentations",
        style_prompt=(
            f"Stylized person illustration, modern corporate art style, "
            f"{INOVEX_COLOR_PROMPT}, "
            f"professional business person, simplified features, "
            f"geometric/vector style, diverse representation, "
            f"clean background, friendly professional appearance"
        ),
        negative_prompt=(
            "photorealistic, creepy, distorted features, uncanny valley, "
            "low quality, amateur, cartoonish, childish, inappropriate"
        ),
        recommended_resolution="1024x1024",
        recommended_model="flux-1.1-pro",
    ),
}


def get_style(category: IllustrationCategory) -> InovexStyle:
    """Get the style configuration for a category."""
    return ILLUSTRATION_STYLES.get(category, ILLUSTRATION_STYLES[IllustrationCategory.CONCEPT])


def build_inovex_prompt(
    subject: str,
    category: IllustrationCategory = IllustrationCategory.CONCEPT,
    additional_style: Optional[str] = None,
    color_variant: str = "default",
) -> dict:
    """
    Build a complete prompt for inovex-style illustration generation.

    Args:
        subject: The subject/concept to illustrate
        category: The illustration category/style
        additional_style: Optional additional style guidance
        color_variant: Color variant ("default", "light", "dark", "green-accent")

    Returns:
        Dict with prompt, negative_prompt, resolution, model recommendation
    """
    style = get_style(category)

    # Build the main prompt
    prompt_parts = [subject]
    prompt_parts.append(style.style_prompt)

    if additional_style:
        prompt_parts.append(additional_style)

    # Apply color variant
    if color_variant == "light":
        prompt_parts.append("on white or light gray background")
    elif color_variant == "dark":
        prompt_parts.append("on deep navy background (#061B59)")
    elif color_variant == "green-accent":
        prompt_parts.append("with prominent mint green (#7DF381) accents")

    return {
        "prompt": ". ".join(prompt_parts),
        "negative_prompt": style.negative_prompt,
        "resolution": style.recommended_resolution,
        "model": style.recommended_model,
        "style_name": style.name,
        "style_description": style.description,
    }


def list_styles() -> List[dict]:
    """List all available inovex illustration styles."""
    return [
        {
            "category": cat.value,
            "name": style.name,
            "description": style.description,
            "recommended_resolution": style.recommended_resolution,
            "recommended_model": style.recommended_model,
        }
        for cat, style in ILLUSTRATION_STYLES.items()
    ]


# Example usage and testing
if __name__ == "__main__":
    import json

    print("inovex Illustration Styles")
    print("=" * 50)

    for style_info in list_styles():
        print(f"\n{style_info['name']} ({style_info['category']})")
        print(f"  {style_info['description']}")
        print(f"  Resolution: {style_info['recommended_resolution']}")
        print(f"  Model: {style_info['recommended_model']}")

    print("\n" + "=" * 50)
    print("Example prompt generation:")
    print("=" * 50)

    example = build_inovex_prompt(
        subject="Cloud computing and data integration",
        category=IllustrationCategory.ISOMETRIC,
        color_variant="dark"
    )
    print(json.dumps(example, indent=2))
