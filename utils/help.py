import csv
import re
from typing import Tuple

import os.path

# Global variables to store patterns (initialized once)
_direct_request_pattern = None
_frustration_pattern = None
_complexity_pattern = None
_urgency_pattern = None
_patterns_initialized = False

def initialize_patterns(csv_path="/home/oladev/ai-agent/db/engine/help.csv"):
    """Initialize regex patterns from CSV file (called once)"""
    global _direct_request_pattern, _frustration_pattern, _complexity_pattern, _urgency_pattern, _patterns_initialized
    
    # Skip if already initialized
    if _patterns_initialized:
        return
    
    # Collect phrases by category
    phrases = {
        "direct_request": [],
        "frustration": [],
        "complexity": [],
        "urgency": []
    }
    
    # Read CSV file
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                phrase = row['phrase'].lower().strip('"')
                category = row['category']
                if category in phrases:
                    phrases[category].append(phrase)
    except FileNotFoundError:
        print(f"Warning: Escalation phrases CSV not found at {csv_path}")
        return
    
    # Compile regex for each category
    _direct_request_pattern = re.compile(r'\b(' + '|'.join(re.escape(p) for p in phrases["direct_request"]) + r')\b', re.IGNORECASE)
    _frustration_pattern = re.compile(r'\b(' + '|'.join(re.escape(p) for p in phrases["frustration"]) + r')\b', re.IGNORECASE)
    _complexity_pattern = re.compile(r'\b(' + '|'.join(re.escape(p) for p in phrases["complexity"]) + r')\b', re.IGNORECASE)
    _urgency_pattern = re.compile(r'\b(' + '|'.join(re.escape(p) for p in phrases["urgency"]) + r')\b', re.IGNORECASE)
    
    _patterns_initialized = True

def needs_human_intervention(text: str) -> Tuple[bool, str]:
    """
    Check if text indicates a need for human intervention.
    
    Args:
        text: User message to check
        
    Returns:
        Tuple: (needs_escalation, reason)
    """
    # Initialize patterns if not already done
    if not _patterns_initialized:
        initialize_patterns()
        
    # Return false if patterns couldn't be initialized (possible error)
    if not _patterns_initialized:
        return False, ""
    
    # Check for direct requests first (highest priority)
    if _direct_request_pattern.search(text):
        return True, "direct_request"
    
    # Check for urgency
    if _urgency_pattern.search(text):
        return True, "urgency"
    
    # Check for complexity
    if _complexity_pattern.search(text):
        return True, "complexity"
    
    # Check for frustration (need at least 2 indicators). I could increase to 3 but who needs angry customer lol?
    frustration_matches = _frustration_pattern.findall(text)
    if len(frustration_matches) >= 2:
        return True, "multiple_frustration_indicators"
    
    return False, ""
