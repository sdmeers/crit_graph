#!/usr/bin/env python3
"""
Critical Role Episode Graph Visualizer
Loads a JSON file containing episode data and creates an interactive visualization
with character portraits fetched from the Critical Role wiki.

Required installations:
pip install requests beautifulsoup4 networkx pyvis

Usage:
python CR_episode_graph.py <json_file> <output_html_file> [--campaign CAMPAIGN]
"""

import requests
from bs4 import BeautifulSoup
import networkx as nx
from pyvis.network import Network
import time
import sys
import os
import urllib.parse
import re
import argparse
import json

class EpisodeGraphVisualizer:
    def __init__(self, json_file, target_campaign=4):
        self.json_file = json_file
        self.base_url = "https://criticalrole.fandom.com"
        self.target_campaign = target_campaign
        self.graph = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.image_cache = {}
        self.validation_cache = {}
        
        # Manual overrides for known edge cases
        self.manual_overrides = {
            "Shadia Fang": "Shadia",
            "Alogar Lloy": "Alogar",
            # Campaign 4 Player Characters
            "Bolaire Lloy": "Bolaire Lathalia",
            "Sir Julien Davinos": "Julien Davinos",
            "Halandil Fang": "Halandil Fang",
            "Hal": "Halandil Fang",
            # Known factions/institutions
            "Torn Banner (Artifact)": "Torn Banner",
            "Penteveral": "Penteveral"
        }
        
        # Common titles to strip when searching
        self.honorifics = [
            'sir', 'lady', 'lord', 'king', 'queen', 'prince', 'princess',
            'duke', 'duchess', 'baron', 'baroness', 'count', 'countess',
            'master', 'mistress', 'captain', 'general', 'admiral'
        ]
        
        # Episode title patterns to avoid
        self.episode_patterns = [
            r'^The\s+\w+\s+of\s+',
            r'^A\s+\w+\s+of\s+',
            r'^\w+\s+\d+x\d+',
        ]
        
        # Color schemes for different node types
        self.type_colors = {
            'event': '#FF6B6B',
            'character': '#4ECDC4',
            'location': '#95E1D3',
            'object': '#F38181',
            'artifact': '#F38181',
            'faction': '#AA96DA',
            'organization': '#AA96DA',
            'historical_event': '#FCBAD3',
            'mystery': '#A8D8EA'
        }
        
        self.type_sizes = {
            'event': 40,
            'character': 30,
            'location': 25,
            'object': 20,
            'artifact': 20,
            'faction': 30,
            'organization': 30,
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
    
    def load_json(self):
        """Load and parse the JSON file, supporting multiple formats."""
        print(f"Loading JSON file: {self.json_file}")
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.graph = nx.DiGraph()

            if 'nodes' in data and 'edges' in data:
                # Handle "nodes" and "edges" format
                nodes = data.get('nodes', [])
                for node_data in nodes:
                    node_id = node_data.get('id')
                    if not node_id:
                        print(f"  ? Skipping node with missing id: {node_data.get('label', 'N/A')}")
                        continue

                    attributes = node_data.copy()
                    if 'id' in attributes:
                        del attributes['id']

                    self.graph.add_node(node_id, **attributes)

                edges = data.get('edges', [])
                for edge_data in edges:
                    source = edge_data.get('source')
                    target = edge_data.get('target')

                    if source and target and self.graph.has_node(source) and self.graph.has_node(target):
                        attributes = edge_data.copy()
                        if 'source' in attributes: del attributes['source']
                        if 'target' in attributes: del attributes['target']
                        if 'relationship' in attributes:
                            attributes['label'] = attributes.pop('relationship')

                        self.graph.add_edge(source, target, **attributes)
                    else:
                        print(f"  ? Skipping edge with missing node: {source} -> {target}")

            elif 'entities' in data and 'relationships' in data:
                # Handle "entities" and "relationships" format
                entities = data.get('entities', {})
                for node_id, node_data in entities.items():
                    label = node_data.get('name', node_id)
                    node_type = node_data.get('type', 'unknown').lower().replace(' ', '_')

                    attributes = {'label': label, 'type': node_type}
                    if 'data' in node_data and isinstance(node_data['data'], dict):
                        attributes.update(node_data['data'])

                    self.graph.add_node(node_id, **attributes)

                relationships = data.get('relationships', [])
                for edge in relationships:
                    source = edge.get('source')
                    target = edge.get('target')
                    relationship_type = edge.get('type', 'related')

                    if source and target and self.graph.has_node(source) and self.graph.has_node(target):
                        self.graph.add_edge(source, target, label=relationship_type)
                    else:
                        print(f"  ? Skipping edge with missing node: {source} -> {target}")

            else:
                print("✗ Error: JSON file does not contain a recognized graph structure ('nodes'/'edges' or 'entities'/'relationships').")
                return False

            print(f"✓ Loaded graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
            return True
        except json.JSONDecodeError as e:
            print(f"✗ Error decoding JSON file: {e}")
            return False
        except Exception as e:
            print(f"✗ Error loading JSON file: {e}")
            return False

    
    def is_episode_title(self, title):
        """Check if a title matches common episode naming patterns."""
        for pattern in self.episode_patterns:
            if re.match(pattern, title, re.IGNORECASE):
                return True
        return False
    
    def detect_page_type(self, soup, page_title):
        """
        Detect the actual type of a wiki page using a local LLM.
        Returns the detected type (or 'unknown') and confidence.
        """
        if self.is_episode_title(page_title):
            return 'episode', 1.0

        # 1. Extract relevant text from the page
        infobox_text = ""
        infobox = soup.find('aside', class_='portable-infobox')
        if infobox:
            infobox_text = infobox.get_text(separator='\n', strip=True)

        content_text = ""
        page_content = soup.find('div', class_='mw-parser-output')
        if page_content:
            # Get text from the first few paragraphs, limit to ~700 words
            paragraphs = page_content.find_all('p', recursive=False)
            text_parts = []
            word_count = 0
            for p in paragraphs:
                p_text = p.get_text(strip=True)
                text_parts.append(p_text)
                word_count += len(p_text.split())
                if word_count > 700:
                    break
            content_text = '\n'.join(text_parts)

        if not infobox_text and not content_text:
            print("      [LLM] No content to classify.")
            return 'unknown', 0.0

        # 2. Construct the prompt
        prompt = f"""
You are an expert assistant classifying pages from the Critical Role fan wiki. Your task is to determine the single most likely type for the page based on the provided text.

Classify the page into ONE of the following categories:
['character', 'location', 'faction', 'object', 'artifact', 'event', 'historical_event', 'mystery', 'episode', 'unknown']

- 'faction' is for organizations, noble houses, mercenary companies, or official groups.
- 'character' is for individual people or creatures.
- 'location' is for places like cities, regions, or buildings.
- 'object' is for items, while 'artifact' is for powerful, unique items.
- 'event' is for specific occurrences, while 'historical_event' is for those in the distant past.

Respond with only a single, valid JSON object containing your classification and a confidence score. Do not add any other text, explanation, or markdown.

Example response: {{"type": "character", "confidence": 0.95}}

---
Page Title: "{page_title}"
---
Infobox Text:
{infobox_text}
---
Page Content:
{content_text}
---
"""
        # 3. Call the local Ollama API
        try:
            print("      [LLM] Querying local LLM for classification...")
            response = self.session.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=120  # Generous timeout for the LLM
            )
            response.raise_for_status()
            
            response_data = response.json()
            llm_json = json.loads(response_data.get('response', '{}'))
            
            detected_type = llm_json.get('type', 'unknown')
            confidence = float(llm_json.get('confidence', 0.0))
            
            print(f"      [LLM] Classified as '{detected_type}' with confidence {confidence:.2f}")
            return detected_type, confidence

        except requests.exceptions.RequestException as e:
            print(f"      [LLM] ✗ ERROR: Could not connect to Ollama API: {e}")
            print("      [LLM] Is Ollama running and is the 'llama3.1:8b' model pulled?")
            return 'unknown', 0.0
        except (json.JSONDecodeError, KeyError) as e:
            print(f"      [LLM] ✗ ERROR: Failed to parse LLM response: {e}")
            print(f"      [LLM] Raw response: {response_data.get('response', '')}")
            return 'unknown', 0.0
    
    def extract_campaigns_from_page(self, soup):
        """Extract campaign numbers mentioned on a wiki page."""
        all_campaigns = set()
        infobox_campaigns = set()
        
        infobox = soup.find('aside', class_='portable-infobox')
        if infobox:
            infobox_text = infobox.get_text().lower()
            episode_refs = re.findall(r'\((\d+)x\d+\)', infobox_text)
            infobox_campaigns.update(int(c) for c in episode_refs)
            campaign_matches = re.findall(r'campaign\s*(\d+)', infobox_text)
            infobox_campaigns.update(int(c) for c in campaign_matches)
            c_matches = re.findall(r'\bc(\d+)\b', infobox_text)
            infobox_campaigns.update(int(c) for c in c_matches)
        
        all_campaigns.update(infobox_campaigns)
        
        text_content = soup.get_text().lower()
        episode_refs = re.findall(r'\((\d+)x\d+\)', text_content)
        all_campaigns.update(int(c) for c in episode_refs)
        campaign_matches = re.findall(r'campaign\s*(\d+)', text_content)
        all_campaigns.update(int(c) for c in campaign_matches)
        c_matches = re.findall(r'\bc(\d+)\b', text_content)
        all_campaigns.update(int(c) for c in c_matches)
        
        categories = soup.find_all('a', href=re.compile(r'/wiki/Category:'))
        for cat in categories:
            cat_text = cat.get_text().lower()
            if 'campaign' in cat_text:
                nums = re.findall(r'\d+', cat_text)
                all_campaigns.update(int(n) for n in nums)
        
        return {
            'infobox_campaigns': infobox_campaigns,
            'all_campaigns': all_campaigns
        }
    
    def validate_page_type(self, soup, expected_type, page_title):
        """Validate that a wiki page matches the expected entity type using LLM classification."""
        reasons = []
        
        # Groups of types that are considered compatible or synonymous
        compatible_types = [
            {'event', 'historical_event'},
            {'object', 'artifact'}
        ]

        # Get the classification from the LLM-powered function
        detected_type, llm_confidence = self.detect_page_type(soup, page_title)
        reasons.append(f"LLM classified as: {detected_type} (confidence: {llm_confidence:.2f})")

        # Start with the confidence provided by the LLM
        final_confidence = llm_confidence

        # Reject if it looks like an episode/transcript page when we don't expect one
        if detected_type == 'episode':
            reasons.append(f"✗ Page is an episode, but expected '{expected_type}'.")
            return 0.0, reasons

        page_header = soup.find('h1', class_='page-header__title')
        if page_header and any(word in page_header.get_text().lower() for word in ['transcript', 'episode']):
            reasons.append("Header indicates it is an episode page (-0.8)")
            final_confidence -= 0.8

        # Check for direct or compatible matches
        is_compatible = False
        if detected_type == expected_type:
            is_compatible = True
            final_confidence = min(1.0, final_confidence + 0.1)
            reasons.append(f"✓ LLM type directly matches expected type ('{expected_type}'). Confidence boosted.")
        else:
            for group in compatible_types:
                if expected_type in group and detected_type in group:
                    is_compatible = True
                    reasons.append(f"✓ LLM type '{detected_type}' is a valid synonym for expected '{expected_type}'. No penalty.")
                    break
        
        # Handle mismatches
        if not is_compatible and detected_type != 'unknown':
            reasons.append(f"! LLM type '{detected_type}' mismatches expected '{expected_type}'. Trusting LLM.")
            # Apply a small penalty for the mismatch
            final_confidence *= 0.85

        # Ensure confidence is within bounds
        final_confidence = max(0.0, min(1.0, final_confidence))
        
        return final_confidence, reasons
    
    def validate_campaign(self, soup, page_title):
        """Check if a page is relevant to the target campaign."""
        campaign_data = self.extract_campaigns_from_page(soup)
        infobox_campaigns = campaign_data['infobox_campaigns']
        all_campaigns = campaign_data['all_campaigns']
        
        if not all_campaigns:
            return 0.6, "No specific campaign mentioned (possibly universal content)"
        
        if infobox_campaigns:
            if self.target_campaign in infobox_campaigns:
                if len(infobox_campaigns) == 1:
                    return 1.0, f"Infobox shows only Campaign {self.target_campaign}"
                else:
                    other_camps = ', '.join(str(c) for c in sorted(infobox_campaigns) if c != self.target_campaign)
                    return 0.9, f"Infobox shows Campaign {self.target_campaign} (also: {other_camps})"
            else:
                other_campaigns = ', '.join(str(c) for c in sorted(infobox_campaigns))
                return 0.1, f"Infobox shows Campaign(s) {other_campaigns}, not {self.target_campaign}"
        
        if self.target_campaign in all_campaigns:
            if len(all_campaigns) == 1:
                return 0.85, f"Only mentions Campaign {self.target_campaign}"
            else:
                return 0.7, f"Mentions Campaign {self.target_campaign} (among {len(all_campaigns)} campaigns)"
        else:
            other_campaigns = ', '.join(str(c) for c in sorted(all_campaigns))
            return 0.15, f"Only mentions Campaign(s) {other_campaigns}, not {self.target_campaign}"
    
    def score_search_result(self, node_label, result, node_type):
        """Score a search result based on title matching."""
        score = 0
        title = result['title']
        size = result.get('size', 0)
        
        if title.lower() == node_label.lower():
            score = 100
        else:
            node_words = set(node_label.lower().split())
            title_words = set(title.lower().split())
            word_overlap = len(node_words & title_words)
            word_coverage = word_overlap / len(node_words) if node_words else 0
            
            score = word_coverage * 50
            if word_overlap == len(node_words):
                score += 20
        
        if self.is_episode_title(title):
            score -= 50
        
        if size < 100:
            score -= 20
        elif size > 1000:
            score += 10
        
        should_validate = score > 20
        return score, should_validate
    
    def fetch_and_validate_page(self, page_title, node_label, node_type):
        """Fetch a wiki page and validate it."""
        cache_key = f"{page_title}|{node_type}"
        if cache_key in self.validation_cache:
            return self.validation_cache[cache_key]
        
        try:
            page_wiki_name = page_title.replace(' ', '_')
            page_url = f"{self.base_url}/wiki/{page_wiki_name}"
            
            print(f"    Validating: {page_url}")
            time.sleep(0.5)
            
            response = self.session.get(page_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            type_confidence, type_reasons = self.validate_page_type(soup, node_type, page_title)
            print(f"      Type confidence: {type_confidence:.2f}")
            for reason in type_reasons:
                print(f"        - {reason}")
            
            campaign_confidence, campaign_reason = self.validate_campaign(soup, page_title)
            print(f"      Campaign confidence: {campaign_confidence:.2f}")
            print(f"        - {campaign_reason}")
            
            if page_title.lower() == node_label.lower():
                total_confidence = (type_confidence * 0.5) + (campaign_confidence * 0.5)
            else:
                total_confidence = (type_confidence * 0.7) + (campaign_confidence * 0.3)
            
            all_reasons = type_reasons + [campaign_reason]
            
            if total_confidence < 0.4:
                print(f"      ✗ Rejected (confidence {total_confidence:.2f} < 0.4)")
                result = (None, None, total_confidence, all_reasons)
                self.validation_cache[cache_key] = result
                return result
            
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
            
            if not image_url and infobox:
                image_elem = infobox.find('img')
                if image_elem:
                    img_url = image_elem.get('src') or image_elem.get('data-src')
                    if img_url:
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url
                        image_url = img_url
            
            if image_url:
                print(f"      ✓ Found image")
            
            print(f"      ✓ Accepted (confidence {total_confidence:.2f})")
            result = (image_url, page_url, total_confidence, all_reasons)
            self.validation_cache[cache_key] = result
            return result
            
        except Exception as e:
            print(f"      ✗ Error: {e}")
            result = (None, None, 0, [f"Error: {str(e)}"])
            self.validation_cache[cache_key] = result
            return result
    
    def strip_honorifics(self, name):
        """Remove common honorifics from a name."""
        words = name.split()
        if words and words[0].lower() in self.honorifics:
            return ' '.join(words[1:])
        return name
    
    def fetch_wiki_image(self, node_label, node_type):
        """Fetch an image and page URL for a node from the Critical Role wiki."""
        if node_label in self.image_cache:
            return self.image_cache[node_label]
        
        print(f"  Searching for: {node_label} (type: {node_type})")
        
        best_result = None
        best_confidence = 0
        best_title = None
        
        search_queries = [node_label]
        
        # Strip parenthetical suffixes like "(Artifact)" or "(NPC)"
        clean_label = re.sub(r'\s*\([^)]*\)\s*$', '', node_label).strip()
        if clean_label != node_label:
            search_queries.insert(0, clean_label)
            print(f"    Will also try without suffix: {clean_label}")
        
        # Try without honorifics
        stripped_name = self.strip_honorifics(node_label)
        if stripped_name != node_label:
            search_queries.append(stripped_name)
            print(f"    Will also try without honorific: {stripped_name}")
        
        # Check manual overrides first
        if node_label in self.manual_overrides:
            override_title = self.manual_overrides[node_label]
            print(f"    Using manual override: {override_title}")
            image_url, page_url, confidence, reasons = self.fetch_and_validate_page(
                override_title, node_label, node_type
            )
            if confidence > 0.35:
                best_result = {'image_url': image_url, 'page_url': page_url, 
                              'confidence': confidence, 'reasons': reasons}
                best_confidence = confidence
                best_title = override_title
                print(f"    ✓ Manual override accepted with confidence {confidence:.2f}")
                self.image_cache[node_label] = best_result
                return best_result
            else:
                print(f"    ✗ Manual override rejected (confidence {confidence:.2f} < 0.35)")
        
        # Search wiki API with all query variations
        for query in search_queries:
            if query != node_label:
                print(f"    Trying search variation: {query}")
                
            try:
                encoded_label = urllib.parse.quote_plus(query)
                search_url = f"{self.base_url}/api.php?action=query&list=search&srsearch={encoded_label}&format=json&srprop=size&srlimit=5"
                
                search_response = self.session.get(search_url, timeout=10)
                search_response.raise_for_status()
                search_data = search_response.json()
                search_results = search_data.get('query', {}).get('search', [])
                
                if query == search_queries[0] or search_results:
                    print(f"    Found {len(search_results)} search results")
                
                for result in search_results[:5]:
                    title = result['title']
                    search_score, should_validate = self.score_search_result(
                        query, result, node_type
                    )
                    
                    print(f"    Candidate: {title} (search score: {search_score:.1f})")
                    
                    if not should_validate:
                        print(f"      Skipped (low search score)")
                        continue
                    
                    image_url, page_url, confidence, reasons = self.fetch_and_validate_page(
                        title, node_label, node_type
                    )
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_result = {
                            'image_url': image_url,
                            'page_url': page_url,
                            'confidence': confidence,
                            'reasons': reasons
                        }
                        best_title = title
                        print(f"      ✓ New best match: {title} (confidence {confidence:.2f})")
                        
                        if confidence > 0.85:
                            print(f"    ✓ Found high-confidence match, stopping search")
                            break
                
                if best_confidence > 0.7:
                    break
                    
            except Exception as e:
                print(f"    ✗ Search error: {e}")
        
        if best_result and best_confidence >= 0.4:
            print(f"  ✓ Final result: {best_title} with confidence {best_confidence:.2f}")
            self.image_cache[node_label] = best_result
            return best_result
        else:
            if best_result:
                print(f"  ✗ Best match ({best_title}) rejected: confidence {best_confidence:.2f} < 0.4")
            else:
                print(f"  ✗ No confident match found")
            self.image_cache[node_label] = None
            return None
    
    def enhance_graph(self):
        """Enhance graph nodes with portraits and styling."""
        print("\nEnhancing graph with portraits and styling...")
        print(f"Target campaign: {self.target_campaign}")
        
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
            
            wiki_data = self.fetch_wiki_image(label, node_type)
            image_url, page_url, confidence = (None, None, 0)
            if wiki_data:
                image_url = wiki_data.get('image_url')
                page_url = wiki_data.get('page_url')
                confidence = wiki_data.get('confidence', 0)
            
            title_parts = [f"<b>{label}</b>"]
            if node_type:
                title_parts.append(f"Type: {node_type.replace('_', ' ').title()}")
            
            if confidence > 0:
                title_parts.append(f"Match Confidence: {confidence:.0%}")
            
            for key, value in node_data.items():
                if key not in ['label', 'type', 'id'] and value:
                    if isinstance(value, list):
                        value = ', '.join(str(v) for v in value)
                    clean_key = key.replace('_', ' ').title()
                    title_parts.append(f"{clean_key}: {value}")
            
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
        
        print("\nEnhancing edges...")
        for source, target, edge_data in self.graph.edges(data=True):
            label = edge_data.get('label', '')
            
            if isinstance(label, list):
                label = label[0] if label else ''
            
            style = self.edge_styles.get(label, {'color': '#999999', 'width': 1})
            
            self.graph.edges[source, target]['color'] = style['color']
            self.graph.edges[source, target]['width'] = style['width']
            if 'dashes' in style:
                self.graph.edges[source, target]['dashes'] = style['dashes']
            
            if label:
                self.graph.edges[source, target]['title'] = label
    
    def create_visualization(self, output_file='episode_graph.html'):
        """Create an interactive visualization."""
        print(f"\nCreating visualization: {output_file}")
        
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
            spring_length=200,
            spring_strength=0.01,
            damping=0.09
        )
        
        net.from_nx(self.graph)
        net.show_buttons(filter_=['physics'])
        net.save_graph(output_file)
        self.enhance_html(output_file)
        
        print(f"✓ Visualization saved to {output_file}")
    
    def enhance_html(self, html_file):
        """Add legend and enhanced interactivity to HTML."""
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            css_additions = '''
    <style>
    body { margin: 0; padding: 0; overflow: hidden; }
    #mynetwork { width: 100vw; height: 100vh; }
    #legend {
        position: absolute; top: 20px; right: 20px;
        background-color: rgba(26, 26, 26, 0.95);
        border: 2px solid #444; border-radius: 8px; padding: 15px;
        color: white; font-family: Arial, sans-serif; font-size: 13px;
        max-width: 280px; max-height: 80vh; overflow-y: auto;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); z-index: 1000;
    }
    #legend h3 {
        margin: 0 0 10px 0; font-size: 16px;
        border-bottom: 1px solid #555; padding-bottom: 8px;
    }
    .legend-section { margin-bottom: 15px; }
    .legend-section h4 { margin: 0 0 8px 0; font-size: 14px; color: #aaa; }
    .legend-item {
        display: flex; align-items: center; margin: 5px 0; font-size: 12px;
    }
    .legend-color {
        width: 20px; height: 20px; border-radius: 3px;
        margin-right: 8px; flex-shrink: 0;
    }
    .legend-line {
        width: 30px; height: 3px; margin-right: 8px; flex-shrink: 0;
    }
    #legend-close {
        position: absolute; top: 10px; right: 10px;
        cursor: pointer; font-size: 18px; color: #aaa;
    }
    #legend-close:hover { color: white; }
    #legend-toggle {
        position: absolute; top: 20px; right: 20px;
        background-color: rgba(26, 26, 26, 0.95);
        border: 2px solid #444; border-radius: 8px; padding: 10px 15px;
        color: white; font-family: Arial, sans-serif; font-size: 14px;
        cursor: pointer; z-index: 1001; display: none;
    }
    #legend-toggle:hover { background-color: rgba(40, 40, 40, 0.95); }
    </style>
    '''
            html_content = html_content.replace('</head>', css_additions + '</head>')
            
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
            
            js_additions = '''
    <script type="text/javascript">
    window.addEventListener('load', function() {
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
        }, 1000);
    });
    </script>
    '''
            html_content = html_content.replace('</body>', js_additions + '\n</body>')
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print("  ✓ Enhanced HTML with legend and interactivity")
            
        except Exception as e:
            print(f"  ⚠ Error enhancing HTML: {e}")
    
    def print_statistics(self):
        """Print graph statistics."""
        print(f"\n{'=' * 60}")
        print("Graph Statistics")
        print(f"{'=' * 60}")
        print(f"Total Nodes: {self.graph.number_of_nodes()}")
        print(f"Total Edges: {self.graph.number_of_edges()}")
        
        type_counts = {}
        for node_id in self.graph.nodes():
            node_type = self.graph.nodes[node_id].get('type', 'unknown')
            if isinstance(node_type, list):
                node_type = node_type[0] if node_type else 'unknown'
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
        
        print("\nNodes by Type:")
        for node_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {node_type.replace('_', ' ').title()}: {count}")
        
        validated_count = sum(1 for data in self.image_cache.values() if data is not None)
        images_found = sum(1 for data in self.image_cache.values() 
                          if data is not None and data.get('image_url') is not None)
        
        if self.image_cache:
            print(f"\nWiki Page Validation:")
            print(f"  Validated pages: {validated_count}/{len(self.image_cache)}")
            print(f"  Images found: {images_found}/{len(self.image_cache)}")
            
            if validated_count > 0:
                avg_confidence = sum(data['confidence'] for data in self.image_cache.values() 
                                    if data is not None) / validated_count
                print(f"  Average confidence: {avg_confidence:.1%}")
        
        print(f"{'=' * 60}")
    
    def run(self, output_file='episode_graph.html'):
        """Main execution flow."""
        print("Critical Role Episode Graph Visualizer")
        print("=" * 60)
        
        if not self.load_json():
            return False
        
        self.enhance_graph()
        self.create_visualization(output_file)
        self.print_statistics()
        
        print(f"\n✓ Complete! Open {output_file} in your browser to explore the graph.")
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Visualize Critical Role episode data from JSON files'
    )
    parser.add_argument('json_file', help='Path to the JSON file')
    parser.add_argument('output_file', help='Path for the output HTML file')
    parser.add_argument('--campaign', type=int, default=4,
                       help='Target campaign number (default: 4)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.json_file):
        print(f"Error: JSON file not found: {args.json_file}")
        sys.exit(1)
    
    output_dir = os.path.dirname(args.output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    visualizer = EpisodeGraphVisualizer(args.json_file, target_campaign=args.campaign)
    success = visualizer.run(args.output_file)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()