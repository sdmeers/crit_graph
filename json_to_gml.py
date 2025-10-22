#!/usr/bin/env python3
"""
Convert JSON network graph format to GML file for Critical Role episodes
"""

import json
import os
import argparse
import re
import unicodedata


def remove_accents(text):
    """Remove accents from unicode string"""
    if text is None:
        return ""
    # Normalize to NFD (decomposed form)
    nfd = unicodedata.normalize('NFD', str(text))
    # Filter out combining characters (accents)
    return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')


def to_ascii_safe(s):
    """Convert string to ASCII-safe version"""
    if s is None:
        return ""
    
    s = str(s)
    
    # Remove accents first
    s = remove_accents(s)
    
    # Replace remaining non-ASCII characters with closest ASCII equivalent or remove
    s = s.encode('ascii', 'ignore').decode('ascii')
    
    return s


def escape_gml_string(s):
    """Escape special characters in GML strings and ensure ASCII"""
    if s is None:
        return ""
    
    # Convert to string and make ASCII-safe
    s = to_ascii_safe(s)
    
    # Replace backslashes first (must be done before other escapes)
    s = s.replace('\\', '\\\\')
    
    # Replace double quotes with single quotes
    s = s.replace('"', "'")
    
    # Replace newlines and carriage returns with spaces
    s = s.replace('\n', ' ').replace('\r', ' ')
    
    # Replace tabs with spaces
    s = s.replace('\t', ' ')
    
    # Replace problematic punctuation that GML parsers don't like
    s = s.replace(';', ' ')
    s = s.replace('|', ' ')
    s = s.replace('[', '(')
    s = s.replace(']', ')')
    s = s.replace('{', '(')
    s = s.replace('}', ')')
    
    # Remove any remaining control characters
    s = ''.join(char for char in s if ord(char) >= 32 or char in ' ')
    
    # Collapse multiple spaces
    s = re.sub(r'\s+', ' ', s)
    
    return s.strip()


def format_attribute_value(value):
    """
    Format attribute values for GML.
    Lists are converted to space-separated strings.
    """
    if value is None:
        return ""
    
    if isinstance(value, list):
        # Convert list to space-separated string
        # Remove any nested quotes and brackets
        cleaned = []
        for item in value:
            item_str = str(item).strip("'\"[](){}")
            if item_str:  # Only add non-empty items
                cleaned.append(item_str)
        # Join with space and then escape
        return escape_gml_string(" ".join(cleaned))
    
    if isinstance(value, dict):
        # Convert dict to key:value pairs
        pairs = []
        for k, v in value.items():
            pair_str = f"{k} {v}"
            pairs.append(pair_str)
        return escape_gml_string(" ".join(pairs))
    
    if isinstance(value, bool):
        return "true" if value else "false"
    
    if isinstance(value, (int, float)):
        return str(value)
    
    # String - escape it
    return escape_gml_string(str(value))


def sanitize_key(key):
    """Sanitize attribute key names for GML"""
    # Replace spaces and special chars with underscores
    key = re.sub(r'[^a-zA-Z0-9_]', '_', key)
    # Remove leading numbers
    key = re.sub(r'^[0-9]+', '', key)
    # Remove trailing/leading underscores
    key = key.strip('_')
    # Ensure not empty
    if not key:
        key = "attribute"
    return key


def extract_episode_info(json_data):
    """Extract episode information from various possible locations in JSON"""
    episode_info = {
        'campaign': 'Unknown Campaign',
        'number': 'Unknown',
        'title': 'Unknown Episode'
    }
    
    # Check for episode metadata
    if 'episode' in json_data:
        ep = json_data['episode']
        episode_info['campaign'] = ep.get('campaign', episode_info['campaign'])
        episode_info['number'] = ep.get('number', episode_info['number'])
        episode_info['title'] = ep.get('title', episode_info['title'])
    
    # Try to extract from metadata
    if 'metadata' in json_data:
        meta = json_data['metadata']
        episode_info['campaign'] = meta.get('campaign', episode_info['campaign'])
        episode_info['number'] = meta.get('episode', episode_info['number'])
        episode_info['title'] = meta.get('title', episode_info['title'])
    
    # Try to infer from filename comment if present
    if 'comment' in json_data:
        comment = json_data['comment']
        # Try to extract episode number from comment
        match = re.search(r'Episode\s+(\d+)', comment, re.IGNORECASE)
        if match:
            episode_info['number'] = match.group(1)
    
    return episode_info


