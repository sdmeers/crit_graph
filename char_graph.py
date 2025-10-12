"""
Critical Role Campaign 4 Wiki Graph Builder with LLM Relationship Classification
Extracts characters, organizations, NPCs, and their relationships from Campaign 4 wiki pages.
Uses local Ollama LLM to classify complex relationships.

Required installations:
pip install requests beautifulsoup4 networkx pyvis

Requires Ollama running locally with llama3.1:8b model

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
    def __init__(self, ollama_model="llama3.1:8b", ollama_url="http://localhost:11434"):
        self.base_url = "https://criticalrole.fandom.com"
        self.graph = nx.DiGraph()
        self.entities = {}
        self.relationships = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.alias_map = {}
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self.llm_cache = {}  # Cache LLM responses to avoid re-processing same text
        
        # New relationship mapping, precedence, and styles
        self.RELATIONSHIP_MAP = {
            'family': 'Family',
            'romantic_partner': 'Romantic Partner',
            'close_friend': 'Ally',
            'ally': 'Ally',
            'served_together': 'Ally',
            'mentor_student': 'Ally',
            'enemy': 'Enemy',
            'rival': 'Enemy',
            'complicated': 'Complicated',
            'member_of': 'Member Of',
            'leads': 'Member Of',
            'aspirant_of': 'Member Of',
            'serves_in': 'Member Of',
            'founded': 'Member Of',
            'associated_with': 'Associated With'
        }
        
        self.PRECEDENCE = ['Enemy', 'Family', 'Romantic Partner', 'Ally', 'Complicated', 'Member Of', 'Associated With']

        self.RELATIONSHIP_STYLES = {
            'Family': {'color': '#00BFFF', 'width': 3, 'label': 'Family'},  # Blue
            'Romantic Partner': {'color': '#FF1493', 'width': 3, 'label': 'Romantic Partner'},  # Pink
            'Ally': {'color': '#00FF00', 'width': 2, 'label': 'Ally'},  # Green
            'Enemy': {'color': '#FF0000', 'width': 2, 'label': 'Enemy'},  # Red
            'Complicated': {'color': '#8A2BE2', 'width': 2, 'label': 'Complicated'},  # Purple
            'Member Of': {'color': '#FFD700', 'width': 3, 'label': 'Member Of'},  # Yellow
            'Associated With': {'color': '#999999', 'width': 1, 'label': ''}  # Grey
        }
        
        # Campaign 4 main cast characters
        self.main_characters = [
            'Thimble',
            'Azune_Nayar',
            'Kattigan_Vale',
            'Thaisha_Lloy',
            'Bolaire_Lathalia',
            'Vaelus',
            'Julien_Davinos',
            'Tyranny',
            'Halandil_Fang',
            'Murray_Mag\'Nesson',
            'Wicander_Halovar',
            'Occtis_Tachonis',
            'Teor_Pridesire'
        ]
    
    def classify_relationship_with_llm(self, source_name, target_name, relationship_text):
        """Use local LLM to classify relationship types from text."""
        # Create cache key from text
        cache_key = f"{source_name}:{target_name}:{relationship_text[:100]}"
        if cache_key in self.llm_cache:
            return self.llm_cache[cache_key]
        
        # Truncate very long text to avoid token limits
        if len(relationship_text) > 1500:
            relationship_text = relationship_text[:1500] + "..."
        
        prompt = f"""Analyze the relationship between {source_name} and {target_name} based on this text:

"{relationship_text}"

