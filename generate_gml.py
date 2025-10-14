#!/usr/bin/env python3
"""
Generate a valid GML file for Critical Role Campaign 4 Episode 1 network graph
"""

def write_gml_file(filename='cr_c4e1_network.gml'):
    """Write a properly formatted GML file"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        # Header
        f.write('Creator "Critical Role C4E1 Network Extractor"\n')
        f.write('graph [\n')
        f.write('  directed 1\n')
        f.write('  comment "Critical Role Campaign 4 Episode 1 Network Graph"\n')
        f.write('\n')
        
        # Define all nodes
        nodes = [
            # Event nodes
            (1, "Execution of Thjazi Fang", "event", {"location": "Guardian Wall, Dol-Makjar", "outcome": "Death"}),
            (2, "Wake at Fang Home", "event", {"location": "The Rookery", "time": "Evening"}),
            (3, "Raid on Hideout", "event", {"location": "The Tanners", "outcome": "Thimble injured"}),
            (4, "Mask Activation", "event", {"location": "Hal's study", "status": "Cliffhanger"}),
            
            # Character nodes
            (10, "Halandil Fang", "character", {"race": "Orc", "class": "Bard"}),
            (11, "Azune Nayar", "character", {"race": "Human", "class": "Sorcerer"}),
            (12, "Thjazi Fang", "character", {"race": "Orc", "status": "Dead"}),
            (13, "Thimble", "character", {"race": "Pixie", "status": "Injured"}),
            (14, "Teor Pridesire", "character", {"race": "Nama", "class": "Paladin"}),
            (15, "Thaisha Lloy", "character", {"race": "Orc", "class": "Druid"}),
            (16, "Occtis Tachonis", "character", {"race": "Human", "class": "Necromancer"}),
            (17, "Wicander Halovar", "character", {"race": "Human", "class": "Cleric"}),
            (18, "Tyranny", "character", {"race": "Demon", "role": "Aspirant"}),
            (19, "Julien Davinos", "character", {"race": "Human", "class": "Fighter"}),
            (20, "Kattigan Vale", "character", {"race": "Human", "class": "Ranger"}),
            (21, "Bolaire Lathalia", "character", {"role": "Museum curator"}),
            (22, "Murray Mag'Nesson", "character", {"race": "Dwarf", "class": "Wizard"}),
            (23, "Vaelus", "character", {"race": "Elf", "faction": "Sisters of Sylandri"}),
            (24, "Aranessa Royce", "character", {"race": "Human", "faction": "House Royce"}),
            (25, "Loza Blade", "character", {"race": "Orc", "faction": "Torn Banner"}),
            (26, "Shadia Fang", "character", {"race": "Orc", "relation": "Hal's daughter"}),
            (27, "Hero Fang", "character", {"race": "Half-Orc", "relation": "Hal's daughter"}),
            (28, "Olgud Akarat", "character", {"race": "Orc", "role": "Business partner"}),
            (29, "Talcydimir Pridesire", "character", {"race": "Nama", "status": "Missing"}),
            (30, "Photarch", "character", {"race": "Human", "role": "Matriarch"}),
            (31, "Alogar Lloy", "character", {"race": "Orc", "status": "Absent"}),
            
            # Location nodes
            (40, "Dol-Makjar", "location", {"type": "City"}),
            (41, "Guardian Wall", "location", {"type": "Monument"}),
            (42, "The Rookery", "location", {"type": "Neighborhood"}),
            (43, "The Tanners", "location", {"type": "Neighborhood"}),
            (44, "Villa Aurora", "location", {"type": "Estate"}),
            (45, "The Penteveral", "location", {"type": "Institution"}),
            (46, "Tir Cruthu", "location", {"type": "Realm"}),
            (47, "Mournvale", "location", {"type": "Region"}),
            
            # Object nodes
            (60, "Stone of Nightsong", "object", {"status": "Stolen"}),
            (61, "Escape Glyph Real", "object", {"creator": "Thimble"}),
            (62, "Escape Glyph False", "object", {"status": "Was on Thjazi"}),
            (63, "Black Clay Mask", "object", {"status": "Reforming"}),
            (64, "Thjazi's Scimitar", "object", {"status": "Returned to Hal"}),
            (65, "Silver Box", "object", {"contents": "Mask pieces"}),
            (66, "Bolaire's Mask", "object", {"type": "Magical"}),
            
            # Faction nodes
            (80, "Sundered Houses", "faction", {"type": "Noble alliance"}),
            (81, "Candescent Creed", "faction", {"type": "Religious order"}),
            (82, "Revolutionary Guard", "faction", {"type": "Military"}),
            (83, "Torn Banner", "faction", {"type": "Mercenary company"}),
            (84, "Crow Keepers", "faction", {"type": "Thieves guild"}),
            (85, "Old Path", "faction", {"type": "Druidic tradition"}),
            (86, "Revolutionary Council", "faction", {"type": "Government"}),
            
            # Historical events
            (100, "Shapers' War", "historical_event", {"timeframe": "70 years ago"}),
            (101, "Falconer's Rebellion", "historical_event", {}),
            (102, "Closing of Faerie", "historical_event", {}),
            (103, "Battle of Maharlian Falls", "historical_event", {}),
            
            # Mysteries
            (120, "Failed Escape Mystery", "mystery", {}),
            (121, "Sky Vision Mystery", "mystery", {}),
            (122, "Betrayal Mystery", "mystery", {}),
            (123, "Stone Purpose Mystery", "mystery", {}),
            (124, "Julien's Curse Mystery", "mystery", {}),
            (125, "Black Mask Mystery", "mystery", {}),
            (126, "Thjazi's Messages Mystery", "mystery", {}),
        ]
        
        # Write nodes
        for node_id, label, node_type, attrs in nodes:
            f.write(f'  node [\n')
            f.write(f'    id {node_id}\n')
            f.write(f'    label "{label}"\n')
            f.write(f'    type "{node_type}"\n')
            for key, value in attrs.items():
                f.write(f'    {key} "{value}"\n')
            f.write(f'  ]\n')
        
        f.write('\n')
        
        # Define all edges
        edges = [
            # Event participation
            (1, 12, "executed"),
            (1, 10, "witnessed"),
            (1, 11, "conducted_scan"),
            (1, 14, "attended"),
            (1, 17, "attended"),
            (1, 19, "attended"),
            (1, 21, "attended"),
            (1, 24, "attended"),
            (1, 25, "attended"),
            
            (2, 10, "hosted"),
            (2, 11, "attended"),
            (2, 14, "attended"),
            (2, 15, "performed_rites"),
            (2, 16, "attended"),
            (2, 17, "attended"),
            (2, 18, "attended"),
            (2, 19, "attended"),
            (2, 21, "attended"),
            (2, 22, "attended"),
            (2, 23, "crashed"),
            (2, 24, "attended"),
            (2, 25, "attended"),
            
            (3, 13, "victim"),
            (3, 11, "investigated"),
            (3, 14, "investigated"),
            (3, 16, "investigated"),
            (3, 20, "investigated"),
            
            (4, 15, "witnessed"),
            (4, 10, "witnessed"),
            
            # Character relationships
            (10, 12, "brother"),
            (10, 26, "father"),
            (10, 27, "father"),
            (10, 15, "former_partner"),
            (10, 28, "business_partner"),
            (10, 21, "friend"),
            
            (12, 24, "estranged_husband"),
            (12, 13, "partner"),
            (12, 11, "former_commander"),
            (12, 14, "former_commander"),
            (12, 20, "friend"),
            
            (11, 14, "friend"),
            (11, 15, "conspirator"),
            (11, 16, "conspirator"),
            
            (15, 26, "mother"),
            (15, 16, "conspirator"),
            (15, 19, "enemy"),
            (15, 31, "mother"),
            
            (19, 24, "childhood_friend"),
            (19, 12, "captured_and_hates"),
            (19, 31, "mentor"),
            
            (17, 30, "grandson"),
            (17, 18, "mentor"),
            
            (14, 29, "brother"),
            (14, 25, "companion"),
            (14, 13, "saved"),
            
            (23, 21, "knows"),
            
            # Location relationships
            (1, 41, "occurred_at"),
            (41, 40, "part_of"),
            (2, 42, "occurred_at"),
            (42, 40, "part_of"),
            (3, 43, "occurred_at"),
            (43, 40, "part_of"),
            (10, 42, "lives_in"),
            (44, 80, "owned_by"),
            (22, 45, "works_at"),
            (13, 46, "origin"),
            (23, 47, "traveled_from"),
            
            # Object relationships
            (60, 3, "stolen_during"),
            (60, 23, "sought_by"),
            (61, 13, "created_by"),
            (62, 12, "was_on"),
            (63, 65, "contained_in"),
            (65, 15, "held_by"),
            (64, 12, "belonged_to"),
            (64, 10, "returned_to"),
            (66, 21, "worn_by"),
            
            # Faction relationships
            (11, 82, "member_of"),
            (17, 81, "priest_of"),
            (18, 81, "aspirant_of"),
            (15, 85, "practitioner_of"),
            (25, 83, "commander_of"),
            (14, 83, "member_of"),
            (16, 80, "member_of"),
            (19, 80, "serves"),
            (24, 80, "member_of"),
            (30, 81, "leader_of"),
            (84, 3, "likely_responsible"),
            
            # Historical connections
            (11, 101, "fought_in"),
            (12, 101, "fought_in"),
            (14, 101, "fought_in"),
            (25, 101, "fought_in"),
            (60, 100, "used_in"),
            (102, 13, "affected"),
            (103, 19, "victory_for"),
            (103, 12, "defeat_for"),
            
            # Mystery connections
            (120, 3, "involves"),
            (120, 29, "involves"),
            (121, 1, "occurred_during"),
            (122, 3, "about"),
            (122, 84, "suspects"),
            (123, 60, "about"),
            (124, 19, "afflicts"),
            (124, 21, "detected_by"),
            (125, 63, "about"),
            (125, 4, "involves"),
            (126, 22, "involves"),
            (126, 21, "involves"),
            (126, 45, "involves"),
        ]
        
        # Write edges
        for source, target, label in edges:
            f.write(f'  edge [\n')
            f.write(f'    source {source}\n')
            f.write(f'    target {target}\n')
            f.write(f'    label "{label}"\n')
            f.write(f'  ]\n')
        
        # Close graph
        f.write(']\n')
    
    print(f"GML file '{filename}' created successfully!")
    print(f"Nodes: {len(nodes)}")
    print(f"Edges: {len(edges)}")

if __name__ == "__main__":
    write_gml_file()