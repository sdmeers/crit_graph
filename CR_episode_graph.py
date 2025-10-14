#!/usr/bin/env python3
"""
Critical Role Episode Graph Visualizer
Loads a GML file containing episode data and creates an interactive visualization
with character portraits fetched from the Critical Role wiki.

Required installations:
pip install requests beautifulsoup4 networkx pyvis

Usage:
python CR_episode_graph.py cr_c4e1_network.gml
"""

import requests
from bs4 import BeautifulSoup
import networkx as nx
from pyvis.network import Network
import time
import sys
import os
import urllib.parse

class EpisodeGraphVisualizer:
    def __init__(self, gml_file):
        self.gml_file = gml_file
        self.base_url = "https://criticalrole.fandom.com"
        self.graph = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.image_cache = {}
        self.manual_overrides = {
            "Shadia Fang": "Shadia",
            "Alogar Lloy": "Alogar"
        }
        
        # Color schemes for different node types
        self.type_colors = {
            'event': '#FF6B6B',
            'character': '#4ECDC4',
            'location': '#95E1D3',
            'object': '#F38181',
            'faction': '#AA96DA',
            'historical_event': '#FCBAD3',
            'mystery': '#A8D8EA'
        }
        
        self.type_sizes = {
            'event': 40,
            'character': 30,
            'location': 25,
            'object': 20,
            'faction': 30,
            'historical_event': 25,
            'mystery': 25
        }
        
        # Edge styles based on relationship
        self.edge_styles = {
            'brother': {'color': '#00BFFF', 'width': 3},
            'sister': {'color': '#00BFFF', 'width': 3},
            'father': {'color': '#00BFFF', 'width': 3},
            'mother': {'color': '#00BFFF', 'width': 3},
            'family': {'color': '#00BFFF', 'width': 3},
            'husband': {'color': '#FF1493', 'width': 3},
            'wife': {'color': '#FF1493', 'width': 3},
            'estranged_husband': {'color': '#FF1493', 'width': 2, 'dashes': True},
            'friend': {'color': '#00FF00', 'width': 2},
            'enemy': {'color': '#FF0000', 'width': 2},
            'conspirator': {'color': '#8A2BE2', 'width': 2},
            'member_of': {'color': '#FFD700', 'width': 2},
            'attended': {'color': '#999999', 'width': 1},
            'witnessed': {'color': '#999999', 'width': 1},
            'executed': {'color': '#FF0000', 'width': 3},
            'saved': {'color': '#00FF00', 'width': 3},
            'hates': {'color': '#FF0000', 'width': 2},
            'captured_and_hates': {'color': '#FF0000', 'width': 3}
        }
    
    def load_gml(self):
        """Load the GML file."""
        print(f"Loading GML file: {self.gml_file}")
        try:
            self.graph = nx.read_gml(self.gml_file)
            print(f"✓ Loaded graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
            return True
        except Exception as e:
            print(f"✗ Error loading GML file: {e}")
            return False
    
    def fetch_wiki_image(self, node_label):
        """Fetch an image and page URL for a node from the Critical Role wiki using a highly refined search strategy."""
        if node_label in self.image_cache:
            return self.image_cache[node_label]

        best_page_title = None

        # Strategy 0: Manual Overrides
        if node_label in self.manual_overrides:
            best_page_title = self.manual_overrides[node_label]
            print(f"  ✓ Using manual override for '{node_label}': '{best_page_title}'")
        else:
            # Strategies 1 & 2: Search API
            print(f"  Searching for wiki page for: {node_label}")
            try:
                encoded_label = urllib.parse.quote_plus(node_label)
                search_url = f"{self.base_url}/api.php?action=query&list=search&srsearch={encoded_label}&format=json&srprop=size"
                
                search_response = self.session.get(search_url, timeout=10)
                search_response.raise_for_status()
                search_data = search_response.json()
                search_results = search_data.get('query', {}).get('search', [])

                # Strategy 1: Prioritize an exact (case-insensitive) title match if it's not a tiny stub
                for result in search_results:
                    if result['title'].lower() == node_label.lower() and result.get('size', 0) > 100:
                        best_page_title = result['title']
                        print(f"    ✓ Found exact match: {best_page_title}")
                        break
                
                # Strategy 2: If no exact match, find the first large page with word overlap, avoiding common bad results.
                if not best_page_title:
                    node_label_words = {word.lower() for word in node_label.split()}
                    for result in search_results:
                        title = result['title']
                        if title == "The Fall of Thjazi Fang":
                            continue
                        title_words = {word.lower() for word in title.split()}
                        if result.get('size', 0) > 500 and node_label_words.intersection(title_words):
                            best_page_title = title
                            print(f"    ✓ Found best match by word overlap: {best_page_title}")
                            break
            except Exception as e:
                print(f"    ⚠ Error searching for {node_label}: {e}")
                self.image_cache[node_label] = None
                return None

        # If a page title was found (by override or search), fetch and process it.
        if not best_page_title:
            self.image_cache[node_label] = None
            return None

        try:
            page_wiki_name = best_page_title.replace(' ', '_')
            page_url = f"{self.base_url}/wiki/{page_wiki_name}"

            time.sleep(0.5)
            response = self.session.get(page_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            image_url = None
            infobox = soup.find('aside', class_='portable-infobox')
            if infobox:
                image_container = infobox.find('figure', class_='pi-item pi-image')
                if image_container:
                    image_elem = image_container.find('img')
                    if image_elem:
                        img_url = image_elem.get('src') or image_elem.get('data-src')
                        if img_url:
                            if '/revision/latest' in img_url:
                                img_url = img_url.split('/revision/latest')[0]
                            if img_url.startswith('//'):
                                img_url = 'https:' + img_url
                            image_url = img_url
            
            if not image_url and infobox: # Fallback
                image_elem = infobox.find('img')
                if image_elem:
                    img_url = image_elem.get('src') or image_elem.get('data-src')
                    if img_url:
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url
                        image_url = img_url

            if image_url:
                print(f"    ✓ Found image on page: {image_url[:80]}...")

            result = {'image_url': image_url, 'page_url': page_url}
            self.image_cache[node_label] = result
            return result

        except Exception as e:
            print(f"    ⚠ Error processing page for {node_label}: {e}")
            self.image_cache[node_label] = None
            return None

    def enhance_graph(self):
        """Enhance graph nodes with portraits and styling."""
        print("\nEnhancing graph with portraits and styling...")
        
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            node_type = node_data.get('type', 'unknown')
            
            if isinstance(node_type, list):
                node_type = node_type[0] if node_type else 'unknown'
            
            label = node_data.get('label', str(node_id))
            
            if isinstance(label, list):
                label = label[0] if label else str(node_id)
            
            color = self.type_colors.get(node_type, '#999999')
            size = self.type_sizes.get(node_type, 20)
            
            # Fetch image and page URL
            wiki_data = self.fetch_wiki_image(label)
            image_url, page_url = (None, None)
            if wiki_data:
                image_url = wiki_data.get('image_url')
                page_url = wiki_data.get('page_url')

            # Build hover title
            title_parts = [f"<b>{label}</b>"]
            if node_type:
                title_parts.append(f"Type: {node_type.replace('_', ' ').title()}")
            
            for key, value in node_data.items():
                if key not in ['label', 'type', 'id'] and value:
                    if isinstance(value, list):
                        value = ', '.join(str(v) for v in value)
                    clean_key = key.replace('_', ' ').title()
                    title_parts.append(f"{clean_key}: {value}")
            
            # Configure node
            node_config = {
                'label': label,
                'color': color,
                'size': size,
            }

            if page_url:
                node_config['url'] = page_url
                title_parts.append("<br><i>Click to open wiki page</i>")

            node_config['title'] = '<br>'.join(title_parts)

            if image_url:
                node_config.update({
                    'shape': 'circularImage',
                    'image': image_url,
                    'size': size * 2,
                    'borderWidth': 3,
                    'borderWidthSelected': 5,
                    'color': {
                        'border': color,
                        'background': color,
                        'highlight': {'border': color, 'background': color}
                    },
                    'title': node_config['title'] + f'<br><img src="{image_url}" width="200" />'
                })
            
            self.graph.nodes[node_id].update(node_config)
        
        # Enhance edges
        print("\nEnhancing edges...")
        for source, target, edge_data in self.graph.edges(data=True):
            label = edge_data.get('label', '')
            
            # Handle case where label might be a list
            if isinstance(label, list):
                label = label[0] if label else ''
            
            # Get style based on label
            style = self.edge_styles.get(label, {'color': '#999999', 'width': 1})
            
            # Update edge with style
            self.graph.edges[source, target]['color'] = style['color']
            self.graph.edges[source, target]['width'] = style['width']
            if 'dashes' in style:
                self.graph.edges[source, target]['dashes'] = style['dashes']
            
            # Keep the label
            if label:
                self.graph.edges[source, target]['title'] = label
    
    def create_visualization(self, output_file='episode_graph.html'):
        """Create an interactive visualization."""
        print(f"\nCreating visualization: {output_file}")
        
        # Create PyVis network
        net = Network(
            height='900px',
            width='100%',
            bgcolor='#1a1a1a',
            font_color='white',
            directed=True
        )
        
        # Configure physics
        net.barnes_hut(
            gravity=-15000,
            central_gravity=0.5,
            spring_length=200,
            spring_strength=0.01,
            damping=0.09
        )
        
        # Load graph into PyVis
        net.from_nx(self.graph)
        
        # Show physics controls
        net.show_buttons(filter_=['physics'])
        
        # Save initial HTML
        net.save_graph(output_file)
        
        # Enhance HTML with legend and interactivity
        self.enhance_html(output_file)
        
        print(f"✓ Visualization saved to {output_file}")
    
    def enhance_html(self, html_file):
        """Add legend and enhanced interactivity to HTML."""
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Add CSS
            css_additions = '''
    <style>
    body {
        margin: 0;
        padding: 0;
        overflow: hidden;
    }
    #mynetwork {
        width: 100vw;
        height: 100vh;
    }
    #legend {
        position: absolute;
        top: 20px;
        right: 20px;
        background-color: rgba(26, 26, 26, 0.95);
        border: 2px solid #444;
        border-radius: 8px;
        padding: 15px;
        color: white;
        font-family: Arial, sans-serif;
        font-size: 13px;
        max-width: 280px;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        z-index: 1000;
    }
    #legend h3 {
        margin: 0 0 10px 0;
        font-size: 16px;
        border-bottom: 1px solid #555;
        padding-bottom: 8px;
    }
    .legend-section {
        margin-bottom: 15px;
    }
    .legend-section h4 {
        margin: 0 0 8px 0;
        font-size: 14px;
        color: #aaa;
    }
    .legend-item {
        display: flex;
        align-items: center;
        margin: 5px 0;
        font-size: 12px;
    }
    .legend-color {
        width: 20px;
        height: 20px;
        border-radius: 3px;
        margin-right: 8px;
        flex-shrink: 0;
    }
    .legend-line {
        width: 30px;
        height: 3px;
        margin-right: 8px;
        flex-shrink: 0;
    }
    #legend-close {
        position: absolute;
        top: 10px;
        right: 10px;
        cursor: pointer;
        font-size: 18px;
        color: #aaa;
    }
    #legend-close:hover {
        color: white;
    }
    #legend-toggle {
        position: absolute;
        top: 20px;
        right: 20px;
        background-color: rgba(26, 26, 26, 0.95);
        border: 2px solid #444;
        border-radius: 8px;
        padding: 10px 15px;
        color: white;
        font-family: Arial, sans-serif;
        font-size: 14px;
        cursor: pointer;
        z-index: 1001;
        display: none;
    }
    #legend-toggle:hover {
        background-color: rgba(40, 40, 40, 0.95);
    }
    </style>
    '''
            html_content = html_content.replace('</head>', css_additions + '</head>')
            
            # Add legend HTML
            legend_html = '''
    <div id="legend">
        <span id="legend-close">✕</span>
        <h3>📊 Critical Role C4E1</h3>
        
        <div class="legend-section">
            <h4>Node Types</h4>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FF6B6B;"></div>
                <span>Event</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #4ECDC4;"></div>
                <span>Character</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #95E1D3;"></div>
                <span>Location</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #F38181;"></div>
                <span>Object</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #AA96DA;"></div>
                <span>Faction</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FCBAD3;"></div>
                <span>Historical Event</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #A8D8EA;"></div>
                <span>Mystery</span>
            </div>
        </div>
        
        <div class="legend-section">
            <h4>Key Relationships</h4>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #00BFFF;"></div>
                <span>Family</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #FF1493;"></div>
                <span>Romantic</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #00FF00;"></div>
                <span>Friend/Ally</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #FF0000;"></div>
                <span>Enemy/Hostile</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #8A2BE2;"></div>
                <span>Conspiracy</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #FFD700;"></div>
                <span>Membership</span>
            </div>
        </div>
        
        <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #555; font-size: 11px; color: #aaa;">
            💡 Click nodes to open wiki<br>
            💡 Drag to move, scroll to zoom<br>
            💡 Click and drag background to pan
        </div>
    </div>

    <button id="legend-toggle">Show Legend</button>
    '''
            
            if '<body>' in html_content:
                html_content = html_content.replace('<body>', '<body>\n' + legend_html, 1)
            
            # Add JavaScript for interactivity
            js_additions = '''
    <script type="text/javascript">
    window.addEventListener('load', function() {
        // Legend handling
        var legend = document.getElementById('legend');
        var legendToggle = document.getElementById('legend-toggle');
        var legendClose = document.getElementById('legend-close');
        var legendVisible = true;

        function toggleLegend() {
            legendVisible = !legendVisible;
            if (legendVisible) {
                legend.style.display = 'block';
                legendToggle.style.display = 'none';
            } else {
                legend.style.display = 'none';
                legendToggle.style.display = 'block';
            }
        }

        if (legendToggle) {
            legendToggle.addEventListener('click', toggleLegend);
        }
        if (legendClose) {
            legendClose.addEventListener('click', toggleLegend);
        }

        // Network interactivity
        setTimeout(function() {
            if (typeof network !== 'undefined' && typeof nodes !== 'undefined') {
                var canvas = document.querySelector('#mynetwork canvas');

                network.on("click", function(params) {
                    if (params.nodes.length > 0) {
                        var nodeId = params.nodes[0];
                        var clickedNode = nodes.get(nodeId);
                        if (clickedNode && clickedNode.url) {
                            window.open(clickedNode.url, "_blank");
                        }
                    }
                });

                network.on("hoverNode", function(params) {
                    var nodeId = params.node;
                    var node = nodes.get(nodeId);
                    if (node && node.url) {
                        if (canvas) canvas.style.cursor = 'pointer';
                    }
                });

                network.on("blurNode", function(params) {
                    if (canvas) canvas.style.cursor = 'default';
                });
                
                if (canvas) {
                    canvas.addEventListener('mousemove', function(event) {
                        var pointer = {
                            x: event.offsetX || (event.pageX - canvas.offsetLeft),
                            y: event.offsetY || (event.pageY - canvas.offsetTop)
                        };
                        var nodeId = network.getNodeAt(pointer);
                        if (nodeId) {
                            var node = nodes.get(nodeId);
                            if (node && node.url) {
                                canvas.style.cursor = 'pointer';
                            } else {
                                canvas.style.cursor = 'default';
                            }
                        } else {
                            canvas.style.cursor = 'default';
                        }
                    });
                }
            }
        }, 1000); // Wait a bit for the network to initialize
    });
    </script>
    '''
            html_content = html_content.replace('</body>', js_additions + '\n</body>')
            
            # Write modified HTML
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print("  ✓ Enhanced HTML with legend and interactivity")
            
        except Exception as e:
            print(f"  ⚠ Error enhancing HTML: {e}")
    
    def print_statistics(self):
        """Print graph statistics."""
        print(f"\n{'=' * 60}")
        print("Graph Statistics")
        print(f"{ '=' * 60}")
        print(f"Total Nodes: {self.graph.number_of_nodes()}")
        print(f"Total Edges: {self.graph.number_of_edges()}")
        
        # Count by type
        type_counts = {}
        for node_id in self.graph.nodes():
            node_type = self.graph.nodes[node_id].get('type', 'unknown')
            # Handle case where type might be a list
            if isinstance(node_type, list):
                node_type = node_type[0] if node_type else 'unknown'
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
        
        print("\nNodes by Type:")
        for node_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {node_type.replace('_', ' ').title()}: {count}")
        
        # Count images found
        images_found = sum(1 for img in self.image_cache.values() if img is not None)
        if self.image_cache:
            print(f"\nImages Found: {images_found}/{len(self.image_cache)}")
        
        print(f"{ '=' * 60}")
    
    def run(self, output_file='episode_graph.html'):
        """Main execution flow."""
        print("Critical Role Episode Graph Visualizer")
        print("=" * 60)
        
        # Load GML
        if not self.load_gml():
            return False
        
        # Enhance graph
        self.enhance_graph()
        
        # Create visualization
        self.create_visualization(output_file)
        
        # Print statistics
        self.print_statistics()
        
        print(f"\n✓ Complete! Open {output_file} in your browser to explore the graph.")
        return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python CR_episode_graph.py <gml_file> [output_file]")
        print("\nExample:")
        print("  python CR_episode_graph.py transcripts/cr_c4e1_network.gml docs/episode1_graph.html")
        sys.exit(1)
    
    gml_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'docs/episode1_graph.html'
    
    if not os.path.exists(gml_file):
        print(f"Error: GML file not found: {gml_file}")
        sys.exit(1)

    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    visualizer = EpisodeGraphVisualizer(gml_file)
    success = visualizer.run(output_file)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