def json_to_gml(json_filename, gml_filename=None, campaign="Araman", episode_num=None):
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
    episode_info = extract_episode_info(data)
    
    # Override with command line args if provided
    if campaign:
        episode_info['campaign'] = campaign
    if episode_num:
        episode_info['number'] = episode_num
    
    # Try to infer episode from filename
    if episode_info['number'] == 'Unknown':
        match = re.search(r'episode[_\s]*(\d+)', json_filename, re.IGNORECASE)
        if match:
            episode_info['number'] = match.group(1)
    
    # Get nodes and edges
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    
    # Create node ID mapping (handle both string and numeric IDs)
    node_id_map = {}
    for idx, node in enumerate(nodes, start=1):
        original_id = node.get('id', f"node_{idx}")
        node_id_map[str(original_id)] = idx
        # Also map by label as fallback
        if 'label' in node:
            node_id_map[node['label']] = idx
    
    # Statistics
    stats = {
        'nodes_total': len(nodes),
        'nodes_by_type': {},
        'edges_total': len(edges),
        'edges_skipped': 0
    }
    
    # Count node types
    for node in nodes:
        node_type = node.get('type', 'unknown')
        stats['nodes_by_type'][node_type] = stats['nodes_by_type'].get(node_type, 0) + 1
    
    # Write GML file - ensure ASCII encoding
    with open(gml_filename, 'w', encoding='ascii', errors='replace') as f:
        # Header
        campaign_ascii = to_ascii_safe(episode_info["campaign"])
        title_ascii = to_ascii_safe(episode_info["title"])
        
        f.write(f'Creator "Critical Role {campaign_ascii} Episode {episode_info["number"]} Network Extractor"\n')
        f.write('graph [\n')
        f.write('  directed 1\n')
        f.write(f'  comment "Critical Role {campaign_ascii} Episode {episode_info["number"]}: {title_ascii}"\n')
        f.write('\n')
        
        # Write nodes
        for idx, node in enumerate(nodes, start=1):
            f.write('  node [\n')
            f.write(f'    id {idx}\n')
            
            # Write label (required)
            label = node.get('label', node.get('id', f'node_{idx}'))
            f.write(f'    label "{escape_gml_string(label)}"\n')
            
            # Write type (important for visualization)
            node_type = node.get('type', 'unknown')
            f.write(f'    type "{escape_gml_string(node_type)}"\n')
            
            # Write all other attributes
            for key, value in node.items():
                if key not in ['id', 'label', 'type']:
                    # Skip empty values
                    if value is None or value == "" or value == [] or value == {}:
                        continue
                    
                    # Sanitize key name
                    safe_key = sanitize_key(key)
                    if not safe_key or safe_key == 'attribute':
                        continue  # Skip invalid keys
                    
                    formatted_value = format_attribute_value(value)
                    if formatted_value and len(formatted_value) > 0:  # Only write non-empty values
                        f.write(f'    {safe_key} "{formatted_value}"\n')
            
            f.write('  ]\n')
        
        # Write edges
        for edge in edges:
            source = str(edge.get('source', ''))
            target = str(edge.get('target', ''))
            
            source_id = node_id_map.get(source)
            target_id = node_id_map.get(target)
            
            if source_id is None or target_id is None:
                print(f"Warning: Skipping edge with invalid node reference: {source} -> {target}")
                stats['edges_skipped'] += 1
                continue
            
            f.write('  edge [\n')
            f.write(f'    source {source_id}\n')
            f.write(f'    target {target_id}\n')
            
            # Write relationship as label
            relationship = edge.get('relationship', edge.get('label', 'related'))
            f.write(f'    label "{escape_gml_string(relationship)}"\n')
            
            # Write weight if present
            if 'weight' in edge:
                try:
                    weight = float(edge['weight'])
                    f.write(f'    weight {weight}\n')
                except (ValueError, TypeError):
                    pass
            
            # Write description if present
            if 'description' in edge:
                desc = edge['description']
                if desc:
                    f.write(f'    description "{escape_gml_string(desc)}"\n')
            
            # Write any other edge attributes
            for key, value in edge.items():
                if key not in ['source', 'target', 'relationship', 'label', 'weight', 'description']:
                    if value is not None and value != "" and value != [] and value != {}:
                        # Sanitize key name
                        safe_key = sanitize_key(key)
                        if not safe_key or safe_key == 'attribute':
                            continue
                        
                        formatted_value = format_attribute_value(value)
                        if formatted_value and len(formatted_value) > 0:
                            f.write(f'    {safe_key} "{formatted_value}"\n')
            
            f.write('  ]\n')
        
        # Close graph
        f.write(']\n')
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"GML file created successfully!")
    print(f"{'='*60}")
    print(f"Output: {gml_filename}")
    print(f"Episode: {episode_info['campaign']} Episode {episode_info['number']} - {episode_info['title']}")
    print(f"\nNodes: {stats['nodes_total']}")
    for node_type, count in sorted(stats['nodes_by_type'].items()):
        print(f"  - {node_type}: {count}")
    print(f"\nEdges: {stats['edges_total']}")
    if stats['edges_skipped'] > 0:
        print(f"  - Skipped (invalid references): {stats['edges_skipped']}")
    print(f"{'='*60}\n")
    
    return gml_filename


def main():
    parser = argparse.ArgumentParser(
        description='Convert JSON network graph to GML format for Critical Role episodes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s episode_3_graph.json
  %(prog)s episode_3_graph.json -o output/ep3.gml
  %(prog)s episode_3_graph.json -c "Araman" -e 3
        """
    )
    parser.add_argument(
        'input_file',
        help='Input JSON file containing network graph data'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output GML file (default: same name as input with .gml extension)',
        default=None
    )
    parser.add_argument(
        '-c', '--campaign',
        help='Campaign name (default: Araman)',
        default='Araman'
    )
    parser.add_argument(
        '-e', '--episode',
        help='Episode number (default: infer from filename)',
        default=None
    )
    
    args = parser.parse_args()
    
    try:
        json_to_gml(args.input_file, args.output, args.campaign, args.episode)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())