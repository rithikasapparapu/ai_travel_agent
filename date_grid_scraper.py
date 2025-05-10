from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
import time
from datetime import datetime, timedelta
import sys
import os
import random

def create_flight_search_url(source, destination, start_date, end_date):
    base_url = "https://www.google.com/travel/flights"
    return f"{base_url}?q=flights%20{source}%20to%20{destination}%20{start_date}%20{end_date}"

def random_sleep(min_seconds=2, max_seconds=5):
    time.sleep(random.uniform(min_seconds, max_seconds))

def wait_for_element(driver, selector, timeout=30):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return element
    except TimeoutException:
        return None

def scroll_page(driver):
    # Scroll in smaller increments
    total_height = int(driver.execute_script("return document.body.scrollHeight"))
    for i in range(0, total_height, 100):
        driver.execute_script(f"window.scrollTo(0, {i});")
        random_sleep(0.5, 1)

def scrape_google_flights(source, destination, start_date, end_date):
    # Set up Chrome options
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")  # Removing headless mode for better success rate
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Add more realistic user agent and additional options
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument("--start-maximized")
    
    # Initialize return data structure
    date_grid_data = {
        'source': source,
        'destination': destination,
        'search_dates': {
            'start': start_date,
            'end': end_date
        },
        'prices': {}
    }
    
    try:
        # Initialize the Chrome WebDriver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Set user agent and other properties to make automation harder to detect
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Additional settings to avoid detection
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        # Navigate to Google Flights
        url = create_flight_search_url(source, destination, start_date, end_date)
        print(f"\nAccessing URL: {url}")
        driver.get(url)
        
        # Initial wait for page load
        print("Waiting for initial page load...")
        random_sleep(10, 12)
        
        # Wait for the main content to load
        print("Waiting for main content to load...")
        wait = WebDriverWait(driver, 20)
        
        # Wait for and click the "Date grid" button using the specific selectors
        print("\nLooking for Date grid button...")
        date_grid_selectors = [
            'button[jsname="KqtnKd"]',  # Using the specific jsname
            'button.VfPpkd-LgbsSe[jsname="KqtnKd"]',  # Using class and jsname
            'button[jscontroller="soHxf"]',  # Using the jscontroller
            'button.ksBjEc.lKxP2d',  # Using specific classes
            'button[data-idom-class*="ksBjEc"]',  # Using data-idom-class
            'button span[jsname="V67aGc"]',  # Using the span inside the button
            'button:has(span:contains("Date grid"))'  # Using the text content
        ]
        
        date_grid_button = None
        for selector in date_grid_selectors:
            try:
                print(f"Trying selector: {selector}")
                elements = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                if elements:
                    print(f"Found {len(elements)} elements with selector: {selector}")
                    for element in elements:
                        try:
                            # Check if this is the date grid button by looking for the text
                            if "Date grid" in element.text:
                                date_grid_button = element
                                print(f"Found Date grid button with selector: {selector}")
                                break
                        except:
                            continue
                if date_grid_button:
                    break
            except Exception as e:
                print(f"Selector {selector} failed: {str(e)}")
                continue
        
        if date_grid_button:
            # Click the Date grid button
            print("Clicking Date grid button...")
            try:
                # Wait for the button to be clickable
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                # Try regular click first
                date_grid_button.click()
                print("Successfully clicked the button")
            except Exception as e:
                print(f"Regular click failed: {str(e)}")
                try:
                    # Try JavaScript click if regular click fails
                    driver.execute_script("arguments[0].click();", date_grid_button)
                    print("Successfully clicked the button using JavaScript")
                except Exception as e:
                    print(f"JavaScript click failed: {str(e)}")
            
            # Wait for the date grid to appear
            print("Waiting for date grid to load...")
            random_sleep(5, 7)
            
            # Try to find price elements specifically
            print("\nLooking for price elements...")
            price_selectors = [
                'div[aria-label*="$"]',  # Elements with price in aria-label
                'div[jsname] span',  # Spans inside named elements
                'div[role="button"] span',  # Spans inside buttons
                'div[role="gridcell"] span',  # Spans inside grid cells
                'div[role="gridcell"] div',  # Divs inside grid cells
                'div[jsaction]',  # Elements with actions
                'div[data-price]',  # Elements with price data
                'div[class*="price"]',  # Elements with price in class name
                'div[class*="cost"]'  # Elements with cost in class name
            ]
            
            # Try multiple times to find prices
            max_retries = 3
            retry_count = 0
            price_elements = []
            
            while retry_count < max_retries and not price_elements:
                print(f"\nAttempt {retry_count + 1} to find prices...")
                
                # Try to trigger price loading
                try:
                    # Scroll around to trigger loading
                    driver.execute_script("""
                        window.scrollTo(0, 0);
                        setTimeout(() => window.scrollTo(0, 100), 500);
                        setTimeout(() => window.scrollTo(0, 0), 1000);
                    """)
                    random_sleep(2, 3)
                    
                    # Try each selector
                    for selector in price_selectors:
                        try:
                            print(f"Trying price selector: {selector}")
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                print(f"Found {len(elements)} potential price elements")
                                # Check each element for price content
                                for element in elements:
                                    try:
                                        text = element.text.strip()
                                        aria_label = element.get_attribute('aria-label')
                                        title = element.get_attribute('title')
                                        
                                        # Print all available information
                                        print(f"\nElement info:")
                                        print(f"Text: '{text}'")
                                        print(f"Aria-label: '{aria_label}'")
                                        print(f"Title: '{title}'")
                                        
                                        # Try to get computed styles
                                        try:
                                            style = driver.execute_script("""
                                                let style = window.getComputedStyle(arguments[0]);
                                                return {
                                                    display: style.display,
                                                    visibility: style.visibility,
                                                    opacity: style.opacity
                                                };
                                            """, element)
                                            print(f"Styles: {style}")
                                        except:
                                            pass
                                        
                                        # Try to find associated date
                                        date = None
                                        if aria_label:
                                            # Extract special labels like "cheapest price" or "low price"
                                            if "cheapest price" in aria_label.lower():
                                                price_type = "Cheapest Price"
                                            elif "low price" in aria_label.lower():
                                                price_type = "Low Price"
                                            
                                            # Extract date range from aria-label
                                            parts = aria_label.split(',')
                                            for part in parts:
                                                if "to" in part and any(month in part for month in ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]):
                                                    date = part.strip()
                                                    break
                                        
                                        # Check for price content
                                        content = [text, aria_label, title]
                                        if any('$' in str(c) for c in content if c):
                                            price_elements.append(element)
                                            print("Found element with price!")
                                    except Exception as e:
                                        print(f"Failed to process element: {str(e)}")
                                        continue
                        except Exception as e:
                            print(f"Selector {selector} failed: {str(e)}")
                            continue
                        
                        if price_elements:
                            break
                except Exception as e:
                    print(f"Failed to trigger price loading: {str(e)}")
                
                if not price_elements:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"No prices found, waiting before retry...")
                        random_sleep(3, 5)
            
            if price_elements:
                print(f"\nFound {len(price_elements)} elements with prices")
                price_data = []
                
                for element in price_elements:
                    try:
                        # Get the price
                        price = element.text.strip()
                        if not price:
                            price = element.get_attribute('aria-label')
                        if not price:
                            price = element.get_attribute('title')
                        
                        # Get the date from aria-label
                        aria_label = element.get_attribute('aria-label')
                        date = None
                        price_type = None
                        
                        if aria_label:
                            # Extract special labels like "cheapest price" or "low price"
                            if "cheapest price" in aria_label.lower():
                                price_type = "Cheapest Price"
                            elif "low price" in aria_label.lower():
                                price_type = "Low Price"
                            
                            # Extract date range from aria-label
                            parts = aria_label.split(',')
                            for part in parts:
                                if "to" in part and any(month in part for month in ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]):
                                    date = part.strip()
                                    break
                        
                        if price and '$' in price:
                            # Clean up the price string to just show the amount
                            price = price.split(',')[0].strip()
                            
                            # Add to price data list
                            price_data.append({
                                'date_range': date if date else "Unknown Date",
                                'price': price,
                                'price_type': price_type
                            })
                            
                            # Add to the return data structure
                            if date:
                                date_grid_data['prices'][date] = {
                                    'price': price,
                                    'price_type': price_type
                                }
                            
                            # Format the output message
                            output_msg = f"Found price: {price}"
                            if price_type:
                                output_msg += f" ({price_type})"
                            if date:
                                output_msg += f" for dates: {date}"
                            print(output_msg)
                    except Exception as e:
                        print(f"Failed to process price element: {str(e)}")
                        continue
                
                # After collecting all data, sort and display it in a more organized way
                if price_data:
                    print("\nPrice Information:")
                    print("=" * 50)
                    
                    # Sort by price (removing '$' and converting to float)
                    sorted_prices = sorted(price_data, key=lambda x: float(x['price'].replace('$', '')))
                    
                    # Group by date range
                    date_groups = {}
                    for item in sorted_prices:
                        date_range = item['date_range']
                        if date_range not in date_groups:
                            date_groups[date_range] = []
                        date_groups[date_range].append(item)
                    
                    # Display grouped results
                    for date_range, prices in date_groups.items():
                        print(f"\nDate Range: {date_range}")
                        print("-" * 30)
                        for price_info in prices:
                            price_str = price_info['price']
                            if price_info['price_type']:
                                price_str += f" ({price_info['price_type']})"
                            print(f"Price: {price_str}")
                        print("-" * 30)
                else:
                    print("\nNo valid price data could be extracted.")
            else:
                print("\nNo price elements found after all attempts.")
        else:
            print("\nCould not find the Date grid button.")
        
        # Save the page source for debugging
        output_file = 'google_flights_response.html'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"\nResponse has been saved to {os.path.abspath(output_file)}")
        
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        print("\nTroubleshooting tips:")
        print("1. Check your internet connection")
        print("2. Verify that the dates are valid and in the future")
        print("3. Try using different city/airport names")
        print("4. Make sure Chrome is installed on your system")
        print("5. Try running without headless mode")
    finally:
        if 'driver' in locals():
            driver.quit()
    
    return date_grid_data

def main():
    print("Google Flights Scraper")
    print("--------------------------------")
    
    # Hard-coded values for testing
    source = "New York"
    destination = "London"
    
    # Calculate dates 6 months from now
    future_date = datetime.now() + timedelta(days=180)
    start_date = future_date.strftime('%Y-%m-%d')
    end_date = (future_date + timedelta(days=14)).strftime('%Y-%m-%d')
    
    print(f"Using test values:")
    print(f"Source: {source}")
    print(f"Destination: {destination}")
    print(f"Start date: {start_date}")
    print(f"End date: {end_date}")
    
    # Get the date grid data
    date_grid_data = scrape_google_flights(source, destination, start_date, end_date)
    
    # Print the structured data
    print("\nStructured Date Grid Data:")
    print("=" * 50)
    print(f"Source: {date_grid_data['source']}")
    print(f"Destination: {date_grid_data['destination']}")
    print(f"Search Dates: {date_grid_data['search_dates']}")
    print("\nPrices:")
    for date, price_info in date_grid_data['prices'].items():
        print(f"Date: {date}")
        print(f"  Price: {price_info['price']}")
        if price_info['price_type']:
            print(f"  Type: {price_info['price_type']}")
        print("-" * 30)

if __name__ == "__main__":
    main() 