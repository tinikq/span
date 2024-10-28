from dataclasses import dataclass
from datetime import date, time
from typing import List, Dict, Any

@dataclass
class Match:
    sport: str
    country: str
    liga: str
    time_match: time
    date_match: date
    team1: str
    team2: str
    coefficients: List[float]
    additional_coefficients: Dict[str, Any]

@dataclass
class ParseResult:
    matches: List[Match]
    errors: List[str]

