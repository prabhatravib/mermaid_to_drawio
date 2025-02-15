import gradio as gr
import base64
import tempfile
import os
import xml.etree.ElementTree as ET
import zlib
import re
from collections import defaultdict, deque
import requests

def parse_mermaid(mermaid_code):
    """
    Parse simple flowchart lines from Mermaid code:
      graph TD
      A --> B
      B -- label --> C
    Returns:
      nodes: set of node_ids (strings)
      edges: list of (source_id, target_id, edge_label)
      direction: "TD" or "LR"
    """
    nodes = set()
    edges = []
    direction = "TD"  # default top-down

    lines = mermaid_code.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 1) Check if line starts with 'graph' to get direction
        if line.startswith("graph "):
            # e.g. "graph TD" or "graph LR"
            parts = line.split()
            if len(parts) >= 2:
                direction = parts[1].upper()

        # 2) Check for edges: anything with '-->'
        elif '-->' in line:
            # Example lines:
            #   A --> B
            #   A -- label --> B
            # We'll do a simple split on '-->'
            left, right = line.split('-->', 1)
            left = left.strip()
            right = right.strip()

            # If there's a '--' in the left part, it's "node -- label"
            # e.g. "A -- label"
            # Otherwise it's just "A"
            if '--' in left:
                left_node_part, edge_label = left.split('--', 1)
                left_node_part = left_node_part.strip()
                edge_label = edge_label.strip()
            else:
                left_node_part = left
                edge_label = ""

            # The source node ID will be everything in left_node_part.
            # The target node ID is everything in right.
            source_id = left_node_part
            target_id = right

            # Add them to the set of nodes
            nodes.add(source_id)
            nodes.add(target_id)

            # Add the edge
            edges.append((source_id, target_id, edge_label))

        else:
            # Possibly a standalone node definition line, e.g. "A" or "A[Something]"
            # We'll just treat it as a node. For the ID, we can use the entire line.
            nodes.add(line)

    return nodes, edges, direction


def compute_layout(nodes, edges, direction="TD"):
    """
    Very basic BFS layering approach to place nodes either top-down (TD) or left-right (LR).
    Returns a dict: {node_id: (x, y)}
    """
    if not nodes:
        return {}

    # Build adjacency + in-degree
    adj = defaultdict(list)
    indeg = {nid: 0 for nid in nodes}
    for (s, t, lbl) in edges:
        adj[s].append(t)
        indeg[t] += 1

    # queue of nodes with indegree=0
    from collections import deque
    queue = deque(n for n in indeg if indeg[n] == 0)
    depth = {n: 0 for n in nodes}  # BFS layer
    coords = {}

    while queue:
        current = queue.popleft()
        for child in adj[current]:
            indeg[child] -= 1
            if indeg[child] == 0:
                depth[child] = depth[current] + 1
                queue.append(child)

    # Sort nodes by (depth, alphabetical) for stable layout
    sorted_nodes = sorted(nodes, key=lambda x: (depth[x], x))

    # Track how many we've placed in each layer
    layer_counts = defaultdict(int)

    for n in sorted_nodes:
        d = depth[n]
        offset_in_layer = layer_counts[d]
        layer_counts[d] += 1

        if direction == "LR":
            # x ~ depth, y ~ offset
            x = d * 200
            y = offset_in_layer * 120
        else:
            # default: TD => y ~ depth, x ~ offset
            y = d * 200
            x = offset_in_layer * 200

        coords[n] = (x, y)

    return coords


