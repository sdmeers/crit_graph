"""
Critical Role Campaign 4 Wiki Graph Builder
Extracts characters, organizations, NPCs, and their relationships from Campaign 4 wiki pages.

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
import time

class CampaignFourGraphBuilder:
    def __init__(self):
        self.base_url = "https://criticalrole.fandom.com"
        self.graph = nx.DiGraph()  # Directed graph for better relationship tracking
        self.entities = {}
        self.relationships = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Campaign 4 main cast characters (from the Cast table)
        self.main_characters = [
            'Thimble',               # Laura Bailey
            'Azune_Nayar',           # Luis Carazo
            'Kattigan_Vale',         # Robbie Daymond
            'Thaisha_Lloy',          # Aabria Iyengar
            'Bolaire_Lathalia',      # Taliesin Jaffe
            'Vaelus',                # Ashley Johnson
            'Julien_Davinos',        # Matthew Mercer (no "Sir_" prefix)
            'Tyranny',               # Whitney Moore
            'Halandil_Fang',         # Liam O\'Brien
            'Murray_Mag\'Nesson',    # Marisha Ray
            'Wicander_Halovar',      # Sam Riegel
            'Occtis_Tachonis',       # Alexander Ward
            'Teor_Pridesire'         # Travis Willingham
        ]
    
    def fetch_page(self, page_title):
        """Fetch a wiki page with rate limiting."""
        time.sleep(0.5)  # Be respectful to the server
        url = f"{self.base_url}/wiki/{page_title}"
        try:
            print(f"  Fetching: {page_title}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"  ⚠ Error fetching {page_title}: {e}")
            return None
    
    def extract_infobox_data(self, soup):
        """Extract structured data from the infobox."""
        data = {}
        infobox = soup.find('aside', class_='portable-infobox')
        
        if not infobox:
            return data
        
        # Extract image from infobox - try multiple locations
        # Method 1: Look for image in pi-image section
        image_container = infobox.find('figure', class_='pi-item pi-image')
        if image_container:
            image_elem = image_container.find('img')
            if image_elem:
                # Get the src or data-src attribute
                img_url = image_elem.get('src') or image_elem.get('data-src')
                if img_url:
                    data['image_url'] = img_url
                    print(f"    Found image: {img_url[:80]}...")
        
        # Method 2: Any img tag in infobox
        if 'image_url' not in data:
            image_elem = infobox.find('img')
            if image_elem:
                img_url = image_elem.get('src') or image_elem.get('data-src')
                if img_url:
                    data['image_url'] = img_url
                    print(f"    Found image (fallback): {img_url[:80]}...")
        
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
                # Get text but also preserve links
                value = value_elem.get_text(strip=True)
                data[label] = value
                
                # Also extract linked entities (for Actor, Class, Race, etc.)
                links = [a.get('href') for a in value_elem.find_all('a', href=True)]
                if links:
                    data[f'{label}_links'] = links
        
        return data
    
    def extract_relationships_section(self, soup):
        """Extract relationships from the dedicated Relationships section."""
        relationships = []
        
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            return relationships
        
        # Find the Relationships header
        for header in content.find_all(['h2', 'h3']):
            header_text = header.get_text(strip=True).lower()
            if 'relationship' in header_text:
                # Get all content until next h2/h3
                current = header.find_next_sibling()
                while current and current.name not in ['h2']:
                    # Look for h3 subsections (individual relationships)
                    if current.name == 'h3':
                        relationship_name_elem = current.find('a', href=True)
                        if relationship_name_elem:
                            href = relationship_name_elem['href']
                            # Filter out edit links and special pages
                            if (href.startswith('/wiki/') and 
                                ':' not in href and 
                                '?' not in href and 
                                'action=edit' not in href):
                                
                                target_page = href.replace('/wiki/', '')
                                # Get the description
                                desc_elem = current.find_next_sibling('p')
                                if desc_elem:
                                    desc_text = desc_elem.get_text()
                                    rel_type = self.infer_relationship_type(desc_text, relationship_name_elem.get_text())
                                    relationships.append({
                                        'target': target_page,
                                        'type': rel_type,
                                        'description': desc_text[:200]
                                    })
                    current = current.find_next_sibling()
                break
        
        return relationships
    
    def extract_biography_relationships(self, soup, current_page):
        """Extract relationships from Biography/Background sections."""
        relationships = []
        
        # Find Biography or Background section
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            return relationships
        
        # Get all text from the Biography/Background section
        biography_section = None
        for header in content.find_all(['h2', 'h3']):
            header_text = header.get_text(strip=True).lower()
            if 'biography' in header_text or 'background' in header_text:
                # Get content until next header
                biography_section = []
                for sibling in header.find_next_siblings():
                    if sibling.name in ['h2', 'h3']:
                        break
                    biography_section.append(sibling)
                break
        
        if biography_section:
            # Extract links from biography (these are potential relationships)
            for elem in biography_section:
                for link in elem.find_all('a', href=True):
                    href = link['href']
                    # Filter out non-wiki links and special pages
                    if (href.startswith('/wiki/') and 
                        ':' not in href and 
                        '?' not in href and 
                        'action=edit' not in href and
                        not href.startswith('http')):
                        
                        linked_page = href.replace('/wiki/', '')
                        # Get surrounding text for context
                        text = elem.get_text()
                        
                        # Look for relationship keywords
                        rel_type = self.infer_relationship_type(text, link.get_text())
                        relationships.append({
                            'target': linked_page,
                            'type': rel_type,
                            'source_text': text[:200]  # Keep some context
                        })
        
        return relationships
    
    def extract_organization_affiliations(self, soup, current_page):
        """Extract organization affiliations from the page."""
        affiliations = []
        
        # Organizations to look for (known from the wiki)
        org_keywords = [
            'House', 'Creed', 'Guard', 'Council', 'Order', 'Sisters',
            'Revolutionary', 'Sundered', 'Candescent', 'Sylandri'
        ]
        
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            return affiliations
        
        # Look in the first few paragraphs (Description/Appearance/Biography)
        paragraphs = content.find_all('p', limit=10)
        
        for para in paragraphs:
            text = para.get_text().lower()
            
            # Check if this paragraph mentions organizations
            if any(keyword.lower() in text for keyword in org_keywords):
                # Extract all links from this paragraph
                for link in para.find_all('a', href=True):
                    href = link['href']
                    if (href.startswith('/wiki/') and 
                        ':' not in href and 
                        '?' not in href):
                        
                        linked_page = href.replace('/wiki/', '')
                        link_text = link.get_text()
                        
                        # Check if it's likely an organization
                        if any(keyword.lower() in link_text.lower() for keyword in org_keywords):
                            # Determine relationship type from context
                            rel_type = 'member_of'
                            if 'aspirant' in text:
                                rel_type = 'aspirant_of'
                            elif 'founded' in text or 'created' in text:
                                rel_type = 'founded'
                            elif 'serves' in text or 'marshal' in text:
                                rel_type = 'serves_in'
                            elif 'member' in text:
                                rel_type = 'member_of'
                            
                            affiliations.append({
                                'target': linked_page,
                                'type': rel_type,
                                'context': text[:150]
                            })
        
        return affiliations

    def infer_relationship_type(self, context_text, target_name):
        """Infer relationship type from context."""
        context_lower = context_text.lower()
        
        # Check for specific relationship patterns
        if any(word in context_lower for word in ['served with', 'fought alongside', 'comrade']):
            return 'served_with'
        elif any(word in context_lower for word in ['member of', 'part of', 'joined']):
            return 'member_of'
        elif any(word in context_lower for word in ['friend', 'ally', 'companion']):
            return 'allied_with'
        elif any(word in context_lower for word in ['family', 'brother', 'sister', 'parent', 'child']):
            return 'family'
        elif any(word in context_lower for word in ['enemy', 'opponent', 'against']):
            return 'opposed_to'
        elif any(word in context_lower for word in ['works for', 'employed by']):
            return 'employed_by'
        else:
            return 'associated_with'
    
    def determine_entity_type(self, page_title, data, categories):
        """Determine what type of entity this is."""
        # Check if it's a main character
        if page_title in self.main_characters:
            return 'Main Character'
        
        # Check categories
        cat_text = ' '.join(categories).lower()
        
        if 'player character' in cat_text or 'pc' in cat_text:
            return 'Player Character'
        elif 'non-player character' in cat_text or 'npc' in cat_text:
            return 'NPC'
        elif 'location' in cat_text or 'city' in cat_text or 'region' in cat_text:
            return 'Location'
        elif 'organization' in cat_text or 'faction' in cat_text or 'house' in cat_text or 'group' in cat_text:
            return 'Organization'
        elif 'cast' in cat_text or 'crew' in cat_text:
            return 'Cast Member'
        elif 'episode' in cat_text:
            return 'Episode'
        elif 'event' in cat_text:
            return 'Event'
        
        # Check infobox data
        if 'Actor' in data or 'Portrayed by' in data:
            return 'Character'
        elif 'Type' in data:
            type_val = data['Type'].lower()
            if 'city' in type_val or 'town' in type_val or 'region' in type_val:
                return 'Location'
            elif 'organization' in type_val or 'faction' in type_val:
                return 'Organization'
        
        # Look at the page title
        if any(word in page_title.lower() for word in ['house', 'council', 'guard', 'creed', 'rebellion']):
            return 'Organization'
        
        return 'Unknown'
    
    def extract_categories(self, soup):
        """Extract categories/tags from the page."""
        categories = []
        cat_section = soup.find('div', id='mw-normal-catlinks')
        
        if cat_section:
            for link in cat_section.find_all('a'):
                if '/wiki/Category:' in link.get('href', ''):
                    categories.append(link.get_text(strip=True))
        
        return categories
    
    def add_metadata_nodes(self, character_page, entity_data):
        """Add nodes for race, class, and other metadata as separate entities."""
        character_name = entity_data.get('name', character_page.replace('_', ' '))
        
        # Add Race node and connection
        if 'Race' in entity_data:
            race = entity_data['Race']
            race_id = f"race_{race.replace(' ', '_')}"
            
            if race_id not in self.graph:
                self.graph.add_node(
                    race_id,
                    label=race,
                    title=f"<b>Race: {race}</b>",
                    color='#16A085',  # Teal
                    size=15,
                    shape='box'
                )
            
            self.graph.add_edge(
                character_page,
                race_id,
                title='Race',
                color='#16A085',
                width=2
            )
        
        # Add Class node(s) and connection
        if 'Class' in entity_data:
            classes = entity_data['Class']
            # Handle multi-class (e.g., "Fighter/Rogue")
            for class_name in classes.split('/'):
                class_name = class_name.strip()
                class_id = f"class_{class_name.replace(' ', '_')}"
                
                if class_id not in self.graph:
                    self.graph.add_node(
                        class_id,
                        label=class_name,
                        title=f"<b>Class: {class_name}</b>",
                        color='#8E44AD',  # Purple
                        size=15,
                        shape='box'
                    )
                
                self.graph.add_edge(
                    character_page,
                    class_id,
                    title='Class',
                    color='#8E44AD',
                    width=2
                )
        
        # Add Actor node and connection (for main characters)
        if 'Actor' in entity_data:
            actor = entity_data['Actor']
            actor_id = f"actor_{actor.replace(' ', '_')}"
            
            if actor_id not in self.graph:
                self.graph.add_node(
                    actor_id,
                    label=actor,
                    title=f"<b>Player: {actor}</b>",
                    color='#E67E22',  # Orange
                    size=20,
                    shape='dot'
                )
            
            self.graph.add_edge(
                actor_id,
                character_page,
                title='Plays',
                color='#E67E22',
                width=2
            )
    def add_entity(self, page_title, entity_data, entity_type):
        """Add an entity to the graph."""
        display_name = entity_data.get('name', page_title.replace('_', ' '))
        
        self.entities[page_title] = {
            'name': display_name,
            'type': entity_type,
            'data': entity_data
        }
        
        # Determine node properties based on type
        color_map = {
            'Main Character': '#E74C3C',      # Red
            'Player Character': '#E74C3C',     # Red
            'NPC': '#3498DB',                  # Blue
            'Location': '#2ECC71',             # Green
            'Organization': '#F39C12',         # Orange
            'Cast Member': '#9B59B6',          # Purple
            'Event': '#E67E22',                # Dark Orange
            'Character': '#1ABC9C',            # Turquoise
            'Unknown': '#95A5A6'               # Gray
        }
        
        size_map = {
            'Main Character': 30,
            'Player Character': 25,
            'NPC': 20,
            'Organization': 25,
            'Location': 20,
            'Event': 20,
            'Character': 15,
            'Unknown': 15
        }
        
        # Build hover title with key info
        title_parts = [f"<b>{display_name}</b>", f"Type: {entity_type}"]
        if 'Actor' in entity_data:
            title_parts.append(f"Played by: {entity_data['Actor']}")
        if 'Race' in entity_data:
            title_parts.append(f"Race: {entity_data['Race']}")
        if 'Class' in entity_data:
            title_parts.append(f"Class: {entity_data['Class']}")
        
        # Add image to hover tooltip if available
        image_url = entity_data.get('image_url')
        if image_url:
            # Ensure we have full URL
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            title_parts.append(f'<img src="{image_url}" width="200" />')
        
        # Node configuration
        node_config = {
            'label': display_name,
            'title': '<br>'.join(title_parts),
            'color': color_map.get(entity_type, '#95A5A6'),
            'size': size_map.get(entity_type, 15)
        }
        
        # For main characters with images, use circular image nodes
        if entity_type in ['Main Character', 'Player Character'] and image_url:
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            
            # Debug: print the image URL we're using
            print(f"    Setting image for {display_name}: {image_url[:80]}...")
            
            node_config['shape'] = 'circularImage'
            node_config['image'] = image_url
            node_config['size'] = 40  # Larger for better visibility
            node_config['borderWidth'] = 3
            node_config['borderWidthSelected'] = 5
        else:
            if entity_type in ['Main Character', 'Player Character']:
                print(f"    ⚠ No image found for {display_name}")
        
        self.graph.add_node(page_title, **node_config)
        
        # Add metadata nodes for main characters
        if entity_type in ['Main Character', 'Player Character']:
            self.add_metadata_nodes(page_title, entity_data)
    
    def add_relationship(self, source_page, target_page, rel_type='associated_with'):
        """Add an edge between entities."""
        if target_page in self.entities:
            edge_label = rel_type.replace('_', ' ').title()

            # Visual distinction for edges
            color = '#95A5A6'  # Default gray
            width = 1
            
            # Organization affiliations
            if rel_type in ['member_of', 'aspirant_of', 'serves_in', 'founded']:
                color = '#F39C12'  # Orange
                width = 3
            # Allies/served with
            elif rel_type in ['allied_with', 'served_with']:
                color = '#2ECC71'  # Green
                width = 2
            # Family
            elif rel_type == 'family':
                color = '#E74C3C'  # Red
                width = 2
            # Enemies
            elif rel_type == 'opposed_to':
                color = '#C0392B'  # Dark Red
                width = 2

            self.graph.add_edge(
                source_page, 
                target_page, 
                title=edge_label,
                label=edge_label if rel_type != 'associated_with' else '',
                color=color,
                width=width
            )
            self.relationships.append({
                'source': source_page,
                'target': target_page,
                'type': rel_type
            })
    
    def process_page(self, page_title):
        """Process a single wiki page."""
        soup = self.fetch_page(page_title)
        if not soup:
            return []
        
        # Extract data
        infobox_data = self.extract_infobox_data(soup)
        categories = self.extract_categories(soup)
        entity_type = self.determine_entity_type(page_title, infobox_data, categories)
        
        # Add to graph
        self.add_entity(page_title, infobox_data, entity_type)
        
        # Priority 1: Organization affiliations
        org_affiliations = self.extract_organization_affiliations(soup, page_title)

        # Extract relationships from dedicated Relationships section (better quality)
        relationships = self.extract_relationships_section(soup)
        
        # Also get relationships from biography (for additional context)
        bio_relationships = self.extract_biography_relationships(soup, page_title)
        
        # Combine all, with organization affiliations first
        all_relationships = org_affiliations + relationships + bio_relationships
        
        return all_relationships
    
    def build_graph(self):
        """Build the complete Campaign 4 graph."""
        print("Building Campaign Four Knowledge Graph")
        print("=" * 50)
        
        # Phase 1: Process all main characters
        print("\n[Phase 1] Processing main characters...")
        all_relationships = {}
        discovered_entities = set()
        
        for character in self.main_characters:
            print(f"\n→ {character}")
            relationships = self.process_page(character)
            all_relationships[character] = relationships
            
            # Collect entities mentioned in relationships
            for rel in relationships:
                discovered_entities.add(rel['target'])
        
        # Phase 2: Process discovered entities (organizations, NPCs, etc.)
        print(f"\n[Phase 2] Processing {len(discovered_entities)} discovered entities...")
        new_entities = discovered_entities - set(self.main_characters)
        
        for entity in list(new_entities)[:20]:  # Limit to prevent explosion
            if entity not in self.entities:
                print(f"\n→ {entity}")
                relationships = self.process_page(entity)
                all_relationships[entity] = relationships
        
        # Phase 3: Add all relationships
        print("\n[Phase 3] Adding relationships to graph...")
        for source, relationships in all_relationships.items():
            for rel in relationships:
                self.add_relationship(source, rel['target'], rel['type'])
        
        print("\n✓ Graph building complete!")
    
    def visualize(self, output_file='campaign4_graph.html'):
        """Create an interactive visualization."""
        net = Network(
            height='900px', 
            width='100%', 
            bgcolor='#1a1a1a', 
            font_color='white',
            directed=True
        )
        
        # Configure physics for better layout
        net.barnes_hut(
            gravity=-15000,
            central_gravity=0.5,
            spring_length=150,
            spring_strength=0.01,
            damping=0.09
        )
        
        # Add graph data
        net.from_nx(self.graph)
        
        # Enable physics controls
        net.show_buttons(filter_=['physics'])
        
        # Save
        net.save_graph(output_file)
        
        # Print statistics
        print(f"\n{'=' * 50}")
        print("Graph Statistics:")
        print(f"  Total Nodes: {self.graph.number_of_nodes()}")
        print(f"  Total Edges: {self.graph.number_of_edges()}")
        print(f"  Main Characters: {sum(1 for n, d in self.graph.nodes(data=True) if d.get('size', 0) >= 25)}")
        print(f"  Organizations: {len([n for n, d in self.entities.items() if d['type'] == 'Organization'])}")
        print(f"  NPCs: {len([n for n, d in self.entities.items() if d['type'] == 'NPC'])}")
        print(f"\n✓ Graph saved to {output_file}")
        print(f"  Open this file in your browser to explore!")
    
    def save_data(self, output_file='campaign4_data.json'):
        """Save entity and relationship data."""
        data = {
            'entities': self.entities,
            'relationships': self.relationships
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Data saved to {output_file}")
    
    def print_summary(self):
        """Print a summary of key findings."""
        print(f"\n{'=' * 50}")
        print("Campaign Four Summary:")
        print(f"{'=' * 50}")
        
        # Main characters with their details
        print(f"\nMain Characters ({len([n for n, d in self.entities.items() if d['type'] == 'Main Character'])}):")
        for char in self.main_characters:
            if char in self.entities:
                data = self.entities[char]['data']
                name = self.entities[char]['name']
                race = data.get('Race', 'Unknown')
                char_class = data.get('Class', 'Unknown')
                actor = data.get('Actor', 'Unknown')
                print(f"  • {name:<25} ({race:<15} {char_class:<20}) - {actor}")
        
        # Organizations found
        orgs = [name for name, data in self.entities.items() if data['type'] == 'Organization']
        if orgs:
            print(f"\nOrganizations ({len(orgs)}):")
            for org in orgs[:15]:
                print(f"  • {self.entities[org]['name']}")
        
        # Key NPCs
        npcs = [name for name, data in self.entities.items() if data['type'] == 'NPC']
        if npcs:
            print(f"\nNPCs ({len(npcs)}):")
            for npc in npcs[:15]:
                print(f"  • {self.entities[npc]['name']}")
        
        # Relationship types
        rel_types = {}
        for rel in self.relationships:
            rel_types[rel['type']] = rel_types.get(rel['type'], 0) + 1
        
        if rel_types:
            print(f"\nRelationship Types:")
            for rel_type, count in sorted(rel_types.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  • {rel_type.replace('_', ' ').title()}: {count}")


def main():
    builder = CampaignFourGraphBuilder()
    
    # Build the complete graph
    builder.build_graph()
    
    # Create visualization
    builder.visualize('campaign4_graph.html')
    
    # Save data
    builder.save_data('campaign4_data.json')
    
    # Print summary
    builder.print_summary()


if __name__ == "__main__":
    main()