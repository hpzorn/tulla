# inovex Illustration Generator for nano-banana MCP

Extension for the nano-banana MCP server that adds inovex corporate brand-aligned illustration generation.

## Features

- **Brand-aligned prompts**: Automatically applies inovex corporate colors and style guidelines
- **8 illustration categories**: hero, icon, diagram, abstract, isometric, concept, data, person
- **4 color variants**: default, light, dark, green-accent
- **Smart defaults**: Each category has optimized resolution and model recommendations

## Installation

1. Copy the module files to nano-banana:
   ```bash
   cp inovex_styles.py ~/.claude/mcp-servers/nano-banana-mcp/
   cp inovex_illustration_tool.py ~/.claude/mcp-servers/nano-banana-mcp/
   ```

2. Edit `~/.claude/mcp-servers/nano-banana-mcp/server.py`:

   Add imports at top:
   ```python
   from inovex_illustration_tool import create_inovex_tool, list_inovex_styles_tool
   ```

   Add after `mcp = FastMCP(...)` line (around line 366):
   ```python
   # Register inovex illustration tools
   create_inovex_tool(mcp, lambda: _nano_banana)
   list_inovex_styles_tool(mcp)
   ```

3. Restart Claude Code or the MCP server.

## Usage

### List available styles
```
list_inovex_styles()
```

### Generate illustrations
```
generate_inovex_illustration(
    subject="Machine learning neural network",
    category="isometric",
    color_variant="dark"
)
```

## Categories

| Category | Description | Default Resolution | Default Model |
|----------|-------------|-------------------|---------------|
| hero | Large banner/hero images | 2048x2048 | flux-1.1-pro |
| icon | Simple iconic illustrations | 1024x1024 | gemini-2.5-flash-image |
| diagram | Technical diagram backgrounds | 1536x1536 | gemini-2.5-flash-image |
| abstract | Abstract geometric backgrounds | 2048x2048 | flux-1.1-pro |
| isometric | Isometric 3D style | 1536x1536 | flux-1.1-pro |
| concept | Conceptual illustrations | 1536x1536 | flux-1.1-pro |
| data | Data visualization decorations | 1536x1536 | gemini-2.5-flash-image |
| person | Stylized person illustrations | 1024x1024 | flux-1.1-pro |

## Color Variants

| Variant | Description |
|---------|-------------|
| default | Standard inovex blue/navy palette |
| light | White/light gray background |
| dark | Deep navy (#061B59) background |
| green-accent | Emphasis on mint green (#7DF381) accents |

## inovex Brand Colors

- **Blue**: #2C5DFF (primary)
- **Green**: #7DF381 (accent)
- **Navy**: #061B59 (dark background)
- **Cyan**: #0AAFE8 (highlight)
- **Teal**: #41E8E0 (secondary accent)

## Examples

### Hero image for AI presentation
```python
generate_inovex_illustration(
    subject="Artificial intelligence brain with neural connections",
    category="hero",
    color_variant="dark"
)
```

### Icon for cloud service
```python
generate_inovex_illustration(
    subject="Cloud computing",
    category="icon",
    color_variant="light"
)
```

### Background for data dashboard
```python
generate_inovex_illustration(
    subject="Data analytics flow",
    category="abstract",
    color_variant="dark"
)
```