def mermaid_to_drawio(mermaid_code):
    """
    Convert Mermaid code to draw.io XML (compressed+base64).
    All nodes use the same style. 
    """
    # 1) Parse
    nodes, edges, direction = parse_mermaid(mermaid_code)
    # 2) Layout
    coords = compute_layout(nodes, edges, direction)

    # 3) Build XML
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram")
    mxGraphModel = ET.SubElement(diagram, "mxGraphModel")
    root = ET.SubElement(mxGraphModel, "root")

    # Default layer
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    # Add node cells
    node_id_map = {}
    cell_counter = 2

    for node_str in nodes:
        cell_id = str(cell_counter)
        cell_counter += 1
        node_id_map[node_str] = cell_id

        # We'll just use the node string as the label
        label = node_str

        style = "rounded=1;whiteSpace=wrap;html=1;"  # All nodes same style
        mxCell = ET.SubElement(root, "mxCell", {
            "id": cell_id,
            "value": label,
            "style": style,
            "parent": "1",
            "vertex": "1"
        })

        x, y = coords.get(node_str, (0, 0))  # default (0,0) if missing
        ET.SubElement(mxCell, "mxGeometry", {
            "as": "geometry",
            "x": str(x),
            "y": str(y),
            "width": "120",
            "height": "60"
        })

    # Add edges
    for (s, t, lbl) in edges:
        edge_id = str(cell_counter)
        cell_counter += 1
        source_cell = node_id_map[s]
        target_cell = node_id_map[t]

        edge_style = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
        edge_cell = ET.SubElement(root, "mxCell", {
            "id": edge_id,
            "value": lbl,
            "style": edge_style,
            "parent": "1",
            "source": source_cell,
            "target": target_cell,
            "edge": "1"
        })
        ET.SubElement(edge_cell, "mxGeometry", {
            "as": "geometry",
            "relative": "1"
        })

    # 4) Convert XML to string and compress
    xml_string = ET.tostring(mxfile, encoding="utf-8", method="xml").decode()
    compressed_xml = zlib.compress(xml_string.encode('utf-8'), level=-1, wbits=-15)
    encoded_xml = base64.b64encode(compressed_xml).decode('utf-8')
    return encoded_xml


def render_mermaid_and_drawio(mermaid_code):
    """
    1) Render Mermaid code in an iframe locally.
    2) Provide a .mmd file download.
    3) Generate a draw.io link using the simpler parser.
    """

    # Load mermaid.min.js for local rendering

    mermaid_js_path=('https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.2.4/mermaid.min.js')
    try:
        with open("mermaid.min.js", "rb") as f:
            mermaid_js_raw = f.read()
    except:
        response = requests.get(mermaid_js_path, stream=True)  # stream=True for large files
    
        mermaid_js_raw = response.content  # Use response.content for binary data    
    
    mermaid_js_b64 = base64.b64encode(mermaid_js_raw).decode("utf-8")

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="data:application/javascript;base64,{mermaid_js_b64}"></script>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                mermaid.initialize({{ startOnLoad: true }});
                mermaid.init(undefined, document.querySelectorAll('.mermaid'));
            }});
        </script>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                text-align: center;
                font-family: sans-serif;
            }}
            .mermaid {{
                display: inline-block;
                max-width: 100%;
                font-size: 1.2rem;
            }}
        </style>
    </head>
    <body>
        <div class="mermaid">
            {mermaid_code}
        </div>
    </body>
    </html>
    """

    # For the iframe srcdoc, we must escape quotes
    safe_html = html_template.replace('"', "&quot;").replace("'", "&#x27;")
    iframe_html = f'<iframe srcdoc="{safe_html}" width="100%" height="500px" frameborder="0"></iframe>'

    # Create a temporary .mmd file for download
    with tempfile.NamedTemporaryFile(suffix=".mmd", delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(mermaid_code)
        tmp_path = tmp.name

    # Generate draw.io link
    drawio_xml_base64 = mermaid_to_drawio(mermaid_code)
    drawio_url = f"https://app.diagrams.net/?splash=0&clibs=U&lang=en#R{drawio_xml_base64}"
    drawio_link = f"<a href='{drawio_url}' target='_blank'>Open in Draw.io</a>"

    return iframe_html, tmp_path, drawio_link


iface = gr.Interface(
    fn=render_mermaid_and_drawio,
    inputs=gr.Textbox(
        lines=5,
        placeholder="Enter Mermaid code here...",
        label="Mermaid Code"
    ),
    outputs=[
            gr.HTML(
                label="Mermaid Diagram",
                value="<div style='color:grey'>Mermaid flowchart:</div>"
            ),
            gr.File(label="Mermaid .mmd file"),
            gr.HTML(
                label="Draw.io Link",
                value="<div style='color:grey'>Draw.io link :</div>"
            )
        ],
        
    title="Mermaid to Draw.io (All Same Shape, Simple Parser)",
    description=(
        "Enter Mermaid flowchart code like:\n\n"
        "```mermaid\n"
        "graph TD\n"
        "    A --> B\n"
        "    B -- yes --> C\n"
        "```\n\n"
        "We'll parse it, render it in an iframe, and give you a link for draw.io.\n"
        "If you see an empty diagram, your Mermaid lines might not match the simple parser. "
    )
)

iface.launch(share=True)
