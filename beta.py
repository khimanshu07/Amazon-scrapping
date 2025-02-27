from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
import csv
import time
import re

def scrape_amazon_products(url):
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode (no browser UI)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Add user agent to avoid detection as a bot
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
    # Initialize the WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    
    # List to store product details
    products = []
    
    try:
        # Navigate to the URL
        driver.get(url)
        print("Navigated to URL successfully")
        
        # Wait for the page to load
        time.sleep(5)
        
        # Create a WebDriverWait instance
        wait = WebDriverWait(driver, 15)
        
        # Wait for product grid to be present
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-result-item")))
        
        # Find all product items
        product_items = driver.find_elements(By.CSS_SELECTOR, "div.s-result-item[data-component-type='s-search-result']")
        print(f"Found {len(product_items)} product items")
        
        # Loop through each product to collect product links and basic info
        product_links = []
        for item in product_items:
            try:
                # Dictionary to store product details
                product_details = {}
                
                # Extract product name
                try:
                    # First attempt - most common selector
                    product_name_element = item.find_element(By.CSS_SELECTOR, "h2 .a-link-normal")
                    product_details["Product Name"] = product_name_element.text.strip()
                    
                    # Get product link
                    product_link = product_name_element.get_attribute("href")
                    product_details["link"] = product_link
                except (NoSuchElementException, StaleElementReferenceException):
                    try:
                        # Second attempt - direct span in anchor
                        product_name_element = item.find_element(By.CSS_SELECTOR, "h2 a")
                        product_details["Product Name"] = product_name_element.text.strip()
                        product_link = product_name_element.get_attribute("href")
                        product_details["link"] = product_link
                    except (NoSuchElementException, StaleElementReferenceException):
                        try:
                            # Third attempt - find any link in the product card with title attribute
                            product_links_elements = item.find_elements(By.CSS_SELECTOR, "a.a-link-normal")
                            for link_element in product_links_elements:
                                if link_element.get_attribute("title") or link_element.text:
                                    product_details["Product Name"] = link_element.get_attribute("title") or link_element.text.strip()
                                    product_link = link_element.get_attribute("href")
                                    product_details["link"] = product_link
                                    break
                        except (NoSuchElementException, StaleElementReferenceException):
                            product_details["Product Name"] = "N/A"
                            product_details["link"] = None
                
                # Extract price
                try:
                    price_element = item.find_element(By.CSS_SELECTOR, ".a-price-whole")
                    price_text = price_element.text.strip()
                    # Clean price by removing commas and converting to integer
                    product_details["Price"] = price_text
                except (NoSuchElementException, StaleElementReferenceException):
                    product_details["Price"] = "Out of Stock"
                
                # Extract rating
                try:
                    rating_element = item.find_element(By.CSS_SELECTOR, "i.a-icon-star-small")
                    rating_text = rating_element.get_attribute("class")
                    # Extract rating value from class name using regex
                    rating_match = re.search(r'a-star-small-(\d+)', rating_text)
                    if rating_match:
                        # Convert the rating from format like "45" to "4.5"
                        rating_value = int(rating_match.group(1)) / 10
                        product_details["Rating"] = str(rating_value)
                    else:
                        product_details["Rating"] = "No Rating"
                except (NoSuchElementException, StaleElementReferenceException):
                    try:
                        # Alternative rating selector
                        rating_element = item.find_element(By.CSS_SELECTOR, ".a-icon-star")
                        rating_text = rating_element.get_attribute("class")
                        rating_match = re.search(r'a-star-(\d+)', rating_text)
                        if rating_match:
                            rating_value = int(rating_match.group(1)) / 10
                            product_details["Rating"] = str(rating_value)
                        else:
                            product_details["Rating"] = "No Rating"
                    except (NoSuchElementException, StaleElementReferenceException):
                        product_details["Rating"] = "No Rating"
                
                # Add product to our list if we have a valid product name and link
                if product_details["Product Name"] != "N/A" and product_details["link"]:
                    product_links.append(product_details)
                
            except Exception as e:
                print(f"Error scraping product listing: {str(e)}")
                continue
        
        print(f"Collected {len(product_links)} product links to visit")
        
        # Now visit each product page to get detailed seller information
        for i, product in enumerate(product_links):
            try:
                print(f"Visiting product page {i+1}/{len(product_links)}: {product['Product Name'][:30]}...")
                
                if product["link"]:
                    # Navigate to the product page
                    driver.get(product["link"])
                    time.sleep(3)  # Wait for page to load
                    
                    # Extract seller name from product page
                    product["Seller Name"] = "Unknown Seller"
                    
                    # Try multiple approaches to find seller name
                    try:
                        # Method 1: Check "Sold by" section (most common)
                        sold_by_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Sold by:') or contains(text(), 'Sold by')]")
                        if sold_by_elements:
                            for element in sold_by_elements:
                                # Get the text after "Sold by:"
                                element_text = element.text
                                if "Sold by:" in element_text:
                                    seller = element_text.split("Sold by:")[1].strip()
                                    # Remove any "and" or additional text after the seller name
                                    seller = seller.split(" and ")[0].strip()
                                    seller = seller.split("\n")[0].strip()
                                    product["Seller Name"] = seller
                                    break
                                elif "Sold by" in element_text:
                                    # Try to find a link within this element or its parent
                                    parent = element.find_element(By.XPATH, "./..")
                                    seller_links = parent.find_elements(By.TAG_NAME, "a")
                                    if seller_links:
                                        product["Seller Name"] = seller_links[0].text.strip()
                                        break
                    except Exception as e:
                        print(f"Method 1 error: {str(e)}")
                    
                    # Method 2: Look for merchant info
                    if product["Seller Name"] == "Unknown Seller":
                        try:
                            merchant_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Merchant') or contains(@id, 'merchant')]")
                            if merchant_elements:
                                for element in merchant_elements:
                                    # Look for seller in this element or nearby
                                    element_text = element.text
                                    if ":" in element_text:
                                        seller = element_text.split(":")[1].strip()
                                        product["Seller Name"] = seller
                                        break
                        except Exception as e:
                            print(f"Method 2 error: {str(e)}")
                    
                    # Method 3: Check for Amazon as seller
                    if product["Seller Name"] == "Unknown Seller":
                        try:
                            # Check if "Ships from" and "Sold by" mentions Amazon
                            ships_from_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Ships from') or contains(text(), 'Sold by')]")
                            for element in ships_from_elements:
                                if "Amazon" in element.text:
                                    product["Seller Name"] = "Amazon"
                                    break
                        except Exception as e:
                            print(f"Method 3 error: {str(e)}")
                    
                    # Method 4: Look for a specific seller section
                    if product["Seller Name"] == "Unknown Seller":
                        try:
                            # Look for elements that are likely to contain seller info
                            potential_seller_elements = driver.find_elements(By.CSS_SELECTOR, "#sellerProfileTriggerId, .mbcMerchantName, #merchant-info")
                            if potential_seller_elements:
                                product["Seller Name"] = potential_seller_elements[0].text.strip()
                        except Exception as e:
                            print(f"Method 4 error: {str(e)}")
                    
                    print(f"Found seller: {product['Seller Name']}")
                
                # Add complete product to final list
                product_data = {
                    "Product Name": product["Product Name"],
                    "Price": product["Price"],
                    "Rating": product["Rating"],
                    "Seller Name": product["Seller Name"]
                }
                products.append(product_data)
                
            except Exception as e:
                print(f"Error processing product page: {str(e)}")
                # Still add the product with unknown seller
                product_data = {
                    "Product Name": product["Product Name"],
                    "Price": product["Price"],
                    "Rating": product["Rating"],
                    "Seller Name": "Error retrieving seller"
                }
                products.append(product_data)
        
        print(f"Successfully scraped {len(products)} products with detailed seller information")
        return products
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return products
    
    finally:
        # Always close the driver
        driver.quit()
        print("WebDriver closed")

def save_to_csv(products, filename="amazon_products.csv"):
    
    # Define field names
    fieldnames = ["Product Name", "Price", "Rating", "Seller Name"]
    
    try:
        # Write to CSV file
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Write product details
            for product in products:
                writer.writerow(product)
                
        print(f"Successfully saved data to {filename}")
        
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")

def main():
    """
    Main function to run the scraper
    """
    # URL to scrape
    url = "https://www.amazon.in/s?rh=n%3A6612025031&fs=true&ref=lp_6612025031_sar"
    
    print("Starting Amazon product scraper with product page navigation...")
    
    # Scrape products
    products = scrape_amazon_products(url)
    
    # Save products to CSV
    if products:
        save_to_csv(products)
        print(f"Saved {len(products)} products to CSV file")
    else:
        print("No products found to save.")

if __name__ == "__main__":
    main()