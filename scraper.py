import re
import time
from playwright.sync_api import sync_playwright
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
    return 'wholefoodsmarket.com' in url or ('amazon.com' in url and 'wholefoods' in url.lower())

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

    is_amazon = 'amazon.com' in url

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()

            # Navigate to the product page
            page.goto(url, wait_until='networkidle', timeout=30000)
            time.sleep(2)  # Allow dynamic content to load

            price = None
            regular_price = None
            on_sale = False
            product_name = None

            # Try to get product name
            try:
                if is_amazon:
                    name_elem = page.query_selector('#productTitle, #title, h1#title span')
                else:
                    name_elem = page.query_selector('h1[data-testid="product-title"], h1.product-name, h1')
                if name_elem:
                    product_name = name_elem.inner_text().strip()
            except:
                pass

            # Try multiple selectors for price
            if is_amazon:
                # Amazon price selectors
                price_selectors = [
                    '.a-price .a-offscreen',
                    '#priceblock_ourprice',
                    '#priceblock_dealprice',
                    '.a-price-whole',
                    '#corePrice_feature_div .a-offscreen',
                    '#corePriceDisplay_desktop_feature_div .a-offscreen',
                    'span.a-price span.a-offscreen',
                    '[data-a-color="price"] .a-offscreen',
                ]
            else:
                # Whole Foods direct site selectors
                price_selectors = [
                    '[data-testid="product-price"]',
                    '.price-value',
                    '.product-price',
                    '.regular-price',
                    '[class*="price"]',
                    '.w-price',
                ]

            for selector in price_selectors:
                try:
                    price_elem = page.query_selector(selector)
                    if price_elem:
                        price_text = price_elem.inner_text()
                        extracted = extract_price(price_text)
                        if extracted:
                            price = extracted
                            break
                except:
                    continue

            # Check for sale price indicators
            if is_amazon:
                sale_selectors = [
                    '.a-text-price .a-offscreen',  # Strikethrough price on Amazon
                    '#priceblock_saleprice',
                    '.savingsPercentage',
                    '[data-a-strike="true"]',
                ]
            else:
                sale_selectors = [
                    '[data-testid="sale-price"]',
                    '.sale-price',
                    '.promo-price',
                    '[class*="sale"]',
                    '.was-price',
                ]

            for selector in sale_selectors:
                try:
                    sale_elem = page.query_selector(selector)
                    if sale_elem:
                        on_sale = True
                        # Try to find the original/regular price
                        was_price_elem = page.query_selector('.was-price, .original-price, [class*="regular"]')
                        if was_price_elem:
                            regular_price = extract_price(was_price_elem.inner_text())
                        break
                except:
                    continue

            # Check page content for sale indicators
            try:
                page_content = page.content().lower()
                if 'sale' in page_content or 'deal' in page_content or 'save' in page_content:
                    if not on_sale:
                        # Double-check by looking for strikethrough prices
                        strike_elem = page.query_selector('s, strike, del, [style*="line-through"]')
                        if strike_elem:
                            on_sale = True
                            regular_price = extract_price(strike_elem.inner_text())
            except:
                pass

            browser.close()

            if price is None:
                return PriceInfo(
                    price=None,
                    regular_price=None,
                    on_sale=False,
                    product_name=product_name,
                    error="Could not extract price from page. The page structure may have changed."
                )

            return PriceInfo(
                price=price,
                regular_price=regular_price if on_sale else price,
                on_sale=on_sale,
                product_name=product_name,
                error=None
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
    results = {}
    for item in items:
        if item.get('whole_foods_url'):
            print(f"Checking price for: {item['name']}")
            results[item['id']] = scrape_whole_foods_price(item['whole_foods_url'])
            time.sleep(2)  # Be polite to the server
    return results

if __name__ == "__main__":
    # Test with a sample URL
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
