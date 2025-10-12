"""
Critical Role Campaign 4 Episode Graph Builder
Extracts a summary of a single episode from its wiki page, including characters,
locations, events, and plot points, and builds a knowledge graph.
Uses a local Ollama LLM to analyze the episode synopsis.

Required installations:
pip install requests beautifulsoup4 networkx pyvis

Requires Ollama running locally with a model like llama3.1:8b

Usage:
python episode_graph.py
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

class EpisodeGraphBuilder:
    def __init__(self, ollama_model="llama3.1:8b", ollama_url="http://localhost:11434"):
        self.base_url = "https://criticalrole.fandom.com"
        self.graph = nx.DiGraph()
        self.entities = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.alias_map = {}
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self.llm_cache = {}
        # A list of main characters to help identify them
        self.main_characters = [
            'Thimble', 'Azune_Nayar', 'Kattigan_Vale', 'Thaisha_Lloy', 'Bolaire_Lathalia',
            'Vaelus', 'Julien_Davinos', 'Tyranny', 'Halandil_Fang', "Murray_Mag'Nesson",
            'Wicander_Halovar', 'Occtis_Tachonis', 'Teor_Pridesire'
        ]

    def clean_display_text(self, text):
        """Remove wiki reference brackets [1], [2], etc. from display text."""
        cleaned = re.sub(r'\[\d+\]', '', text)
        cleaned = re.sub(r'\[citation needed\]', '', cleaned)
        cleaned = re.sub(r'\[presumed.*?\].*?', '', cleaned, flags=re.IGNORECASE)
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
        
        title_elem = infobox.find('h2', class_='pi-title')
        if title_elem:
            data['name'] = title_elem.get_text(strip=True)
        
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
    

    def extract_episode_data_with_llm(self, soup):
        """Use LLM to extract a structured summary of an episode from its wiki page."""
        print("  Extracting synopsis for LLM analysis...")
        content = soup.find('div', class_='mw-parser-output')
        if not content:
            print("  ⚠ Could not find page content.")
            return None

        synopsis_text = []
        synopsis_header = content.find('span', id='Synopsis')
        if not synopsis_header:
            synopsis_header = content.find('span', id='Summary')
            if not synopsis_header:
                print("  ⚠ Could not find 'Synopsis' or 'Summary' section.")
                return None
        
        for element in synopsis_header.parent.find_next_siblings():
            if element.name == 'h2':
                break
            if element.name in ['p', 'h3', 'ul', 'li']:
                synopsis_text.append(element.get_text(strip=True))
        
        full_synopsis = "\n".join(synopsis_text)
        
        if not full_synopsis:
            print("  ⚠ Synopsis section was empty.")
            return None

        print(f"  Synopsis found ({len(full_synopsis)} characters). Sending to LLM...")

        cache_key = f"episode_summary:{self.normalize_page_title(soup.title.string)}:{full_synopsis[:200]}"
        if cache_key in self.llm_cache:
            print("  ✓ Found cached LLM response.")
            return self.llm_cache[cache_key]

        prompt = f"""
Analyze the following episode summary from a Critical Role wiki page. Your task is to act as a story analyst and extract the key information into a structured JSON object.

**Episode Summary:**
---
{full_synopsis[:8000]}
---

**Instructions:**
1.  Identify all characters (player characters and NPCs) who were present or significantly mentioned by their full name.
2.  Identify all distinct locations that were visited or were central to the events.
3.  Summarize the 3-5 most important, distinct events that occurred. An event is a specific action or scene. For each event, list the main participants by name.
4.  Distill the 2-4 most critical plot points revealed. A plot point is a new piece of information or a revelation that drives the story forward.

**Output Format:**
Provide your analysis *only* in a valid JSON object, with no other text before or after it. Use the following structure:

{{
  "characters_present": ["<Character Name>", "<NPC Name>", ...],
  "locations_visited": ["<Location Name>", ...],
  "key_events": [
    {{
      "event": "<Concise name for the event>",
      "summary": "<A one-sentence summary of the event.>",
      "participants": ["<Character Name>", ...]
    }},
    ...
  ],
  "plot_points_revealed": [
    "<Plot point summary sentence>",
    ...
  ]
}}

