"""Match listing geography without guessing from titles or eligibility domicile."""

import re
import unicodedata


# Common Indian city names and renamed-city aliases. Explicit location/state
# values still work worldwide; this index adds state matching for city-only feeds.
STATE_CITIES = {
    "Andhra Pradesh": ["Visakhapatnam|Vizag", "Vijayawada", "Amaravati", "Tirupati"],
    "Arunachal Pradesh": ["Itanagar"],
    "Assam": ["Guwahati", "Dispur"],
    "Bihar": ["Patna", "Gaya"],
    "Chhattisgarh": ["Raipur", "Bhilai"],
    "Goa": ["Panaji|Panjim", "Margao"],
    "Gujarat": ["Ahmedabad", "Gandhinagar", "Surat", "Vadodara|Baroda", "Rajkot"],
    "Haryana": ["Gurugram|Gurgaon", "Faridabad", "Panchkula"],
    "Himachal Pradesh": ["Shimla", "Dharamshala"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad"],
    "Karnataka": ["Bengaluru|Bangalore", "Mysuru|Mysore", "Mangaluru|Mangalore", "Hubballi|Hubli"],
    "Kerala": ["Thiruvananthapuram|Trivandrum", "Kochi|Cochin", "Kozhikode|Calicut"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Gwalior", "Jabalpur"],
    "Maharashtra": ["Mumbai|Bombay", "Pune|Poona", "Nagpur", "Nashik|Nasik", "Thane"],
    "Manipur": ["Imphal"],
    "Meghalaya": ["Shillong"],
    "Mizoram": ["Aizawl"],
    "Nagaland": ["Kohima", "Dimapur"],
    "Odisha|Orissa": ["Bhubaneswar", "Cuttack"],
    "Punjab": ["Ludhiana", "Amritsar", "Mohali", "Jalandhar"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota"],
    "Sikkim": ["Gangtok"],
    "Tamil Nadu": ["Chennai|Madras", "Coimbatore", "Madurai", "Tiruchirappalli|Trichy"],
    "Telangana": ["Hyderabad", "Warangal"],
    "Tripura": ["Agartala"],
    "Uttar Pradesh": ["Lucknow", "Noida", "Greater Noida", "Ghaziabad", "Kanpur", "Varanasi"],
    "Uttarakhand|Uttaranchal": ["Dehradun", "Haridwar"],
    "West Bengal": ["Kolkata|Calcutta", "Siliguri", "Durgapur"],
    "Andaman and Nicobar Islands": ["Port Blair|Sri Vijaya Puram"],
    "Chandigarh": [],
    "Dadra and Nagar Haveli and Daman and Diu": ["Silvassa", "Daman", "Diu"],
    "Delhi|New Delhi|NCT of Delhi": [],
    "Jammu and Kashmir": ["Jammu", "Srinagar"],
    "Ladakh": ["Leh", "Kargil"],
    "Lakshadweep": ["Kavaratti"],
    "Puducherry|Pondicherry": [],
}


def normalize(value):
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[^\W_]+", text))


def contains(text, phrase):
    return f" {phrase} " in f" {text} "


def location_values(record):
    values = []
    for value in (
        record.get("location"),
        record.get("city"),
        record.get("state"),
        (record.get("source_summary") or {}).get("locations"),
        (record.get("requirements") or {}).get("locations"),
    ):
        if isinstance(value, str):
            values.append(normalize(value))
        elif isinstance(value, list):
            values.extend(normalize(item) for item in value if isinstance(item, str))
    return values


def matches_location(record, query):
    query = normalize(query)
    if not query:
        return True
    values = location_values(record)
    terms = {query}
    # Expand exact state names to known cities, and city aliases to each other.
    # Never expand a city to its whole state: Mumbai must not match Pune.
    for state, cities in STATE_CITIES.items():
        states = {normalize(name) for name in state.split("|")}
        if query in states:
            terms.update(states)
            terms.update(normalize(city) for group in cities for city in group.split("|"))
        for group in cities:
            aliases = {normalize(city) for city in group.split("|")}
            if query in aliases:
                terms.update(aliases)
    return any(contains(value, term) for value in values for term in terms)
