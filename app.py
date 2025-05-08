from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
import json
import requests
from datetime import datetime, timedelta
import time
from serpapi.google_search import GoogleSearch
import os
from dotenv import load_dotenv
from flight_deals_scraper import get_flight_deals

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')

# Global variable to store destination data
destination_data = {}

# Global variable to store trip details
trip_details = {
    'vacation_type': '',
    'travel_date': '',
    'budget': 300,
    'vacation_length': 7
}

# API classes
class FlightAPI:
    def __init__(self):
        # self.api_key = "4d4a48186e6f8239f71f0cb805a2c33745f8a2e2c17d469af687c930c25bf7c5"  # Replace with your actual SerpApi key
        self.api_key = "your_api_key_here"

    def get_flights(self, origin, destination, date, max_price=None):
        try:
            all_flights = []
            base_date = datetime.strptime(date, "%Y-%m-%d")
            dates = [
                (base_date - timedelta(days=1)).strftime("%Y-%m-%d"),
                base_date.strftime("%Y-%m-%d"),
                (base_date + timedelta(days=1)).strftime("%Y-%m-%d")
            ]
            
            for search_date in dates:
                formatted_date = datetime.strptime(search_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                params = {
                    "engine": "google_flights",
                    "departure_id": origin,
                    "arrival_id": destination,
                    "outbound_date": formatted_date,
                    "type": "2",
                    "currency": "USD",
                    "hl": "en",
                    "gl": "us",
                    "api_key": self.api_key
                }
                
                if max_price:
                    params["max_price"] = max_price
                
                search = GoogleSearch(params)
                results = search.get_dict()
                # print(f"results----{results}")
                flights = []
                
                if "best_flights" in results:
                    for flight_option in results["best_flights"]:
                        flight = self._extract_flight_details(flight_option)
                        flight['date'] = search_date
                        flights.append(flight)
                
                if "other_flights" in results:
                    for flight_option in results["other_flights"]:
                        flight = self._extract_flight_details(flight_option)
                        flight['date'] = search_date
                        flights.append(flight)
                
                all_flights.extend(flights)
            
            if not all_flights:
                print(f"No flights found for {origin} to {destination} around {date}")
                return []
                
            return all_flights
        except Exception as e:
            print(f"Error fetching flights: {str(e)}")
            return []
    
    def _extract_flight_details(self, flight_option):
        """Extract flight details from a flight option in the SerpApi response"""
        # Get the first flight segment for departure and arrival times
        first_flight = flight_option.get("flights", [{}])[0]
        last_flight = flight_option.get("flights", [{}])[-1]
        
        # Extract departure and arrival information
        departure_airport = first_flight.get("departure_airport", {})
        arrival_airport = last_flight.get("arrival_airport", {})
        
        # Format the flight number and airline
        airline = first_flight.get("airline", "Unknown")
        flight_no = first_flight.get("flight_number", "N/A")
        
        # If there are multiple flight segments, add connection info
        connection_info = ""
        if len(flight_option.get("flights", [])) > 1:
            connection_info = f" (via {flight_option.get('layovers', [{}])[0].get('name', 'Unknown')})"
        
        return {
            "airline": airline,
            "flight_no": flight_no,
            "departure": departure_airport.get("time", "N/A"),
            "arrival": arrival_airport.get("time", "N/A"),
            "price": flight_option.get("price", 0),
            "aircraft": first_flight.get("airplane", "N/A"),
            "duration": self._format_duration(flight_option.get("total_duration", 0)),
            "connection_info": connection_info
        }
    
    def _format_duration(self, minutes):
        """Convert minutes to a formatted duration string (e.g., '2h 30m')"""
        if not minutes:
            return "N/A"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        
        if hours > 0 and remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{remaining_minutes}m"
    
    def _get_mock_data(self):
        # Return mock flight data in case of API errors
        return [
            {
                "airline": "Mock Airlines",
                "flight_no": "MA123",
                "departure": "10:00 AM",
                "arrival": "1:00 PM",
                "price": 250,
                "aircraft": "Boeing 737",
                "duration": "3h 0m",
                "connection_info": ""
            },
            {
                "airline": "Mock Airlines",
                "flight_no": "MA456",
                "departure": "2:00 PM",
                "arrival": "5:00 PM",
                "price": 300,
                "aircraft": "Airbus A320",
                "duration": "3h 0m",
                "connection_info": ""
            }
        ]

class HotelAPI:
    def __init__(self):
        # self.api_key = "4d4a48186e6f8239f71f0cb805a2c33745f8a2e2c17d469af687c930c25bf7c5"
        self.api_key = "your_api_key_here"
    def get_hotels(self, date, location, min_rating=3.0, max_price=None, vacation_length=7):
        try:
            check_in_date = datetime.strptime(date, "%Y-%m-%d")
            check_out_date = check_in_date + timedelta(days=vacation_length)
            
            params = {
                "engine": "google_hotels",
                "q": f"hotels in {location}",
                "check_in_date": check_in_date.strftime("%Y-%m-%d"),
                "check_out_date": check_out_date.strftime("%Y-%m-%d"),
                "currency": "USD",
                "gl": "us",
                "hl": "en",
                "api_key": self.api_key
            }
            
            if max_price:
                params["max_price"] = max_price
            
            if min_rating >= 4.5:
                params["rating"] = "9"  # 4.5+
            elif min_rating >= 4.0:
                params["rating"] = "8"  # 4.0+
            elif min_rating >= 3.5:
                params["rating"] = "7"  # 3.5+
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            hotels = []
            if "properties" in results:
                for property_data in results["properties"]:
                    price_per_night = property_data.get("rate_per_night", {}).get("extracted_lowest", 0)
                    total_price = price_per_night * vacation_length
                    
                    # Only include hotels where total stay is within budget
                    if total_price <= max_price * vacation_length:
                        hotel = self._extract_hotel_details(property_data)
                        hotel['check_in'] = check_in_date.strftime("%Y-%m-%d")
                        hotel['check_out'] = check_out_date.strftime("%Y-%m-%d")
                        hotel['total_price'] = total_price  # Add total price for the entire stay
                        hotels.append(hotel)
            
            if not hotels:
                print(f"No hotels found in {location} for the specified dates within budget")
                return []
                
            return hotels
        except Exception as e:
            print(f"Error fetching hotels: {str(e)}")
            return []
    
    def _extract_hotel_details(self, property_data):
        """Extract hotel details from a property in the SerpApi response"""
        return {
            "name": property_data.get("name", "Unknown Hotel"),
            "price": property_data.get("rate_per_night", {}).get("extracted_lowest", 0),
            "rating": property_data.get("overall_rating", 0),
            "address": property_data.get("description", "Address not available"),
            "amenities": property_data.get("amenities", []),
            "images": [img.get("thumbnail", "") for img in property_data.get("images", [])],
            "reviews": property_data.get("reviews", 0),
            "hotel_class": property_data.get("hotel_class", "Not rated"),
            "location_rating": property_data.get("location_rating", 0)
        }
    
    def _get_mock_data(self):
        # Return mock hotel data in case of API errors
        return [
            {
                "name": "Marriott Downtown",
                "price": 229,
                "rating": 4.5,
                "address": "123 Main St",
                "amenities": ["Pool", "Fitness Center", "Restaurant", "Bar"],
                "images": [],
                "reviews": 0,
                "hotel_class": "4-star",
                "location_rating": 4.2
            },
            {
                "name": "Hilton Central",
                "price": 199,
                "rating": 4.3,
                "address": "456 Main St",
                "amenities": ["Free Wi-Fi", "Spa", "Gym"],
                "images": [],
                "reviews": 0,
                "hotel_class": "4-star",
                "location_rating": 4.0
            }
        ]

# class WeatherAPI:
#     def get_forecast(self, date, location):
#         mock_weather_data = {
#             "high_temp": 75,
#             "low_temp": 62,
#             "conditions": "Sunny",
#             "precipitation": 10
#         }
#         return mock_weather_data

# RAG System
class HoustonTravelRAG:
    def __init__(self):
        self.flight_api = FlightAPI()
        self.hotel_api = HotelAPI()
        # self.weather_api = WeatherAPI()

    def _get_base_locations(self, trip_type, travel_date):
        try:
            print(f"\nAttempting to get locations for trip type: {trip_type}")
            
            # Get flight deals data
            flight_deals = get_flight_deals()
            for deal in flight_deals:
                print(f"Title: {deal['title']}, Fare Availability: {deal['fare_availability']}")
            # Filter deals for Dallas origin and matching travel dates
            houston_deals = []
            for deal in flight_deals:
                if 'Dallas' in deal['title'] or 'DFW' in deal['title']:
                    # Check if the travel date falls within the fare availability period
                    fare_availability = deal['fare_availability']
                    if any(month in fare_availability for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                        houston_deals.append(deal)
            
            # Create context from flight deals
            deals_context = "\nAvailable Flight Deals from Dallas:\n"
            for deal in houston_deals:
                deals_context += f"- {deal['title']}\n"
                deals_context += f"  Fare Availability: {deal['fare_availability']}\n"
            
            prompt = f"""
            You are a helpful travel assistant. I need you to suggest 20 most popular destination cities for a {trip_type} trip.
            The user plans to travel on {travel_date}.
            
            {deals_context}
            
            Please consider the available flight deals that match the travel date when suggesting destinations, but also include other relevant destinations that match the trip type.
            
            For each city, provide:
            1. The city name
            2. The main airport code (3-letter IATA code)
            3. A brief list of activities or highlights related to {trip_type} that visitors can enjoy there
            
            Format your response as a JSON array with objects containing 'city', 'airport_code', and 'activities' fields.
            Do not include any explanations or text outside the JSON array.
            Do not include multiple JSON arrays - just one array with all destinations.
            
            Example format:
            [
                {{"city": "Paris", "airport_code": "CDG", "activities": "Visit the Eiffel Tower, explore the Louvre Museum, enjoy French cuisine"}},
                {{"city": "Tokyo", "airport_code": "NRT", "activities": "Visit temples, enjoy sushi, explore technology districts"}}
            ]
            """
            
            print("Sending prompt to model...")
            response = model.generate_content(prompt)
            output = response.text.strip()
            print(f"Raw model output: {output}")
            
            # Try to parse the response as JSON
            try:
                # Find the first complete JSON array in the response
                import re
                json_match = re.search(r'\[\s*\{.*?\}\s*\]', output, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    destinations = json.loads(json_str)
                    print(f"Successfully parsed {len(destinations)} destinations from JSON")
                    return destinations
                else:
                    print("No JSON array found in response")
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {str(e)}")
            
            # Fallback to line-by-line parsing if JSON parsing fails
            destinations = []
            current_destination = {}
            
            lines = output.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('DESTINATION'):
                    if current_destination and 'city' in current_destination and 'airport_code' in current_destination:
                        destinations.append(current_destination)
                    current_destination = {}
                elif line.startswith('CITY:'):
                    current_destination['city'] = line.replace('CITY:', '').strip()
                elif line.startswith('AIRPORT:'):
                    current_destination['airport_code'] = line.replace('AIRPORT:', '').strip()
                elif line.startswith('ACTIVITIES:'):
                    current_destination['activities'] = line.replace('ACTIVITIES:', '').strip()
            
            # Add the last destination if it exists
            if current_destination and 'city' in current_destination and 'airport_code' in current_destination:
                destinations.append(current_destination)
                    
            if destinations:
                print(f"Successfully parsed {len(destinations)} destinations from line-by-line parsing")
                return destinations
            else:
                print("Failed to parse any destinations from response")
                return [{"city": "Dallas", "airport_code": "DFW", "activities": "Default activities"}]
                
        except Exception as e:
            print(f"Error in _get_base_locations: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return [{"city": "Dallas", "airport_code": "DFW", "activities": "Default activities"}]

def format_prompt(context, query):
    # Check if we have a single flight or multiple flights
    if 'flights' in context:
        # Original format with multiple flights
        flight_details = "\n".join([
            f"- {f['airline']} {f['flight_no']}: Departs {f['departure']}, Arrives {f['arrival']} "
            f"({f['aircraft']}) - ${f['price']}"
            for f in context['flights']
        ])
        budget_analysis = (
            f"Estimated flight costs:\n"
            f"- Range: ${min(f['price'] for f in context['flights'])} to "
            f"${max(f['price'] for f in context['flights'])}"
        )
    else:
        # New format with a single selected flight
        flight = context
        flight_details = f"- {flight.get('airline', 'Unknown')} {flight.get('flight_no', 'N/A')}: " \
                        f"Departs {flight.get('departure', 'N/A')}, " \
                        f"Arrives {flight.get('arrival', 'N/A')} " \
                        f"({flight.get('aircraft', 'N/A')}) - ${flight.get('price', 0)}"
        
        budget_analysis = f"Flight cost: ${flight.get('price', 0)}"

    return f"""You are a helpful travel assistant. Create a detailed travel itinerary based on the following information:

LOCATION AND TYPE:
- Trip Type: {query['type']}
- Start Date: {query['date']}
- Maximum Budget: ${query.get('max_price', 300)}
- Priority: {query.get('priority', 'balanced options')}

AVAILABLE FLIGHTS:
{flight_details}

BUDGET ANALYSIS:
{budget_analysis}

Please create a detailed itinerary that includes:
1. Recommended flight with exact times
2. Total cost estimate
3. Packing list

Format your response as a clear, well-structured itinerary with these sections clearly marked."""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/flights')
def flights():
    return render_template('flights.html')

@app.route('/get_all_flights', methods=['POST'])
def get_all_flights():
    try:
        data = request.json
        vacation_type = data.get('vacation_type', '')
        travel_date = data.get('travel_date', '')
        
        # Ensure budget and vacation_length are numbers
        try:
            total_budget = float(data.get('budget', 300))
            vacation_length = int(data.get('vacation_length', 7))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid budget or vacation length"}), 400
        
        # Split budget: 60% for flights, 40% for hotels
        flight_budget = int(total_budget * 0.6)
        hotel_budget = int(total_budget * 0.4) 
        
        # Check if we already have the same trip details
        global trip_details, destination_data
        if (trip_details['vacation_type'] == vacation_type and 
            trip_details['travel_date'] == travel_date and 
            trip_details['budget'] == total_budget and
            trip_details['vacation_length'] == vacation_length and 
            destination_data):
            return jsonify({"destinations": list(destination_data.values())})
        
        # Update trip details
        trip_details = {
            'vacation_type': vacation_type,
            'travel_date': travel_date,
            'budget': total_budget,
            'vacation_length': vacation_length
        }
        
        # Get destination options
        rag = HoustonTravelRAG()
        destinations = rag._get_base_locations(vacation_type, travel_date)
        
        # Default origin airport (can be made configurable)
        origin_airport = "DFW"  # Dallas/Fort Worth International Airport
        
        # Fetch flights and hotels for each destination
        flight_api = FlightAPI()
        hotel_api = HotelAPI()
        for dest in destinations:
            # Fetch flights with flight budget
            dest['flights'] = flight_api.get_flights(
                origin=origin_airport,
                destination=dest['airport_code'],
                date=travel_date,
                max_price=flight_budget
            )
            
            # Calculate max price per night based on total hotel budget and vacation length
            max_price_per_night = int(hotel_budget / vacation_length)
            
            # Fetch hotels with calculated max price per night
            dest['hotels'] = hotel_api.get_hotels(
                date=travel_date,
                location=dest['city'],
                max_price=max_price_per_night,
                vacation_length=vacation_length
            )
        
        # Store the destinations data globally
        destination_data = {dest['city']: dest for dest in destinations}
        
        return jsonify({"destinations": destinations})
    except Exception as e:
        print(f"Error in get_all_flights: {str(e)}")
        return jsonify({"error": "An error occurred while processing the request"}), 500

@app.route('/get_destination_flights', methods=['POST'])
def get_destination_flights():
    data = request.json
    city = data.get('city', '')
    
    # Get the stored destination data
    global destination_data
    if city in destination_data:
        return jsonify({
            "flights": destination_data[city].get('flights', []),
            "hotels": destination_data[city].get('hotels', [])
        })
    else:
        return jsonify({"flights": [], "hotels": []})

@app.route('/destination_flights')
def destination_flights():
    city = request.args.get('city', '')
    vacation_type = request.args.get('vacation_type', '')
    travel_date = request.args.get('travel_date', '')
    budget = request.args.get('budget', 300)
    
    return render_template('destination_flights.html',
                         city=city,
                         vacation_type=vacation_type,
                         travel_date=travel_date,
                         budget=budget)

@app.route('/generate_itinerary', methods=['GET'])
def generate_itinerary_get():
    city = request.args.get('city', '')
    airport_code = request.args.get('airport_code', '')
    flight_data = request.args.get('flight_data', '{}')
    
    try:
        flight = json.loads(flight_data)
    except:
        flight = {}
    
    # Get other parameters from session or default values
    vacation_type = request.args.get('vacation_type', 'vacation')
    travel_date = request.args.get('travel_date', datetime.now().strftime("%Y-%m-%d"))
    budget = request.args.get('budget', 300)
    
    # Create a context object with the flight data
    selected_flight = {
        'city': city,
        'airport_code': airport_code,
        'airline': flight.get('airline', 'Unknown'),
        'flight_no': flight.get('flight_no', 'N/A'),
        'departure': flight.get('departure', 'N/A'),
        'arrival': flight.get('arrival', 'N/A'),
        'duration': flight.get('duration', 'N/A'),
        'price': flight.get('price', 0),
        'aircraft': flight.get('aircraft', 'N/A')
    }
    
    prompt = format_prompt(selected_flight, {
        "type": vacation_type,
        "date": travel_date,
        "max_price": budget,
        "selected_flight": selected_flight
    })
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        return render_template('itinerary.html', 
                              itinerary=response_text,
                              city=city,
                              vacation_type=vacation_type,
                              travel_date=travel_date)
    except Exception as e:
        print(f"Error generating itinerary: {str(e)}")
        return render_template('itinerary.html', 
                              itinerary="Sorry, there was an error generating your itinerary. Please try again.",
                              city=city,
                              vacation_type=vacation_type,
                              travel_date=travel_date)

@app.route('/generate_itinerary', methods=['POST'])
def generate_itinerary():
    data = request.json
    vacation_type = data.get('vacation_type', '')
    travel_date = data.get('travel_date', '')
    budget = data.get('budget', 300)
    selected_flight = data.get('selected_flight', {})
    
    prompt = format_prompt(selected_flight, {
        "type": vacation_type,
        "date": travel_date,
        "max_price": budget,
        "selected_flight": selected_flight
    })
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        return jsonify({"itinerary": response_text})
    except Exception as e:
        print(f"Error generating itinerary: {str(e)}")
        return jsonify({"itinerary": "Sorry, there was an error generating your itinerary. Please try again."})

if __name__ == '__main__':
    app.run(debug=True)