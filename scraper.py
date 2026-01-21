import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional

@dataclass
class PriceInfo:
    price: Optional[float]
    regular_price: Optional[float]
    on_sale: bool
    product_name: Optional[str]
    error: Optional[str] = None

def extract_price(price_text: str) -> Optional[float]:
    """Extract numeric price from text like '$4.99' or '4.99/lb'"""
    if not price_text:
        return None
    match = re.search(r'\$?([\d,]+\.?\d*)', price_text.replace(',', ''))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None

def is_valid_url(url: str) -> bool:
    """Check if URL is a valid Whole Foods or Amazon Whole Foods URL"""
    if not url:
        return False
    url_lower = url.lower()
    return 'wholefoodsmarket.com' in url_lower or ('amazon.com' in url_lower and 'wholefoods' in url_lower)

def scrape_whole_foods_price(url: str) -> PriceInfo:
    """
    Scrape price information from a Whole Foods or Amazon Whole Foods product page.
    Returns PriceInfo with current price, regular price, and sale status.
    """
    if not is_valid_url(url):
        return PriceInfo(
            price=None,
            regular_price=None,
            on_sale=False,
            product_name=None,
            error="Invalid URL. Use a wholefoodsmarket.com or Amazon Whole Foods URL"
        )

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        is_amazon = 'amazon.com' in url.lower()
        price = None
        regular_price = None
        on_sale = False
        product_name = None

        if is_amazon:
            # Get product name
            title_elem = soup.find('span', {'id': 'productTitle'})
            if title_elem:
                product_name = title_elem.get_text().strip()

            # Try multiple price selectors for Amazon
            # Method 1: Look for price in corePrice section
            core_price = soup.find('div', {'id': 'corePrice_feature_div'})
            if core_price:
                price_span = core_price.find('span', {'class': 'a-offscreen'})
                if price_span:
                    price = extract_price(price_span.get_text())

            # Method 2: Look for apex price
            if not price:
                apex_price = soup.find('span', {'id': 'priceblock_ourprice'})
                if apex_price:
                    price = extract_price(apex_price.get_text())

            # Method 3: Look for any a-price span
            if not price:
                price_elem = soup.find('span', {'class': 'a-price'})
                if price_elem:
                    offscreen = price_elem.find('span', {'class': 'a-offscreen'})
                    if offscreen:
                        price = extract_price(offscreen.get_text())

            # Method 4: Search for price pattern in page
            if not price:
                # Look for price in the whole page text
                price_pattern = re.search(r'\$(\d+\.?\d*)', response.text)
                if price_pattern:
                    price = float(price_pattern.group(1))

            # Check for sale
            was_price = soup.find('span', {'class': 'a-text-price'})
            if was_price:
                was_offscreen = was_price.find('span', {'class': 'a-offscreen'})
                if was_offscreen:
                    regular = extract_price(was_offscreen.get_text())
                    if regular and price and regular > price:
                        on_sale = True
                        regular_price = regular

            savings = soup.find('span', {'class': 'savingsPercentage'})
            if savings:
                on_sale = True

        else:
            # Whole Foods Market website
            title_elem = soup.find('h1')
            if title_elem:
                product_name = title_elem.get_text().strip()

            price_elem = soup.find(attrs={'data-testid': 'product-price'})
            if price_elem:
                price = extract_price(price_elem.get_text())

            if not price:
                price_elem = soup.find(class_=re.compile('price'))
                if price_elem:
                    price = extract_price(price_elem.get_text())

        if price is None:
            return PriceInfo(
                price=None,
                regular_price=None,
                on_sale=False,
                product_name=product_name,
                error="Could not extract price. The website may require JavaScript or is blocking automated access."
            )

        return PriceInfo(
            price=price,
            regular_price=regular_price if on_sale else price,
            on_sale=on_sale,
            product_name=product_name,
            error=None
        )

    except requests.RequestException as e:
        return PriceInfo(
            price=None,
            regular_price=None,
            on_sale=False,
            product_name=None,
            error=f"Failed to fetch page: {str(e)}"
        )
    except Exception as e:
        return PriceInfo(
            price=None,
            regular_price=None,
            on_sale=False,
            product_name=None,
            error=f"Failed to scrape: {str(e)}"
        )

def check_all_prices(items: list) -> dict:
    """
    Check prices for a list of items with Whole Foods URLs.
    Returns a dict mapping item_id to PriceInfo.
    """
    import time
    results = {}
    for item in items:
        if item.get('whole_foods_url'):
            print(f"Checking price for: {item['name']}")
            results[item['id']] = scrape_whole_foods_price(item['whole_foods_url'])
            time.sleep(2)  # Be polite to the server
    return results

if __name__ == "__main__":
    test_url = input("Enter a Whole Foods product URL to test: ").strip()
    if test_url:
        print("Scraping...")
        result = scrape_whole_foods_price(test_url)
        print(f"\nProduct: {result.product_name}")
        print(f"Price: ${result.price}")
        print(f"Regular Price: ${result.regular_price}")
        print(f"On Sale: {result.on_sale}")
        if result.error:
            print(f"Error: {result.error}")
