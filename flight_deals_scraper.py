import requests
from bs4 import BeautifulSoup
import time

def get_fare_availability_and_date(article_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(article_url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get posted date from header
        posted_date = ""
        header = soup.find('header', class_='entry-header')
        if header:
            # Try different possible date elements
            date_element = header.find('time', class_='entry-date published')
            if not date_element:
                date_element = header.find('time', class_='entry-date')
            if not date_element:
                date_element = header.find('span', class_='date')
            if not date_element:
                date_element = header.find('div', class_='posted-on')
            
            if date_element:
                posted_date = date_element.get_text(strip=True)
        
        # Find the article content
        article_content = soup.find('div', class_='entry-content')
        if not article_content:
            return "Article content not found", posted_date
            
        # Find all h2 headings
        h2_headings = article_content.find_all('h2')
        
        # Look for the h2 containing fare availability
        for h2 in h2_headings:
            if 'Fare Availability' in h2.text:
                # Get all content until the next h2
                content = []
                current = h2.find_next_sibling()
                while current and current.name != 'h2':
                    text = current.get_text(strip=True)
                    if text:  # Only add non-empty text
                        content.append(text)
                    current = current.find_next_sibling()
                
                return "\n".join(content), posted_date
        
        return "Fare Availability information not found", posted_date
        
    except Exception as e:
        return f"Error fetching fare availability: {str(e)}", ""

def get_flight_deals():
    url = "https://www.theflightdeal.com/category/flight-deals/dallas/"
    flight_deals = []
    
    try:
        # Fetch webpage content with headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Check for HTTP errors
        
        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all article elements containing flight deals
        articles = soup.find_all('article')
        
        # Extract and clean text from each deal
        for article in articles:
            # Get the title
            title = article.find('h2', class_='entry-title')
            if title and title.a:
                deal_title = title.a.text.strip()
                article_url = title.a['href']  # Get the article URL
                
                # Get the content
                content = article.find('div', class_='entry-content')
                if content:
                    deal_text = content.get_text(separator=' ', strip=True)
                    
                    # Get fare availability and posted date
                    fare_info, posted_date = get_fare_availability_and_date(article_url)
                    
                    # Add deal to list
                    flight_deals.append({
                        'title': deal_title,
                        'content': deal_text[:200] + "...",
                        'fare_availability': fare_info,
                        'posted_date': posted_date,
                        'url': article_url
                    })
                    
                    # Add a small delay to be respectful to the server
                    time.sleep(2)  # Increased delay to be more respectful
        
        return flight_deals
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

if __name__ == "__main__":
    # Print flight deals when run directly
    print("\nRecent Flight Deals:")
    print("-" * 80)
    
    deals = get_flight_deals()
    print(f"Found {len(deals)} articles")
    
    for deal in deals:
        print(f"Title: {deal['title']}")
        print(f"Content: {deal['content']}")
        print("\nFare Availability:")
        print(deal['fare_availability'])
        print(f"\nPosted on: {deal['posted_date'] if deal['posted_date'] else 'Date not found'}")
        print("-" * 80)