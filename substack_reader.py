from typing import Any, Optional
import json
import requests
import re
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server for Trade Companion by Adam Mancini
mcp = FastMCP("trade_companion_reader")

# Path to stored cookies
COOKIES_FILE = Path("substack_cookies.json")

# Trade Companion Substack URL
TRADE_COMPANION_URL = "https://tradecompanion.substack.com"

def get_cookies_dict() -> dict:
    """Load cookies from file and convert to requests format."""
    if not COOKIES_FILE.exists():
        return {}
    
    # Load cookies from file
    cookies_data = json.loads(COOKIES_FILE.read_text())
    
    # Convert cookies to requests format (name: value dict)
    return {cookie['name']: cookie['value'] for cookie in cookies_data}

def get_headers() -> dict:
    """Return headers that mimic a browser request."""
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://substack.com/',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'cache-control': 'max-age=0',
        'priority': 'u=0, i'
    }

def clean_html_text(html_text: str) -> str:
    """Remove HTML tags and clean up text."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_text)
    
    # Replace HTML entities
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)
    
    return text.strip()

def fetch_substack_article_text(url: str) -> Optional[dict[str, Any]]:
    """
    Fetch a Trade Companion article by Adam Mancini and extract plain text content.
    Returns the article title, author, date, and plain text content.
    """
    cookies = get_cookies_dict()
    headers = get_headers()
    
    try:
        # Make the request
        response = requests.get(url, cookies=cookies, headers=headers)
        response.raise_for_status()
        
        # Extract title
        title_match = re.search(r'<h1[^>]*?>(.*?)</h1>', response.text, re.DOTALL)
        title = clean_html_text(title_match.group(1)) if title_match else "Unknown Title"
        
        # Set author to Adam Mancini
        author = "Adam Mancini"
        
        # Extract date
        date_pattern = r'<time[^>]*?datetime="([^"]+)"'
        date_match = re.search(date_pattern, response.text)
        date = date_match.group(1) if date_match else ""
        
        # Extract article content
        # First, try to find the article container
        content_pattern = r'<div[^>]*?class="[^"]*?body[^"]*?"[^>]*?>(.*?)</div>\s*<(footer|div\s+class="[^"]*?comments)'
        content_match = re.search(content_pattern, response.text, re.DOTALL)
        
        if not content_match:
            # Try alternative pattern
            content_pattern = r'<article[^>]*?>(.*?)</article>'
            content_match = re.search(content_pattern, response.text, re.DOTALL)
        
        if content_match:
            html_content = content_match.group(1)
            
            # Remove scripts, styles, and other non-content elements
            html_content = re.sub(r'<script[^>]*?>.*?</script>', '', html_content, flags=re.DOTALL)
            html_content = re.sub(r'<style[^>]*?>.*?</style>', '', html_content, flags=re.DOTALL)
            html_content = re.sub(r'<svg[^>]*?>.*?</svg>', '', html_content, flags=re.DOTALL)
            html_content = re.sub(r'<figure[^>]*?>.*?</figure>', '', html_content, flags=re.DOTALL)
            
            # Extract text from paragraphs and headings
            text_blocks = []
            
            # Get headings
            for i in range(2, 7):  # h2 through h6
                headings = re.findall(f'<h{i}[^>]*?>(.*?)</h{i}>', html_content, re.DOTALL)
                for h in headings:
                    text_blocks.append(f"{'#' * (i-1)} {clean_html_text(h)}")
            
            # Get paragraphs
            paragraphs = re.findall(r'<p[^>]*?>(.*?)</p>', html_content, re.DOTALL)
            for p in paragraphs:
                cleaned_p = clean_html_text(p)
                if cleaned_p:  # Only add non-empty paragraphs
                    text_blocks.append(cleaned_p)
            
            # Get list items
            list_items = re.findall(r'<li[^>]*?>(.*?)</li>', html_content, re.DOTALL)
            for li in list_items:
                cleaned_li = clean_html_text(li)
                if cleaned_li:  # Only add non-empty list items
                    text_blocks.append(f"• {cleaned_li}")
            
            # Combine all text blocks with double newlines
            text_content = "\n\n".join(text_blocks)
            
            # Final cleanup
            text_content = re.sub(r'\n{3,}', '\n\n', text_content)  # Remove excessive newlines
        else:
            text_content = "Could not extract article content."
        
        return {
            "title": title,
            "author": author,
            "date": date,
            "content": text_content
        }
        
    except Exception as e:
        return None

def fetch_trade_companion_articles() -> list[dict[str, Any]]:
    """
    Fetch a list of articles from Trade Companion by Adam Mancini.
    Returns a list of articles with title, url, date, and preview.
    Excludes the "My Trade Methodology Fundamentals" article.
    """
    cookies = get_cookies_dict()
    headers = get_headers()
    
    try:
        # Make the request to the publication homepage
        response = requests.get(TRADE_COMPANION_URL, cookies=cookies, headers=headers)
        response.raise_for_status()
        
        # Extract article URLs
        article_urls = []
        
        # Direct pattern to find all URLs in the format "https://tradecompanion.substack.com/p/something"
        url_pattern = r'https://tradecompanion\.substack\.com/p/[^/\s"\']+(?=[\s"\'])'
        url_matches = re.findall(url_pattern, response.text)
        
        # Excluded article slug
        excluded_slug = "my-trade-methodology-fundamentals"
        
        for url in url_matches:
            # Only add URLs that match the publication domain and aren't the excluded article
            if url.startswith(TRADE_COMPANION_URL.rstrip('/')) and '/p/' in url:
                if excluded_slug not in url:
                    article_urls.append(url)
        
        # Create articles list from URLs
        articles = []
        
        # Remove duplicates while preserving order
        unique_urls = []
        for url in article_urls:
            if url not in unique_urls:
                unique_urls.append(url)
        
        # Create a basic article entry for each URL
        for url in unique_urls:
            # Extract title from URL
            slug = url.split('/')[-1]
            title = slug.replace('-', ' ').title()
            
            articles.append({
                "title": title,
                "url": url,
                "date": "",  # We'll need to fetch the article to get the date
                "preview": ""
            })
        
        return articles
        
    except Exception as e:
        return []

@mcp.tool()
def get_latest_trade_companion_adam_mancini_article() -> str:
    """
    Fetch and return the content of the latest Trade Companion article by Adam Mancini.
    Excludes the "My Trade Methodology Fundamentals" article.
    """
    articles = fetch_trade_companion_articles()
    
    if not articles:
        return "Failed to fetch articles from Trade Companion. The service might be temporarily unavailable."
    
    # Get the latest article (first in the list)
    latest_article_url = articles[0]["url"]
    
    article_data = fetch_substack_article_text(latest_article_url)
    
    if not article_data:
        return "Failed to fetch the latest article. The article might not be accessible."
    
    # Format the article data
    formatted_article = f"""
Title: {article_data['title']}
Author: {article_data['author']}
Published: {article_data['date']}
URL: {latest_article_url}

{article_data['content']}
"""
    
    return formatted_article

if __name__ == "__main__":
    # Initialize and run the server for Trade Companion by Adam Mancini
    mcp.run(transport='stdio')
