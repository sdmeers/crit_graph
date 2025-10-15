#!/usr/bin/env python3
"""
Convert JSON network graph format to GML file for Critical Role episodes
"""

import json
import os
import argparse


def escape_gml_string(s):
    """Escape special characters in GML strings"""
    if s is None:
        return ""
    # Replace quotes and backslashes
    s = str(s).replace('\\', '\\\\').replace('"', '\\"')
    # Replace newlines
    s = s.replace('\n', ' ').replace('\r', ' ')
    return s


def json_to_gml(json_filename, gml_filename=None):
    """Convert JSON network graph to GML format"""
    
    # Read JSON file
    with open(json_filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Generate output filename if not provided
    if gml_filename is None:
        base = os.path.splitext(json_filename)[0]
        gml_filename = f"{base}.gml"
    
    # Create output directory if needed
    output_dir = os.path.dirname(gml_filename)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Extract episode info
    episode = data.get('episode', {})
    ep_num = episode.get('number', 'Unknown')
    ep_title = episode.get('title', 'Unknown')
    campaign = episode.get('campaign', 'Unknown')
    
    # Create node ID mapping (string IDs to numeric IDs)
    nodes = data.get('nodes', [])
    node_id_map = {}
    for idx, node in enumerate(nodes, start=1):
        node_id_map[node['id']] = idx
    
    # Write GML file
    with open(gml_filename, 'w', encoding='utf-8') as f:
        # Header
        f.write(f'Creator "Critical Role {campaign} Episode {ep_num} Network Extractor"\n')
        f.write('graph [\n')
        f.write('  directed 1\n')
        f.write(f'  comment "Critical Role {campaign} Episode {ep_num}: {ep_title}"\n')
        f.write('\n')
        
        # Write nodes
        for idx, node in enumerate(nodes, start=1):
            f.write(f'  node [\n')
            f.write(f'    id {idx}\n')
            
            # Write label
            label = escape_gml_string(node.get('label', node.get('id', '')))
            f.write(f'    label "{label}"\n')
            
            # Write type
            node_type = escape_gml_string(node.get('type', 'unknown'))
            f.write(f'    type "{node_type}"\n')
            
            # Write all other attributes
            for key, value in node.items():
                if key not in ['id', 'label', 'type']:
                    escaped_value = escape_gml_string(value)
                    f.write(f'    {key} "{escaped_value}"\n')
            
            f.write(f'  ]\n')
        
        f.write('\n')
        
        # Write edges
        edges = data.get('edges', [])
        for edge in edges:
            source_id = node_id_map.get(edge['source'])
            target_id = node_id_map.get(edge['target'])
            
            if source_id is None or target_id is None:
                print(f"Warning: Skipping edge with invalid node reference: {edge['source']} -> {edge['target']}")
                continue
            
            f.write(f'  edge [\n')
            f.write(f'    source {source_id}\n')
            f.write(f'    target {target_id}\n')
            
            # Write relationship as label
            relationship = escape_gml_string(edge.get('relationship', edge.get('label', '')))
            f.write(f'    label "{relationship}"\n')
            
            # Write weight if present
            if 'weight' in edge:
                f.write(f'    weight {edge["weight"]}\n')
            
            # Write any other edge attributes
            for key, value in edge.items():
                if key not in ['source', 'target', 'relationship', 'label', 'weight']:
                    escaped_value = escape_gml_string(value)
                    f.write(f'    {key} "{escaped_value}"\n')
            
            f.write(f'  ]\n')
        
        # Close graph
        f.write(']\n')
    
    print(f"GML file '{gml_filename}' created successfully!")
    print(f"Episode: {campaign} Episode {ep_num} - {ep_title}")
    print(f"Nodes: {len(nodes)}")
    print(f"Edges: {len(edges)}")
    
    return gml_filename


def main():
    parser = argparse.ArgumentParser(
        description='Convert JSON network graph to GML format for Critical Role episodes'
    )
    parser.add_argument(
        'input_file',
        help='Input JSON file (e.g., episode_2_graph.txt or .json)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output GML file (default: same name as input with .gml extension)',
        default=None
    )
    
    args = parser.parse_args()
    
    json_to_gml(args.input_file, args.output)


if __name__ == "__main__":
    main()