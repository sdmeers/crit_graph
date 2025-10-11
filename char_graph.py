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
import urllib.parse

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
        self.alias_map = {}
        
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
    
    def normalize_page_title(self, page_title):
        """Normalize a page title to a standard format."""
        # Remove any URL fragments or query parameters first
        if '#' in page_title:
            page_title = page_title.split('#')[0]
        if '?' in page_title:
            page_title = page_title.split('?')[0]
        
        # Decode URL encoding
        normalized = urllib.parse.unquote(page_title)
        # Replace spaces with underscores
        normalized = normalized.replace(' ', '_')
        # Remove /wiki/ prefix if present
        normalized = normalized.replace('/wiki/', '')
        # Remove trailing slashes
        normalized = normalized.rstrip('/')
        
        return normalized
    
    def get_canonical_name(self, page_title):
        """Get the canonical name for a page, using alias map if available."""
        normalized = self.normalize_page_title(page_title)
        # Check if we've already fetched this and know its canonical name
        if normalized in self.alias_map:
            return self.alias_map[normalized]
        return normalized
    
    def fetch_page(self, page_title):
        """Fetch a wiki page with rate limiting and handle redirects."""
        time.sleep(0.5)  # Be respectful to the server
        
        # Normalize the input
        page_title = self.normalize_page_title(page_title)
        
        url = f"{self.base_url}/wiki/{page_title}"
        try:
            print(f"  Fetching: {page_title}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Get the final URL after any redirects
            final_url = response.url
            
            # Extract the page name from the URL
            url_path = final_url.split('/wiki/')[-1]
            
            # CRITICAL: Remove fragment from the URL before processing
            if '#' in url_path:
                url_path = url_path.split('#')[0]
            
            canonical_name = urllib.parse.unquote(url_path)
            canonical_name = canonical_name.replace(' ', '_')
            
            if page_title != canonical_name:
                print(f"    Redirected to: {canonical_name}")
                # Store the alias mapping
                self.alias_map[page_title] = canonical_name
            else:
                # Even if no redirect, store identity mapping
                self.alias_map[page_title] = canonical_name
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup, canonical_name
        except Exception as e:
            print(f"  ⚠ Error fetching {page_title}: {e}")
            return None, None
    
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
        
        # Method 2: Any img tag in infobox
        if 'image_url' not in data:
            image_elem = infobox.find('img')
            if image_elem:
                img_url = image_elem.get('src') or image_elem.get('data-src')
                if img_url:
                    data['image_url'] = img_url
        
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
                                'action=edit' not in href):
                                
                                # Remove fragment BEFORE normalizing
                                if '#' in href:
                                    href = href.split('#')[0]
                                if '?' in href:
                                    href = href.split('?')[0]
                                
                                target_page = self.normalize_page_title(href)
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
                        'action=edit' not in href and
                        not href.startswith('http')):
                        
                        # Remove fragment BEFORE normalizing
                        if '#' in href:
                            href = href.split('#')[0]
                        if '?' in href:
                            href = href.split('?')[0]
                        
                        linked_page = self.normalize_page_title(href)
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
                        ':' not in href):
                        
                        # Remove fragment BEFORE normalizing
                        if '#' in href:
                            href = href.split('#')[0]
                        if '?' in href:
                            href = href.split('?')[0]
                        
                        linked_page = self.normalize_page_title(href)
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
        elif any(word in context_lower for word in ['member of', 'part of', 'joined', 'belongs to']):
            return 'member_of'
        elif any(word in context_lower for word in ['aspirant', 'novice', 'initiate']):
            return 'aspirant_of'
        elif any(word in context_lower for word in ['friend', 'ally', 'companion']):
            return 'allied_with'
        elif any(word in context_lower for word in ['family', 'brother', 'sister', 'parent', 'child']):
            return 'family'
        elif any(word in context_lower for word in ['enemy', 'opponent', 'against']):
            return 'opposed_to'
        elif any(word in context_lower for word in ['works for', 'employed by', 'serves']):
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
        
        # Add click instruction
        title_parts.append("<br><i>Click to open wiki page</i>")
        
        # Node configuration
        node_config = {
            'label': display_name,
            'title': '<br>'.join(title_parts),
            'color': color_map.get(entity_type, '#95A5A6'),
            'size': size_map.get(entity_type, 15),
            'url': f"{self.base_url}/wiki/{page_title}"  # Add wiki URL
        }
        
        # For main characters with images, use circular image nodes
        if entity_type in ['Main Character', 'Player Character'] and image_url:
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            
            node_config['shape'] = 'circularImage'
            node_config['image'] = image_url
            node_config['size'] = 40  # Larger for better visibility
            node_config['borderWidth'] = 3
            node_config['borderWidthSelected'] = 5
        
        self.graph.add_node(page_title, **node_config)
        
        # Add metadata nodes for main characters
        if entity_type in ['Main Character', 'Player Character']:
            self.add_metadata_nodes(page_title, entity_data)
    
    def add_relationship(self, source_page, target_page, rel_type='associated_with'):
        """Add an edge between entities, avoiding duplicates."""
        if target_page not in self.entities:
            return
            
        # Check if this exact relationship already exists
        if self.graph.has_edge(source_page, target_page):
            # Edge already exists - check if we should update it
            existing_edge = self.graph[source_page][target_page]
            existing_type = existing_edge.get('title', '').lower().replace(' ', '_')
            
            # Prioritize more specific relationship types
            priority = {
                'member_of': 3,
                'aspirant_of': 3,
                'serves_in': 3,
                'founded': 3,
                'family': 2,
                'allied_with': 2,
                'served_with': 2,
                'opposed_to': 2,
                'employed_by': 1,
                'associated_with': 0
            }
            
            if priority.get(rel_type, 0) > priority.get(existing_type, 0):
                # New relationship is more specific, update it
                pass
            else:
                # Keep existing relationship
                return
        
        # Determine edge styling based on relationship type
        edge_color = '#999999'  # Default gray
        edge_width = 1
        
        if rel_type in ['member_of', 'aspirant_of', 'serves_in']:
            edge_color = '#F39C12'  # Orange for organizations
            edge_width = 3
        elif rel_type == 'family':
            edge_color = '#E74C3C'  # Red for family
            edge_width = 2
        elif rel_type in ['allied_with', 'served_with']:
            edge_color = '#2ECC71'  # Green for allies
            edge_width = 2
        elif rel_type == 'opposed_to':
            edge_color = '#C0392B'  # Dark red for enemies
            edge_width = 2
        
        # Add edge with relationship type
        edge_label = rel_type.replace('_', ' ').title()
        self.graph.add_edge(
            source_page, 
            target_page, 
            title=edge_label,
            label=edge_label if rel_type != 'associated_with' else '',
            color=edge_color,
            width=edge_width
        )
        
        # Only add to relationships list if not already there
        rel_exists = any(
            r['source'] == source_page and 
            r['target'] == target_page and 
            r['type'] == rel_type 
            for r in self.relationships
        )
        
        if not rel_exists:
            self.relationships.append({
                'source': source_page,
                'target': target_page,
                'type': rel_type
            })
    
    def process_page(self, page_title):
        """Process a single wiki page, handling redirects."""
        # Normalize input
        page_title = self.normalize_page_title(page_title)
        
        # Check if we already know the canonical name (from a previous fetch)
        if page_title in self.alias_map:
            canonical_name = self.alias_map[page_title]
            if canonical_name in self.entities:
                print(f"    Already processed (via alias): {canonical_name}")
                return []
        
        soup, canonical_name = self.fetch_page(page_title)
        
        if not canonical_name:  # Fetch failed
            return []

        # If the canonical entity is already in the graph, we're done with this page.
        if canonical_name in self.entities:
            print(f"    Already processed: {canonical_name}")
            return []

        # Add entity using canonical name
        infobox_data = self.extract_infobox_data(soup)
        categories = self.extract_categories(soup)
        entity_type = self.determine_entity_type(canonical_name, infobox_data, categories)
        self.add_entity(canonical_name, infobox_data, entity_type)

        # Extract relationships (targets are now normalized)
        org_affiliations = self.extract_organization_affiliations(soup, canonical_name)
        relationships = self.extract_relationships_section(soup)
        bio_relationships = self.extract_biography_relationships(soup, canonical_name)
        
        all_relationships = org_affiliations + relationships + bio_relationships
        return all_relationships
    
    def build_graph(self):
        """Build the complete Campaign 4 graph."""
        print("Building Campaign Four Knowledge Graph")
        print("=" * 50)
        
        # Phase 1: Process entities and collect relationships
        print("\n[Phase 1] Processing entities and collecting relationships...")
        all_relationships = {}
        queue = list(self.main_characters)
        processed = set()  # Track what we've already processed (canonical names)
        
        limit = 50  # Set a hard limit to avoid crawling the whole wiki
        count = 0

        while queue and count < limit:
            page_title = queue.pop(0)
            
            # Normalize the page title
            normalized = self.normalize_page_title(page_title)
            
            # Check if we've already processed this canonical entity
            canonical = self.get_canonical_name(normalized)
            if canonical in processed:
                continue
            
            count += 1
            print(f"\n→ Processing {normalized} ({count}/{limit})")

            relationships = self.process_page(normalized)
            
            # Mark the canonical name as processed
            canonical = self.get_canonical_name(normalized)
            if canonical:
                processed.add(canonical)
                all_relationships[canonical] = relationships
                
                # Add related entities to queue
                for rel in relationships:
                    target = self.normalize_page_title(rel['target'])
                    # Extra safety: strip fragments again
                    if '#' in target:
                        target = target.split('#')[0]
                    
                    target_canonical = self.get_canonical_name(target)
                    
                    # Only add to queue if not already processed and not in queue
                    if target_canonical not in processed and target not in queue:
                        queue.append(target)

        # Phase 2: Resolve all relationship targets by fetching them
        print("\n[Phase 2] Resolving canonical names for all relationships...")
        unresolved_targets = set()
        
        # Collect all unique targets that we haven't processed yet
        for source_canonical, relationships in all_relationships.items():
            for rel in relationships:
                target = self.normalize_page_title(rel['target'])
                target_canonical = self.get_canonical_name(target)
                
                # If the target wasn't processed (not in entities), we need to resolve it
                if target_canonical not in self.entities:
                    # Make sure we strip fragments before adding to unresolved
                    clean_target = target.split('#')[0] if '#' in target else target
                    unresolved_targets.add(clean_target)
        
        print(f"  Found {len(unresolved_targets)} unresolved targets")
        
        # Fetch each unresolved target just to get its canonical name (don't process fully)
        for target in unresolved_targets:
            if self.get_canonical_name(target) not in self.entities:
                soup, canonical = self.fetch_page(target)
                # We don't need to process it, just needed to populate alias_map
        
        # Phase 3: Add all relationships using fully resolved canonical names
        print("\n[Phase 3] Adding relationships to graph...")
        for source_canonical, relationships in all_relationships.items():
            for rel in relationships:
                target = self.normalize_page_title(rel['target'])
                
                # Now get the canonical name (should be in alias_map from Phase 2)
                target_canonical = self.get_canonical_name(target)
                
                # Only add relationship if both entities exist in the graph
                if source_canonical in self.entities and target_canonical in self.entities:
                    self.add_relationship(source_canonical, target_canonical, rel['type'])
        
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
        
        # Save the initial graph
        net.save_graph(output_file)
        
        # Modify the HTML to add click handler and cursor behavior
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Add CSS for removing white margin
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
</style>
'''
            html_content = html_content.replace('</head>', css_additions + '</head>')
            
            # Add JavaScript for click handling and cursor changes
            js_additions = '''
