"""
Critical Role Wiki Graph Builder
A starter project for building an interactive knowledge graph from Critical Role wiki pages.

Required installations:
pip install requests beautifulsoup4 networkx pyvis

Usage:
python cr_wiki_graph.py
"""

import requests
from bs4 import BeautifulSoup
import networkx as nx
from pyvis.network import Network
import re
from collections import defaultdict
import json

class CriticalRoleGraphBuilder:
    def __init__(self):
        self.base_url = "https://criticalrole.fandom.com"
        self.graph = nx.Graph()
        self.entities = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_page(self, page_title):
        """Fetch a wiki page and return BeautifulSoup object."""
        url = f"{self.base_url}/wiki/{page_title}"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"Error fetching {page_title}: {e}")
            return None
    
    def extract_infobox_data(self, soup):
        """Extract structured data from the infobox."""
        data = {}
        infobox = soup.find('aside', class_='portable-infobox')
        
        if not infobox:
            return data
        
        # Extract title
        title_elem = infobox.find('h2', class_='pi-title')
        if title_elem:
            data['name'] = title_elem.get_text(strip=True)
        
        # Extract key-value pairs
        for item in infobox.find_all('div', class_='pi-item'):
            label_elem = item.find('h3', class_='pi-data-label')
            value_elem = item.find('div', class_='pi-data-value')
            
            if label_elem and value_elem:
                label = label_elem.get_text(strip=True)
                value = value_elem.get_text(strip=True)
                data[label] = value
        
        return data
    
    def extract_links(self, soup, current_page):
        """Extract links to other wiki pages (potential relationships)."""
        links = set()
        
        # Focus on main content area
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            return links
        
        # Get all internal wiki links
        for link in content.find_all('a', href=True):
            href = link['href']
            if href.startswith('/wiki/') and ':' not in href:
                page_name = href.replace('/wiki/', '')
                # Filter out common pages
                if page_name not in ['Critical_Role', 'Campaign_Four'] and page_name != current_page:
                    links.add(page_name)
        
        return links
    
    def extract_categories(self, soup):
        """Extract categories/tags from the page."""
        categories = []
        cat_section = soup.find('div', id='mw-normal-catlinks')
        
        if cat_section:
            for link in cat_section.find_all('a'):
                if '/wiki/Category:' in link.get('href', ''):
                    categories.append(link.get_text(strip=True))
        
        return categories
    
    def determine_entity_type(self, data, categories):
        """Determine what type of entity this is."""
        # Check categories first
        cat_text = ' '.join(categories).lower()
        
        if 'player character' in cat_text or 'pc' in cat_text:
            return 'Player Character'
        elif 'non-player character' in cat_text or 'npc' in cat_text:
            return 'NPC'
        elif 'location' in cat_text or 'city' in cat_text or 'region' in cat_text:
            return 'Location'
        elif 'organization' in cat_text or 'group' in cat_text:
            return 'Organization'
        elif 'cast' in cat_text or 'crew' in cat_text:
            return 'Cast Member'
        elif 'episode' in cat_text:
            return 'Episode'
        
        # Check infobox data
        if 'Actor' in data or 'Portrayed by' in data:
            return 'Character'
        elif 'Type' in data:
            type_val = data['Type'].lower()
            if 'city' in type_val or 'town' in type_val:
                return 'Location'
            elif 'organization' in type_val:
                return 'Organization'
        
        return 'Unknown'
    
    def add_entity(self, page_title, entity_data, entity_type):
        """Add an entity to the graph."""
        self.entities[page_title] = {
            'name': entity_data.get('name', page_title.replace('_', ' ')),
            'type': entity_type,
            'data': entity_data
        }
        
        # Determine node color based on type
        color_map = {
            'Player Character': '#FF6B6B',
            'NPC': '#4ECDC4',
            'Location': '#45B7D1',
            'Organization': '#FFA07A',
            'Cast Member': '#98D8C8',
            'Episode': '#F7DC6F',
            'Character': '#BB8FCE',
            'Unknown': '#95A5A6'
        }
        
        self.graph.add_node(
            page_title,
            label=entity_data.get('name', page_title.replace('_', ' ')),
            title=f"{entity_type}: {entity_data.get('name', page_title)}",
            color=color_map.get(entity_type, '#95A5A6'),
            size=25 if entity_type == 'Player Character' else 15
        )
    
    def add_relationships(self, source_page, related_pages):
        """Add edges between entities."""
        for target_page in related_pages:
            if target_page in self.entities:
                self.graph.add_edge(source_page, target_page, weight=1)
    
    def process_page(self, page_title):
        """Process a single wiki page."""
        print(f"Processing: {page_title}")
        
        soup = self.fetch_page(page_title)
        if not soup:
            return
        
        # Extract data
        infobox_data = self.extract_infobox_data(soup)
        categories = self.extract_categories(soup)
        entity_type = self.determine_entity_type(infobox_data, categories)
        
        # Add to graph
        self.add_entity(page_title, infobox_data, entity_type)
        
        # Extract relationships
        links = self.extract_links(soup, page_title)
        
        return links
    
    def build_graph(self, starting_pages, max_depth=2):
        """Build the graph starting from a list of pages."""
        to_process = set(starting_pages)
        processed = set()
        depth = 0
        
        while to_process and depth < max_depth:
            print(f"\n--- Depth {depth} ({len(to_process)} pages) ---")
            current_batch = list(to_process)
            to_process = set()
            
            for page in current_batch:
                if page in processed:
                    continue
                
                links = self.process_page(page)
                processed.add(page)
                
                if links and depth < max_depth - 1:
                    # Add some linked pages for next depth (limit to prevent explosion)
                    to_process.update(list(links)[:5])
            
            depth += 1
        
        # Add all relationships after all entities are collected
        print("\n--- Adding relationships ---")
        for page in processed:
            soup = self.fetch_page(page)
            if soup:
                links = self.extract_links(soup, page)
                self.add_relationships(page, links)
    
    def visualize(self, output_file='cr_graph.html'):
        """Create an interactive visualization."""
        net = Network(height='800px', width='100%', bgcolor='#222222', font_color='white')
        
        # Configure physics for better layout
        net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=200)
        
        # Add graph data
        net.from_nx(self.graph)
        
        # Add legend
        net.show_buttons(filter_=['physics'])
        
        # Save
        net.save_graph(output_file)
        print(f"\n✓ Graph saved to {output_file}")
        print(f"  Nodes: {self.graph.number_of_nodes()}")
        print(f"  Edges: {self.graph.number_of_edges()}")
    
    def save_data(self, output_file='cr_data.json'):
        """Save entity data for later use."""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.entities, f, indent=2)
        print(f"✓ Entity data saved to {output_file}")


def main():
    # Initialize builder
    builder = CriticalRoleGraphBuilder()
    
    # Starting pages - main Campaign 4 characters
    # You can find these on the Campaign Four wiki page
    starting_pages = [
        'Ashton_Greymoore',
        'Fearne_Calloway',
        'Fresh_Cut_Grass',
        'Imogen_Temult',
        'Laudna',
        'Orym',
        'Chetney_Pock_O\'Pea',
        'Campaign_Four'  # Include the campaign page itself
    ]
    
    print("Critical Role Campaign 4 Knowledge Graph Builder")
    print("=" * 50)
    
    # Build the graph
    builder.build_graph(starting_pages, max_depth=2)
    
    # Create visualization
    builder.visualize('cr_campaign4_graph.html')
    
    # Save data
    builder.save_data('cr_campaign4_data.json')
    
    print("\n✓ Done! Open cr_campaign4_graph.html in your browser to view the graph.")


if __name__ == "__main__":
    main()