JSON_OUTPUT:
"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": { "temperature": 0.2 }
                },
                timeout=180  # Longer timeout for potentially long analysis
            )
            
            if response.status_code == 200:
                result_text = response.json().get('response', '').strip()
                
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if not json_match:
                    print("  ⚠ LLM did not return a valid JSON object.")
                    print(f"    LLM Raw Response: {result_text}")
                    return None
                
                json_str = json_match.group(0)
                
                try:
                    data = json.loads(json_str)
                    self.llm_cache[cache_key] = data
                    print("  ✓ LLM analysis complete.")
                    print("\n-- LLM Episode Summary --")
                    print(json.dumps(data, indent=2))
                    print("-------------------------")
                    # Find the synopsis section again to return its soup object
                    synopsis_header = soup.find('span', id='Synopsis') or soup.find('span', id='Summary')
                    synopsis_soup = BeautifulSoup('<div></div>', 'html.parser').new_tag('div')
                    for element in synopsis_header.parent.find_next_siblings():
                        if element.name == 'h2':
                            break
                        synopsis_soup.append(element)
                    return data, synopsis_soup
                except json.JSONDecodeError as e:
                    print(f"  ⚠ LLM returned invalid JSON: {e}")
                    print(f"    LLM JSON Response: {json_str}")
                    return None
            else:
                print(f"  ⚠ LLM request failed: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"  ⚠ LLM request timed out")
            return None
        except Exception as e:
            print(f"  ⚠ LLM error: {e}")
            return None

    def process_character_node(self, character_name):
        """Fetches and adds a character node, including portrait if available."""
        char_page_title = self.normalize_page_title(character_name)
        if char_page_title in self.entities:
            return # Already processed

        print(f"  Processing entity: {character_name}")
        soup, canonical_name = self.fetch_page(char_page_title)
        if not soup:
            self.add_simple_node(character_name, 'Unknown Character')
            return

        infobox_data = self.extract_infobox_data(soup)
        categories = self.extract_categories(soup)
        entity_type = self.determine_entity_type(canonical_name, infobox_data, categories)
        
        self.add_entity(canonical_name, infobox_data, entity_type)

    def add_simple_node(self, name, node_type, node_id=None, summary=None):
        """Adds a basic node for non-character entities like locations, events, etc."""
        if not node_id:
            node_id = self.normalize_page_title(name)

        if node_id in self.entities:
            return

        print(f"  Adding node: {name} ({node_type})")
        self.entities[node_id] = {'name': name, 'type': node_type, 'data': {}}

        color_map = {
            'Location': '#2ECC71', # Emerald
            'Event': '#E74C3C', # Alizarin
            'Plot Point': '#F1C40F', # Sunflower
            'Unknown Character': '#95A5A6' # Concrete
        }
        shape_map = {
            'Location': 'database',
            'Event': 'diamond',
            'Plot Point': 'box',
            'Unknown Character': 'dot'
        }
        title = f"<b>{name}</b><br>Type: {node_type}"
        if summary:
            # Simple text wrapping for long summaries
            wrapped_summary = '\n'.join(summary[i:i+80] for i in range(0, len(summary), 80))
            title += f"<br><br><i>{wrapped_summary}</i>"

        self.graph.add_node(
            node_id,
            label=name.replace(f'Plot: ', ''),
            title=title,
            color=color_map.get(node_type, '#95A5A6'),
            shape=shape_map.get(node_type, 'dot'),
            size=20
        )

    def build_graph_for_episode(self, episode_url):
        """Builds a graph by analyzing a single episode page."""
        print(f"Building Episode Graph for: {episode_url}")
        print("=" * 60)

        episode_page_title = episode_url.split('/wiki/')[-1]
        soup, canonical_name = self.fetch_page(episode_page_title)

        if not soup:
            print("Could not fetch episode page. Aborting.")
            return

        episode_data, synopsis_soup = self.extract_episode_data_with_llm(soup)

        if not episode_data:
            print("Could not extract data from episode page. Aborting.")
            return

        episode_display_name = canonical_name.replace('_', ' ')
        self.graph.add_node(
            canonical_name,
            label=episode_display_name,
            title=f"<b>Episode: {episode_display_name}</b>",
            color='#3498DB',
            size=40,
            shape='star',
            url=f"{self.base_url}/wiki/{canonical_name}"
        )
        self.entities[canonical_name] = {'name': episode_display_name, 'type': 'Episode', 'data': {}}

        print("\n[Phase 1] Resolving and processing discovered entities...")
        
        resolved_char_map = {}
        for char_name_from_llm in episode_data.get('characters_present', []):
            link = synopsis_soup.find('a', string=re.compile(r'\s*' + re.escape(char_name_from_llm) + r'\s*'))
            
            page_title = None
            if link and link.get('href'):
                page_title = self.normalize_page_title(link['href'])
                print(f"  ✓ Resolved '{char_name_from_llm}' to page '{page_title}' via link.")
            else:
                page_title = self.normalize_page_title(char_name_from_llm)
                print(f"  ⚠ Could not resolve link for '{char_name_from_llm}', using name directly.")
            
            if page_title:
                resolved_char_map[char_name_from_llm] = page_title
                self.process_character_node(page_title)

        for loc_name in episode_data.get('locations_visited', []):
            self.add_simple_node(loc_name, 'Location')

        for i, event in enumerate(episode_data.get('key_events', [])):
            event_id = f"event_{canonical_name}_{i}"
            self.add_simple_node(event['event'], 'Event', node_id=event_id, summary=event['summary'])

        for i, plot_point in enumerate(episode_data.get('plot_points_revealed', [])):
            plot_point_id = f"plot_{canonical_name}_{i}"
            label = f"Plot: {plot_point[:50]}..." if len(plot_point) > 50 else f"Plot: {plot_point}"
            self.add_simple_node(label, 'Plot Point', node_id=plot_point_id, summary=plot_point)

        print("\n[Phase 2] Connecting graph nodes...")
        for page_title in resolved_char_map.values():
            if page_title in self.entities:
                self.graph.add_edge(page_title, canonical_name, title='Appeared In', color='#BDC3C7', width=2)
        
        for loc_name in episode_data.get('locations_visited', []):
            loc_id = self.normalize_page_title(loc_name)
            self.graph.add_edge(loc_id, canonical_name, title='Featured In', color='#BDC3C7', width=2)

        for i, event in enumerate(episode_data.get('key_events', [])):
            event_id = f"event_{canonical_name}_{i}"
            self.graph.add_edge(event_id, canonical_name, title='Part Of', color='#E74C3C', width=3)
            for participant_name_from_llm in event.get('participants', []):
                resolved_participant_title = resolved_char_map.get(participant_name_from_llm)
                if resolved_participant_title and resolved_participant_title in self.entities:
                    self.graph.add_edge(resolved_participant_title, event_id, title='Participated In', color='#2ECC71', width=2.5)
                else:
                    print(f"  ! Could not connect unresolved participant '{participant_name_from_llm}' to event '{event['event']}'.")

        for i, plot_point in enumerate(episode_data.get('plot_points_revealed', [])):
            plot_point_id = f"plot_{canonical_name}_{i}"
            self.graph.add_edge(plot_point_id, canonical_name, title='Revealed In', color='#F1C40F', width=3)

        print("\n✓ Graph building complete!")
    
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
    
    def determine_entity_type(self, page_title, data, categories):
        """Determine what type of entity this is."""
        # Check if it's a known main character
        if page_title in self.main_characters:
            return 'Player Character'
        
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
        
        # Fallback based on infobox data
        if any(key in data for key in ['Race', 'Class', 'Actor', 'Portrayed by']):
            # Check if it has an Actor link, making it a PC
            if 'Actor' in data or 'Portrayed by' in data:
                return 'Player Character'
            return 'NPC'
        
        return 'Unknown'

    def add_entity(self, page_title, entity_data, entity_type):
        """Add an entity to the graph."""
        display_name = entity_data.get('name', page_title.replace('_', ' '))
        display_name = self.clean_display_text(display_name)
        
        if page_title in self.entities:
            return

        self.entities[page_title] = {
            'name': display_name,
            'type': entity_type,
            'data': entity_data
        }
        
        color_map = {
            'Player Character': '#FF0000',
            'NPC': '#00BFFF',
            'Cast Member': '#9370DB',
            'Unknown': '#999999'
        }
        
        size_map = {
            'Player Character': 30,
            'NPC': 20,
            'Cast Member': 25,
            'Unknown': 15
        }
        
        title_parts = [f"<b>{display_name}</b>", f"Type: {entity_type}"]
        if 'Actor' in entity_data:
            title_parts.append(f"Played by: {entity_data['Actor']}")
        if 'Race' in entity_data:
            title_parts.append(f"Race: {self.clean_display_text(entity_data['Race'])}")
        if 'Class' in entity_data:
            title_parts.append(f"Class: {self.clean_display_text(entity_data['Class'])}")
        
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
            if entity_type == 'Player Character':
                node_config.update({
                    'shape': 'circularImage', 'image': image_url, 'size': 40,
                    'borderWidth': 4, 'borderWidthSelected': 6,
                    'color': {'border': '#FF0000', 'background': '#FF0000'}
                })
            elif entity_type == 'NPC':
                node_config.update({
                    'shape': 'circularImage', 'image': image_url, 'size': 30,
                    'borderWidth': 3, 'borderWidthSelected': 5,
                    'color': {'border': '#00BFFF', 'background': '#00BFFF'}
                })
            elif entity_type == 'Cast Member':
                 node_config.update({
                    'shape': 'circularImage', 'image': image_url, 'size': 35,
                    'borderWidth': 3, 'borderWidthSelected': 5,
                    'color': {'border': '#9370DB', 'background': '#9370DB'}
                })

        self.graph.add_node(page_title, **node_config)
        
        if entity_type == 'Player Character':
            self.add_metadata_nodes(page_title, entity_data)
    
    def visualize(self, output_file='episode_graph.html'):
        """Create an interactive visualization with legend."""
        net = Network(
            height='900px', 
            width='100%', 
            bgcolor='#1a1a1a', 
            font_color='white',
            directed=True
        )
        
        net.barnes_hut(
            gravity=-20000,
            central_gravity=0.4,
            spring_length=200,
            spring_strength=0.02,
            damping=0.09
        )
        
        net.from_nx(self.graph)
        net.show_buttons(filter_=['physics'])
        net.save_graph(output_file)
        
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            css_additions = """
    <style>
    body { margin: 0; padding: 0; overflow: hidden; }
    #mynetwork { width: 100vw; height: 100vh; }
    #legend { position: absolute; top: 20px; right: 20px; background-color: rgba(26, 26, 26, 0.95); border: 2px solid #444; border-radius: 8px; padding: 15px; color: white; font-family: Arial, sans-serif; font-size: 13px; max-width: 250px; z-index: 1000; }
    #legend h3 { margin: 0 0 10px 0; font-size: 16px; border-bottom: 1px solid #555; padding-bottom: 8px; }
    .legend-item { display: flex; align-items: center; margin: 5px 0; font-size: 12px; }
    .legend-shape { width: 20px; height: 20px; margin-right: 8px; flex-shrink: 0; text-align: center; line-height: 20px; font-size: 16px; }
    </style>
    """
            html_content = html_content.replace('</head>', css_additions + '</head>')
            
            legend_html = """
    <div id="legend">
        <h3>📊 Episode Legend</h3>
        <div class="legend-item">
            <div class="legend-shape" style="color: #3498DB;">★</div>
            <span>Episode</span>
        </div>
        <div class="legend-item">
            <div class="legend-shape" style="color: #FF0000;">●</div>
            <span>Player Character</span>
        </div>
        <div class="legend-item">
            <div class="legend-shape" style="color: #00BFFF;">●</div>
            <span>NPC</span>
        </div>
        <div class="legend-item">
            <div class="legend-shape" style="color: #9370DB;">●</div>
            <span>Cast Member</span>
        </div>
        <div class="legend-item">
            <div class="legend-shape" style="color: #2ECC71;">⛁</div>
            <span>Location</span>
        </div>
        <div class="legend-item">
            <div class="legend-shape" style="color: #E74C3C;">◆</div>
            <span>Key Event</span>
        </div>
        <div class="legend-item">
            <div class="legend-shape" style="color: #F1C40F;">■</div>
            <span>Plot Point</span>
        </div>
    </div>
    """
            
            if '<body>' in html_content:
                html_content = html_content.replace('<body>', '<body>\n' + legend_html, 1)
            else:
                html_content = html_content.replace('</body>', legend_html + '\n</body>', 1)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
                        
        except Exception as e:
            print(f"  ⚠ Error modifying HTML: {e}")
        
        print(f"\n{'=' * 50}")
        print("Graph Statistics:")
        print(f"  Total Nodes: {self.graph.number_of_nodes()}")
        print(f"  Total Edges: {self.graph.number_of_edges()}")
        print(f"\n✓ Graph saved to {output_file}")
        print(f"  Open this file in your browser to explore!")
    
def main():
    builder = EpisodeGraphBuilder(
        ollama_model="llama3.1:8b",
        ollama_url="http://localhost:11434"
    )
    
    # The episode to analyze
    episode_url = "https://criticalrole.fandom.com/wiki/The_Fall_of_Thjazi_Fang"
    
    builder.build_graph_for_episode(episode_url)
    
    # Create a unique filename for the output
    page_title_for_filename = episode_url.split('/wiki/')[-1]
    output_filename = f"docs/{builder.normalize_page_title(page_title_for_filename)}_graph.html"
    builder.visualize(output_filename)
    
if __name__ == "__main__":
    main()