<script type="text/javascript">
// Wait for page to fully load
window.addEventListener('load', function() {
    setTimeout(function() {
        if (typeof network !== 'undefined' && typeof nodes !== 'undefined') {
            var canvas = document.querySelector('#mynetwork canvas');
            
            // Handle node clicks to open wiki pages
            network.on("click", function(params) {
                if (params.nodes.length > 0) {
                    var nodeId = params.nodes[0];
                    var clickedNode = nodes.get(nodeId);
                    if (clickedNode && clickedNode.url) {
                        window.open(clickedNode.url, "_blank");
                    }
                }
            });
            
            // Change cursor to pointer when hovering over nodes
            network.on("hoverNode", function(params) {
                if (canvas) {
                    canvas.style.cursor = 'pointer';
                }
            });
            
            network.on("blurNode", function(params) {
                if (canvas) {
                    canvas.style.cursor = 'default';
                }
            });
            
            // Fallback cursor handler using pointer position
            if (canvas) {
                canvas.addEventListener('mousemove', function(event) {
                    var pointer = {
                        x: event.offsetX || (event.pageX - canvas.offsetLeft),
                        y: event.offsetY || (event.pageY - canvas.offsetTop)
                    };
                    
                    var nodeId = network.getNodeAt(pointer);
                    
                    if (nodeId) {
                        canvas.style.cursor = 'pointer';
                    } else {
                        canvas.style.cursor = 'default';
                    }
                });
            }
        }
    }, 2000);
});
</script>
'''
            html_content = html_content.replace('</body>', js_additions + '\n</body>')
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
                    
        except Exception as e:
            print(f"  ⚠ Error modifying HTML: {e}")
        
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
        print(f"  💡 Click any node to open its wiki page in a new tab")
        print(f"  💡 Hover over nodes to see the pointer cursor")
    
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
            canonical = self.get_canonical_name(char)
            if canonical in self.entities:
                data = self.entities[canonical]['data']
                name = self.entities[canonical]['name']
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