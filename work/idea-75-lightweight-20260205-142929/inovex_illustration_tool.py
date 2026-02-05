"""
inovex Illustration Generator Tool for nano-banana MCP Server

This module extends the nano-banana MCP server with a specialized tool
for generating inovex corporate brand-aligned illustrations.

Installation:
1. Copy inovex_styles.py and this file to ~/.claude/mcp-servers/nano-banana-mcp/
2. Import and register in server.py (see integration instructions below)

Integration in server.py:
    # Add at top of file:
    from inovex_illustration_tool import create_inovex_tool, list_inovex_styles_tool

    # Add after mcp = FastMCP(...):
    create_inovex_tool(mcp, lambda: _nano_banana)
    list_inovex_styles_tool(mcp)
"""

from typing import Any, Optional, Callable
from inovex_styles import (
    IllustrationCategory,
    build_inovex_prompt,
    list_styles,
    INOVEX_COLORS,
)


def create_inovex_tool(mcp, get_server: Callable):
    """
    Register the generate_inovex_illustration tool with the MCP server.

    Args:
        mcp: The FastMCP server instance
        get_server: Callable that returns the NanoBananaServer instance
    """

    @mcp.tool()
    def generate_inovex_illustration(
        subject: str,
        category: str = "concept",
        additional_style: Optional[str] = None,
        color_variant: str = "default",
        resolution: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Generate an inovex corporate brand-aligned illustration.

        Uses the inovex corporate color palette and style guidelines to create
        professional illustrations suitable for presentations, documentation,
        and marketing materials.

        CATEGORY GUIDE:
        ---------------
        hero     - Large banner/hero images for websites and slides (2048x2048)
        icon     - Simple iconic illustrations for UI and docs (1024x1024)
        diagram  - Technical diagram backgrounds and decorations
        abstract - Abstract geometric backgrounds for slides
        isometric - Isometric 3D style for tech concepts
        concept  - Conceptual illustrations for ideas (default)
        data     - Data visualization decorative elements
        person   - Stylized person illustrations

        COLOR VARIANTS:
        ---------------
        default      - Standard inovex blue/navy palette
        light        - Light/white background variant
        dark         - Deep navy background
        green-accent - Extra emphasis on mint green accents

        INOVEX BRAND COLORS:
        --------------------
        Blue:  #2C5DFF (primary)
        Green: #7DF381 (accent)
        Navy:  #061B59 (dark)
        Cyan:  #0AAFE8 (highlight)
        Teal:  #41E8E0 (secondary)

        Args:
            subject: What to illustrate (e.g., "Cloud computing", "AI brain")
            category: Style category (hero, icon, diagram, abstract, isometric, concept, data, person)
            additional_style: Extra style guidance to append
            color_variant: Color scheme variant (default, light, dark, green-accent)
            resolution: Override resolution (e.g., "1024x1024", "2048x2048")
            model: Override model (e.g., "gemini-2.5-flash-image", "flux-1.1-pro")

        Returns:
            Dict with image_url, cost_cents, style info, and remaining budget.

        Example:
            generate_inovex_illustration(
                subject="Machine learning neural network",
                category="isometric",
                color_variant="dark"
            )
        """
        server = get_server()
        if server is None:
            return {"error": "Server not initialized"}

        try:
            # Parse category
            try:
                cat = IllustrationCategory(category.lower())
            except ValueError:
                return {
                    "error": f"Invalid category: {category}",
                    "valid_categories": [c.value for c in IllustrationCategory],
                }

            # Build the inovex-styled prompt
            prompt_config = build_inovex_prompt(
                subject=subject,
                category=cat,
                additional_style=additional_style,
                color_variant=color_variant,
            )

            # Use provided overrides or style recommendations
            final_resolution = resolution or prompt_config["resolution"]
            final_model = model or prompt_config["model"]

            # Generate using the nano-banana server
            result = server.generate(
                prompt=prompt_config["prompt"],
                resolution=final_resolution,
                negative_prompt=prompt_config["negative_prompt"],
                model=final_model,
            )

            # Add style metadata to result
            result["inovex_style"] = {
                "category": category,
                "style_name": prompt_config["style_name"],
                "color_variant": color_variant,
                "brand_colors": INOVEX_COLORS,
            }

            return result

        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    return generate_inovex_illustration


def list_inovex_styles_tool(mcp):
    """
    Register the list_inovex_styles tool with the MCP server.

    Args:
        mcp: The FastMCP server instance
    """

    @mcp.tool()
    def list_inovex_styles() -> dict[str, Any]:
        """
        List all available inovex illustration styles with descriptions.

        Returns comprehensive information about each style category including:
        - Category name and description
        - Recommended resolution and model
        - Use case guidance

        INOVEX BRAND COLORS (for reference):
        ------------------------------------
        Blue:  #2C5DFF (primary corporate blue)
        Green: #7DF381 (bright mint green accent)
        Navy:  #061B59 (dark background)
        Cyan:  #0AAFE8 (bright highlight)
        Teal:  #41E8E0 (secondary accent)

        Returns:
            Dict with styles list and brand color reference.
        """
        return {
            "styles": list_styles(),
            "color_variants": [
                {"name": "default", "description": "Standard inovex blue/navy palette"},
                {"name": "light", "description": "Light/white background variant"},
                {"name": "dark", "description": "Deep navy (#061B59) background"},
                {"name": "green-accent", "description": "Extra emphasis on mint green accents"},
            ],
            "brand_colors": INOVEX_COLORS,
            "usage_examples": [
                {
                    "description": "Hero image for AI presentation",
                    "call": 'generate_inovex_illustration(subject="Artificial intelligence brain with neural connections", category="hero", color_variant="dark")',
                },
                {
                    "description": "Icon for cloud service",
                    "call": 'generate_inovex_illustration(subject="Cloud computing", category="icon", color_variant="light")',
                },
                {
                    "description": "Background for data dashboard",
                    "call": 'generate_inovex_illustration(subject="Data analytics flow", category="abstract", color_variant="dark")',
                },
            ],
        }

    return list_inovex_styles


# Standalone testing
if __name__ == "__main__":
    import json

    # Test prompt building
    from inovex_styles import build_inovex_prompt, IllustrationCategory

    print("Testing inovex prompt generation:")
    print("=" * 60)

    test_cases = [
        ("Machine learning", IllustrationCategory.ISOMETRIC, "dark"),
        ("Cloud infrastructure", IllustrationCategory.HERO, "default"),
        ("Data integration", IllustrationCategory.ICON, "light"),
        ("Analytics dashboard", IllustrationCategory.DATA, "dark"),
    ]

    for subject, category, variant in test_cases:
        result = build_inovex_prompt(subject, category, color_variant=variant)
        print(f"\nSubject: {subject}")
        print(f"Category: {category.value}, Variant: {variant}")
        print(f"Model: {result['model']}, Resolution: {result['resolution']}")
        print(f"Prompt preview: {result['prompt'][:100]}...")