Classify their relationship as one or more of these categories:
- family (blood relatives, spouses, adopted family)
- romantic_partner (current or past romantic relationship)
- close_friend (deep friendship, bonded companions)
- ally (working together, mutual support)
- served_together (military service, combat companions)
- mentor_student (teaching/learning relationship)
- enemy (opposed, hostile)
- rival (competitive but not necessarily hostile)
- complicated (complex relationship that doesn't fit simple categories)
- member_of (organizational membership)
- leads (leadership role)

Output ONLY the category or categories that apply, comma-separated, with no explanation.
Example outputs: "close_friend,ally" or "enemy" or "complicated,family"

Categories:"""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent classification
                        "top_p": 0.9,
                        "num_predict": 50  # Short response expected
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                classification = result.get('response', '').strip().lower()
                
                # Parse the response - extract only valid categories
                valid_categories = {
                    'family', 'romantic_partner', 'close_friend', 'ally', 
                    'served_together', 'mentor_student', 'enemy', 'rival',
                    'complicated', 'member_of', 'leads'
                }
                
                # Extract categories from response
                found_categories = []
                for category in valid_categories:
                    if category in classification or category.replace('_', ' ') in classification:
                        found_categories.append(category)
                
                # If no valid categories found, default to associated_with
                if not found_categories:
                    found_categories = ['associated_with']
                
                # Cache the result
                self.llm_cache[cache_key] = found_categories
                
                print(f"    LLM classified as: {', '.join(found_categories)}")
                return found_categories
            else:
                print(f"    ⚠ LLM request failed: {response.status_code}")
                return ['associated_with']
                
        except requests.exceptions.Timeout:
            print(f"    ⚠ LLM request timed out")
            return ['associated_with']
        except Exception as e:
            print(f"    ⚠ LLM error: {e}")
            return ['associated_with']
    
    def clean_display_text(self, text):
        """Remove wiki reference brackets [1], [2], etc. from display text."""
        cleaned = re.sub(r'\[\d+\]', '', text)
        cleaned = re.sub(r'\[citation needed\]', '', cleaned)
        cleaned = re.sub(r'\[presumed.*?\]', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def normalize_page_title(self, page_title):
        """Normalize a page title to a standard format."""
        if '#' in page_title:
            page_title = page_title.split('#')[0]
        if '?' in page_title:
            page_title = page_title.split('?')[0]
        
        normalized = urllib.parse.unquote(page_title)
        normalized = normalized.replace(' ', '_')
        normalized = normalized.replace('/wiki/', '')
        normalized = normalized.rstrip('/')
        
        return normalized
    
    def get_canonical_name(self, page_title):
        """Get the canonical name for a page, using alias map if available."""
        normalized = self.normalize_page_title(page_title)
        if normalized in self.alias_map:
            return self.alias_map[normalized]
        return normalized
    
    def fetch_page(self, page_title):
        """Fetch a wiki page with rate limiting and handle redirects."""
        time.sleep(0.5)
        
        page_title = self.normalize_page_title(page_title)
        url = f"{self.base_url}/wiki/{page_title}"
        
        try:
            print(f"  Fetching: {page_title}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            final_url = response.url
            url_path = final_url.split('/wiki/')[-1]
            
            if '#' in url_path:
                url_path = url_path.split('#')[0]
            
            canonical_name = urllib.parse.unquote(url_path)
            canonical_name = canonical_name.replace(' ', '_')
            
            if page_title != canonical_name:
                print(f"    Redirected to: {canonical_name}")
                self.alias_map[page_title] = canonical_name
            else:
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
        
        # Extract image
        image_container = infobox.find('figure', class_='pi-item pi-image')
        if image_container:
            image_elem = image_container.find('img')
            if image_elem:
                img_url = image_elem.get('src') or image_elem.get('data-src')
                if img_url:
                    if '/revision/latest' in img_url:
                        img_url = img_url.split('/revision/latest')[0]
                    data['image_url'] = img_url
        
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
                value = value_elem.get_text(strip=True)
                data[label] = value
                
                links = [a.get('href') for a in value_elem.find_all('a', href=True)]
                if links:
                    data[f'{label}_links'] = links
        
        return data
    
    def extract_relationships_section(self, soup, current_page_name):
        """Extract relationships from the dedicated Relationships section with full context."""
        relationships = []
        
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            return relationships
        
        # Find the Relationships header
        for header in content.find_all(['h2', 'h3']):
            header_text = header.get_text(strip=True).lower()
            if 'relationship' in header_text:
                current = header.find_next_sibling()
                
                while current and current.name not in ['h2']:
                    if current.name == 'h3':
                        # Found a relationship subsection
                        relationship_name_elem = current.find('a', href=True)
                        
                        if relationship_name_elem:
                            href = relationship_name_elem['href']
                            
                            if (href.startswith('/wiki/') and 
                                ':' not in href and 
                                'action=edit' not in href):
                                
                                if '#' in href:
                                    href = href.split('#')[0]
                                if '?' in href:
                                    href = href.split('?')[0]
                                
                                target_page = self.normalize_page_title(href)
                                target_display_name = relationship_name_elem.get_text(strip=True)
                                
                                # Collect ALL paragraphs for this relationship until next h3 or h2
                                relationship_text = []
                                text_elem = current.find_next_sibling()
                                
                                while text_elem and text_elem.name not in ['h2', 'h3']:
                                    if text_elem.name == 'p':
                                        relationship_text.append(text_elem.get_text(strip=True))
                                    text_elem = text_elem.find_next_sibling()
                                
                                full_text = ' '.join(relationship_text)
                                
                                if full_text:
                                    # Use LLM to classify the relationship
                                    print(f"    Analyzing relationship: {current_page_name} → {target_display_name}")
                                    rel_types = self.classify_relationship_with_llm(
                                        current_page_name,
                                        target_display_name,
                                        full_text
                                    )
                                    
                                    relationships.append({
                                        'target': target_page,
                                        'types': rel_types,
                                        'description': full_text[:500],  # Keep more context
                                        'full_text': full_text
                                    })
                    
                    current = current.find_next_sibling()
                break
        
        return relationships
    
    def extract_biography_relationships(self, soup, current_page):
        """Extract relationships from Biography/Background sections."""
        relationships = []
        
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            return relationships
        
        biography_section = None
        for header in content.find_all(['h2', 'h3']):
            header_text = header.get_text(strip=True).lower()
            if 'biography' in header_text or 'background' in header_text:
                biography_section = []
                for sibling in header.find_next_siblings():
                    if sibling.name in ['h2', 'h3']:
                        break
                    biography_section.append(sibling)
                break
        
        if biography_section:
            for elem in biography_section:
                for link in elem.find_all('a', href=True):
                    href = link['href']
                    
                    if (href.startswith('/wiki/') and 
                        ':' not in href and 
                        'action=edit' not in href and
                        not href.startswith('http')):
                        
                        if '#' in href:
                            href = href.split('#')[0]
                        if '?' in href:
                            href = href.split('?')[0]
                        
                        linked_page = self.normalize_page_title(href)
                        text = elem.get_text()
                        
                        relationships.append({
                            'target': linked_page,
                            'types': ['associated_with'],  # Default for bio mentions
                            'source_text': text[:200]
                        })
        
        return relationships
    
    def extract_organization_affiliations(self, soup, current_page):
        """Extract organization affiliations from the page."""
        affiliations = []
        
        org_keywords = [
            'House', 'Creed', 'Guard', 'Council', 'Order', 'Sisters',
            'Revolutionary', 'Sundered', 'Candescent', 'Sylandri'
        ]
        
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            return affiliations
        
        paragraphs = content.find_all('p', limit=10)
        
        for para in paragraphs:
            text = para.get_text().lower()
            
            if any(keyword.lower() in text for keyword in org_keywords):
                for link in para.find_all('a', href=True):
                    href = link['href']
                    
                    if (href.startswith('/wiki/') and ':' not in href):
                        if '#' in href:
                            href = href.split('#')[0]
                        if '?' in href:
                            href = href.split('?')[0]
                        
                        linked_page = self.normalize_page_title(href)
                        link_text = link.get_text()
                        
                        if any(keyword.lower() in link_text.lower() for keyword in org_keywords):
                            rel_type = 'member_of'
                            if 'aspirant' in text:
                                rel_type = 'aspirant_of'
                            elif 'founded' in text or 'created' in text:
                                rel_type = 'founded'
                            elif 'serves' in text or 'marshal' in text:
                                rel_type = 'serves_in'
                            
                            affiliations.append({
                                'target': linked_page,
                                'types': [rel_type],
                                'context': text[:150]
                            })
        
        return affiliations

    def determine_entity_type(self, page_title, data, categories):
        """Determine what type of entity this is."""
        if page_title in self.main_characters:
            return 'Main Character'
        
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
        
        if 'Type' in data:
            type_val = data['Type'].lower()
            if 'city' in type_val or 'town' in type_val or 'region' in type_val:
                return 'Location'
            elif 'organization' in type_val or 'faction' in type_val:
                return 'Organization'
        
        if any(word in page_title.lower() for word in ['house', 'council', 'guard', 'creed', 'rebellion']):
            return 'Organization'
        
        if any(key in data for key in ['Race', 'Class', 'Actor', 'Portrayed by', 'Pronouns']):
            return 'NPC'
        
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
        """Add nodes for race, class, and player actor as separate entities."""
        character_name = entity_data.get('name', character_page.replace('_', ' '))
        
        if 'Race' in entity_data:
            race = self.clean_display_text(entity_data['Race'])
            race_id = f"race_{race.replace(' ', '_').replace('(', '').replace(')', '')}"
            
            if race_id not in self.graph:
                self.graph.add_node(
                    race_id,
                    label=race,
                    title=f"<b>Race: {race}</b>",
                    color='#00CED1',
                    size=15,
                    shape='box'
                )
            
            self.graph.add_edge(character_page, race_id, title='Race', color='#16A085', width=2)
        
        if 'Class' in entity_data:
            classes = self.clean_display_text(entity_data['Class'])
            for class_name in classes.split('/'):
                class_name = class_name.strip()
                class_id = f"class_{class_name.replace(' ', '_').replace('(', '').replace(')', '')}"
                
                if class_id not in self.graph:
                    self.graph.add_node(
                        class_id,
                        label=class_name,
                        title=f"<b>Class: {class_name}</b>",
                        color='#9370DB',
                        size=15,
                        shape='box'
                    )
                
                self.graph.add_edge(character_page, class_id, title='Class', color='#8E44AD', width=2)
        
        if 'Actor' in entity_data:
            actor_name = entity_data['Actor']
            actor_page_title = actor_name.replace(' ', '_')

            if actor_page_title not in self.graph:
                print(f"    Found player: {actor_name}. Fetching page for portrait.")
                actor_soup, canonical_name = self.fetch_page(actor_page_title)
                
                actor_data = {}
                if actor_soup:
                    actor_data = self.extract_infobox_data(actor_soup)
                
                display_name = actor_data.get('name', actor_name)
                image_url = actor_data.get('image_url')

                node_config = {
                    'label': display_name,
                    'title': f"<b>Player: {display_name}</b><br><i>Click to open wiki page</i>",
                    'color': '#FF1493',
                    'size': 20,
                    'url': f"{self.base_url}/wiki/{canonical_name or actor_page_title}"
                }

                if image_url:
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    
                    node_config.update({
                        'shape': 'circularImage',
                        'image': image_url,
                        'size': 40,
                        'borderWidth': 3,
                        'borderWidthSelected': 5,
                        'color': {
                            'border': '#FF1493', 'background': '#FF1493',
                            'highlight': {'border': '#FF1493', 'background': '#FF1493'}
                        },
                        'title': f'<b>Player: {display_name}</b><br><img src="{image_url}" width="200" /><br><i>Click to open wiki page</i>'
                    })
                else:
                    node_config['shape'] = 'dot'

                self.graph.add_node(actor_page_title, **node_config)
                
                if actor_page_title not in self.entities:
                    self.entities[actor_page_title] = {
                        'name': display_name,
                        'type': 'Cast Member',
                        'data': actor_data
                    }

            self.graph.add_edge(
                actor_page_title,
                character_page,
                title='Plays',
                color='#FF1493',
                width=2
            )
    
    def add_entity(self, page_title, entity_data, entity_type):
        """Add an entity to the graph."""
        display_name = entity_data.get('name', page_title.replace('_', ' '))
        display_name = self.clean_display_text(display_name)
        
        self.entities[page_title] = {
            'name': display_name,
            'type': entity_type,
            'data': entity_data
        }
        
        color_map = {
            'Main Character': '#FF0000',
            'Player Character': '#FF0000',
            'NPC': '#00BFFF',
            'Location': '#00FF00',
            'Organization': '#FFD700',
            'Cast Member': '#9370DB',
            'Event': '#FF1493',
            'Unknown': '#999999'
        }
        
        size_map = {
            'Main Character': 30,
            'Player Character': 25,
            'NPC': 20,
            'Organization': 25,
            'Location': 20,
            'Event': 20,
            'Unknown': 15
        }
        
        title_parts = [f"<b>{display_name}</b>", f"Type: {entity_type}"]
        if 'Actor' in entity_data:
            title_parts.append(f"Played by: {entity_data['Actor']}")
        if 'Race' in entity_data:
            cleaned_race = self.clean_display_text(entity_data['Race'])
            title_parts.append(f"Race: {cleaned_race}")
        if 'Class' in entity_data:
            cleaned_class = self.clean_display_text(entity_data['Class'])
            title_parts.append(f"Class: {cleaned_class}")
        
        image_url = entity_data.get('image_url')
        if image_url:
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            title_parts.append(f'<img src="{image_url}" width="200" />')
        
        title_parts.append("<br><i>Click to open wiki page</i>")
        
        node_config = {
            'label': display_name,
            'title': '<br>'.join(title_parts),
            'color': color_map.get(entity_type, '#95A5A6'),
            'size': size_map.get(entity_type, 15),
            'url': f"{self.base_url}/wiki/{page_title}"
        }
        
        if image_url:
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            
            if entity_type in ['Main Character', 'Player Character']:
                node_size = 80
                border_width = 4
                border_width_selected = 6
                border_color = '#FF0000'
            elif entity_type == 'NPC':
                node_size = 40
                border_width = 3
                border_width_selected = 5
                border_color = '#00BFFF'
            else:
                node_size = 40
                border_width = 3
                border_width_selected = 5
                border_color = color_map.get(entity_type, '#95A5A6')
            
            node_config['shape'] = 'circularImage'
            node_config['image'] = image_url
            node_config['size'] = node_size
            node_config['borderWidth'] = border_width
            node_config['borderWidthSelected'] = border_width_selected
            node_config['color'] = {
                'border': border_color,
                'background': border_color,
                'highlight': {
                    'border': border_color,
                    'background': border_color
                }
            }
        
        self.graph.add_node(page_title, **node_config)
        
        if entity_type in ['Main Character', 'Player Character']:
            self.add_metadata_nodes(page_title, entity_data)    
    
    def get_strongest_relationship(self, rel_types):
        """Determines the single strongest relationship type from a list of raw types."""
        new_types = {self.RELATIONSHIP_MAP.get(t, 'Associated With') for t in rel_types}
        for rel in self.PRECEDENCE:
            if rel in new_types:
                return rel
        return 'Associated With'

    def add_relationship(self, source_page, target_page, rel_types=['associated_with']):
        """Add a single, prioritized edge between entities based on the strongest relationship."""
        if target_page not in self.entities:
            return
        
        strongest_rel = self.get_strongest_relationship(rel_types)
        style = self.RELATIONSHIP_STYLES.get(strongest_rel)

        if not style:
            return

        # Add or update the edge with the strongest relationship found
        self.graph.add_edge(
            source_page,
            target_page,
            title=style['label'],
            label=style['label'],
            color=style['color'],
            width=style['width']
        )
        
        # Track in relationships list for data export
        self.relationships.append({
            'source': source_page,
            'target': target_page,
            'type': strongest_rel,
            'original_types': list(set(rel_types))
        })
    
    def process_page(self, page_title):
        """Process a single wiki page, handling redirects."""
        page_title = self.normalize_page_title(page_title)
        
        if page_title in self.alias_map:
            canonical_name = self.alias_map[page_title]
            if canonical_name in self.entities:
                print(f"    Already processed (via alias): {canonical_name}")
                return []
        
        soup, canonical_name = self.fetch_page(page_title)
        
        if not canonical_name:
            return []

        if canonical_name in self.entities:
            print(f"    Already processed: {canonical_name}")
            return []

        infobox_data = self.extract_infobox_data(soup)
        categories = self.extract_categories(soup)
        entity_type = self.determine_entity_type(canonical_name, infobox_data, categories)
        
        # Get display name for LLM context
        display_name = infobox_data.get('name', canonical_name.replace('_', ' '))
        
        self.add_entity(canonical_name, infobox_data, entity_type)

        # Extract relationships with LLM classification
        print(f"    Extracting relationships...")
        org_affiliations = self.extract_organization_affiliations(soup, canonical_name)
        relationships = self.extract_relationships_section(soup, display_name)
        bio_relationships = self.extract_biography_relationships(soup, canonical_name)
        
        all_relationships = org_affiliations + relationships + bio_relationships
        return all_relationships
    
    def build_graph(self):
        """Build the complete Campaign 4 graph."""
        print("Building Campaign Four Knowledge Graph with LLM Classification")
        print("=" * 60)
        print(f"Using Ollama model: {self.ollama_model}")
        print(f"Ollama URL: {self.ollama_url}")
        print("=" * 60)
        
        # Test Ollama connection
        try:
            test_response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if test_response.status_code == 200:
                print("✓ Ollama connection successful")
            else:
                print("⚠ Warning: Ollama may not be running properly")
        except Exception as e:
            print(f"⚠ Warning: Could not connect to Ollama: {e}")
            print("  Relationships will use fallback classification")
        
        print("\n[Phase 1] Processing entities and collecting relationships...")
        all_relationships = {}
        queue = list(self.main_characters)
        processed = set()
        
        limit = 200
        count = 0

        while queue and count < limit:
            page_title = queue.pop(0)
            normalized = self.normalize_page_title(page_title)
            canonical = self.get_canonical_name(normalized)
            
            if canonical in processed:
                continue
            
            count += 1
            print(f"\n→ Processing {normalized} ({count}/{limit})")

            relationships = self.process_page(normalized)
            
            canonical = self.get_canonical_name(normalized)
            if canonical:
                processed.add(canonical)
                all_relationships[canonical] = relationships
                
                for rel in relationships:
                    target = self.normalize_page_title(rel['target'])
                    if '#' in target:
                        target = target.split('#')[0]
                    
                    target_canonical = self.get_canonical_name(target)
                    
                    if target_canonical not in processed and target not in queue:
                        queue.append(target)

        print("\n[Phase 2] Resolving canonical names for all relationships...")
        unresolved_targets = set()
        
        for source_canonical, relationships in all_relationships.items():
            for rel in relationships:
                target = self.normalize_page_title(rel['target'])
                target_canonical = self.get_canonical_name(target)
                
                if target_canonical not in self.entities:
                    clean_target = target.split('#')[0] if '#' in target else target
                    unresolved_targets.add(clean_target)
        
        print(f"  Found {len(unresolved_targets)} unresolved targets")
        
        for target in unresolved_targets:
            if self.get_canonical_name(target) not in self.entities:
                soup, canonical = self.fetch_page(target)
        
        print("\n[Phase 3] Aggregating and adding relationships to graph...")
        final_rels = defaultdict(list)
        for source_canonical, relationships in all_relationships.items():
            for rel in relationships:
                target = self.normalize_page_title(rel['target'])
                target_canonical = self.get_canonical_name(target)
                
                if source_canonical in self.entities and target_canonical in self.entities:
                    rel_types = rel.get('types', ['associated_with'])
                    final_rels[(source_canonical, target_canonical)].extend(rel_types)

        for (source, target), all_types in final_rels.items():
            self.add_relationship(source, target, all_types)
        
        print("\n✓ Graph building complete!")
        print(f"  LLM cache size: {len(self.llm_cache)} classifications")
    
    def visualize(self, output_file='campaign4_graph.html'):
        """Create an interactive visualization with legend."""
        net = Network(
            height='900px', 
            width='100%', 
            bgcolor='#1a1a1a', 
            font_color='white',
            directed=True
        )
        
        net.barnes_hut(
            gravity=-15000,
            central_gravity=0.5,
            spring_length=150,
            spring_strength=0.01,
            damping=0.09
        )
        
        net.from_nx(self.graph)
        net.show_buttons(filter_=['physics'])
        net.save_graph(output_file)
        
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
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
        max-width: 250px;
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
    #legend-section {
        margin-bottom: 15px;
    }
    #legend-section h4 {
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
            
            legend_html = '''
    <div id="legend">
        <h3>📊 Legend</h3>
        
        <div id="legend-section">
            <h4>Node Types</h4>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FF0000;"></div>
                <span>Main/Player Character</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #00BFFF;"></div>
                <span>NPC</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FFD700;"></div>
                <span>Organization</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #00FF00;"></div>
                <span>Location</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FF1493;"></div>
                <span>Player/Actor</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #00CED1;"></div>
                <span>Race</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #9370DB;"></div>
                <span>Class</span>
            </div>
        </div>
        
        <div id="legend-section">
            <h4>Relationships</h4>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #FF0000;"></div>
                <span>Enemy</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #00BFFF;"></div>
                <span>Family</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #FF1493;"></div>
                <span>Romantic Partner</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #00FF00;"></div>
                <span>Ally</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #8A2BE2;"></div>
                <span>Complicated</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #FFD700;"></div>
                <span>Member Of</span>
            </div>
            <div class="legend-item">
                <div class="legend-line" style="background-color: #999999;"></div>
                <span>Associated With</span>
            </div>
        </div>
        
        <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #555; font-size: 11px; color: #aaa;">
            💡 Click nodes to open wiki<br>
            💡 Drag to move, scroll to zoom<br>
            💡 LLM-classified relationships
        </div>
    </div>

    <button id="legend-toggle">Show Legend</button>
    '''
            
            if '<body>' in html_content:
                html_content = html_content.replace('<body>', '<body>\n' + legend_html, 1)
            elif '<div id="mynetwork">' in html_content:
                html_content = html_content.replace('<div id="mynetwork">', legend_html + '\n<div id="mynetwork">', 1)
            else:
                html_content = html_content.replace('</body>', legend_html + '\n</body>', 1)
            
            js_additions = '''
    <script type="text/javascript">
    window.addEventListener('load', function() {
        setTimeout(function() {
            if (typeof network !== 'undefined' && typeof nodes !== 'undefined') {
                var canvas = document.querySelector('#mynetwork canvas');
                var legend = document.getElementById('legend');
                var legendToggle = document.getElementById('legend-toggle');
                
                var legendVisible = true;
                
                legendToggle.addEventListener('click', function() {
                    legendVisible = !legendVisible;
                    if (legendVisible) {
                        legend.style.display = 'block';
                        legendToggle.style.display = 'none';
                    } else {
                        legend.style.display = 'none';
                        legendToggle.style.display = 'block';
                        legendToggle.textContent = 'Show Legend';
                    }
                });
                
                var closeBtn = document.createElement('span');
                closeBtn.innerHTML = '✕';
                closeBtn.style.cssText = 'position: absolute; top: 10px; right: 10px; cursor: pointer; font-size: 18px; color: #aaa;';
                closeBtn.onclick = function() {
                    legend.style.display = 'none';
                    legendToggle.style.display = 'block';
                };
                legend.insertBefore(closeBtn, legend.firstChild);
                
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
                    if (canvas) {
                        canvas.style.cursor = 'pointer';
                    }
                });
                
                network.on("blurNode", function(params) {
                    if (canvas) {
                        canvas.style.cursor = 'default';
                    }
                });
                
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
        
        print(f"\n{'=' * 50}")
        print("Graph Statistics:")
        print(f"  Total Nodes: {self.graph.number_of_nodes()}")
        print(f"  Total Edges: {self.graph.number_of_edges()}")
        print(f"  Main Characters: {sum(1 for n, d in self.graph.nodes(data=True) if d.get('size', 0) >= 25)}")
        print(f"  Organizations: {len([n for n, d in self.entities.items() if d['type'] == 'Organization'])}")
        print(f"  NPCs: {len([n for n, d in self.entities.items() if d['type'] == 'NPC'])}")
        print(f"\n✓ Graph saved to {output_file}")
        print(f"  Open this file in your browser to explore!")
        print(f"  💡 Relationships classified using {self.ollama_model}")        

    def save_data(self, output_file='campaign4_data.json'):
        """Save entity and relationship data."""
        data = {
            'entities': self.entities,
            'relationships': self.relationships,
            'llm_cache_size': len(self.llm_cache)
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Data saved to {output_file}")
    
    def print_summary(self):
        """Print a summary of key findings."""
        print(f"\n{'=' * 50}")
        print("Campaign Four Summary:")
        print(f"{'=' * 50}")
        
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
        
        orgs = [name for name, data in self.entities.items() if data['type'] == 'Organization']
        if orgs:
            print(f"\nOrganizations ({len(orgs)}):")
            for org in orgs[:15]:
                print(f"  • {self.entities[org]['name']}")
        
        npcs = [name for name, data in self.entities.items() if data['type'] == 'NPC']
        if npcs:
            print(f"\nNPCs ({len(npcs)}):")
            for npc in npcs[:15]:
                print(f"  • {self.entities[npc]['name']}")
        
        rel_types = {}
        for rel in self.relationships:
            rel_types[rel['type']] = rel_types.get(rel['type'], 0) + 1
        
        if rel_types:
            print(f"\nRelationship Types (LLM-classified):")
            for rel_type, count in sorted(rel_types.items(), key=lambda x: x[1], reverse=True)[:15]:
                print(f"  • {rel_type.replace('_', ' ').title()}: {count}")


def main():
    # Initialize with your Ollama settings
    builder = CampaignFourGraphBuilder(
        ollama_model="llama3.1:8b",
        ollama_url="http://localhost:11434"
    )
    
    # Build the complete graph
    builder.build_graph()
    
    # Create visualization
    builder.visualize('docs/index.html')
    
    # Save data
    builder.save_data('campaign4_data.json')
    
    # Print summary
    builder.print_summary()


if __name__ == "__main__":
    main()