# Mermaid to Draw.io Converter

A simple process that converts Mermaid flowchart diagram code to Draw.io flwochart diagrams. Built with Gradio, this tool provides an easy way to visualize and render your Mermaid diagrams.

## Features

- Live preview of Mermaid diagrams
- Conversion to Draw.io format with preserved layout
- Download diagrams as .mmd files
- Simple and intuitive web interface
- Support for both Top-Down (TD) and Left-Right (LR) flowchart directions

## Supported Mermaid Syntax

The parser currently supports basic flowchart syntax:
- Graph declarations (`graph TD` or `graph LR`)
- Simple node definitions
- Edge connections with and without labels (`A --> B` or `A -- label --> B`)

## Technical Details

The converter uses:
- BFS-based layout algorithm for node positioning
- Consistent node styling in Draw.io output
- XML-based conversion for Draw.io compatibility
- Base64 encoding for Draw.io URL generation

## Usage

1. Enter your Mermaid flowchart code in the text area
2. View the live preview in the embedded iframe
3. Download the .mmd file if needed
4. Click the Draw.io link to open your diagram in Draw.io

Example input:
```
graph TD
    A --> B
    B -- yes --> C
```

## Limitations

- Uses a simplified Mermaid parser
- All nodes use the same shape/style in Draw.io
- Basic layout algorithm that may not handle complex diagrams optimally

## Dependencies

- gradio
- base64
- xml.etree.ElementTree
- zlib
- mermaid.min.js (included)

## Contributing

Feel free to contribute by:
- Adding support for more Mermaid syntax features
- Improving the layout algorithm
- Enhancing Draw.io style conversion
- Adding new export formats
