import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import whois
import re
import time
from urllib.parse import urljoin, urlparse

visited_urls = set()

# Function to check WHOIS expiration
def is_domain_expired(domain):
    try:
        w = whois.whois(domain)
        expiry = w.expiration_date
        if isinstance(expiry, list):
            expiry = expiry[0]
        if expiry is None:
            return True
        return expiry < datetime.now()
    except Exception as e:
        print(f"WHOIS failed for {domain}: {e}")
        return True  # Assume expired if WHOIS fails

# Extract only valid domain names (not full URLs) from HTML text
def extract_domains_from_html(html):
    text = BeautifulSoup(html, 'html.parser').get_text()
    # Regex pattern to match proper domain names (e.g., example.com, test.ai, sample.io)
    pattern = r"\b[a-zA-Z0-9-]{1,63}\.(?:com|ai|io)\b"
    return list(set(re.findall(pattern, text, re.IGNORECASE)))

# Extract internal links from a page
def extract_internal_links(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    base_netloc = urlparse(base_url).netloc
    links = set()
    for tag in soup.find_all("a", href=True):
        href = tag['href']
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme.startswith('http') and parsed.netloc == base_netloc:
            links.add(full_url.split('#')[0])  # remove anchors
    return links

# Spider to crawl links up to given depth, and collect domains from page contents
def spider_collect_domains(start_url, depth=1):
    to_visit = {start_url}
    all_domains = set()

    for _ in range(depth):
        next_round = set()
        for url in to_visit:
            if url in visited_urls:
                continue
            visited_urls.add(url)
            try:
                res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if res.status_code == 200:
                    html = res.text
                    domains = extract_domains_from_html(html)
                    all_domains.update(domains)
                    next_links = extract_internal_links(html, url)
                    next_round.update(next_links)
                    print(f"✅ Crawled: {url} - Domains Found: {len(domains)}, Internal Links: {len(next_links)}")
                time.sleep(1)
            except Exception as e:
                print(f"Error crawling {url}: {e}")
        to_visit = next_round
    return all_domains

# List of source URLs to start spidering from
sources = [
    "https://www.expireddomains.net/expired-domains/",
    "https://www.moonsy.com/expired_domains/",
    "https://www.justdropped.com/",
    "https://snapnames.com",
    "https://www.namejet.com/Pages/Auctions/ExpiredDomains.aspx"
]

# Main Execution: Collect domains via spidering
all_domains = set()
print("🕷️ Starting spider crawl and domain extraction...\n")
for source in sources:
    domains = spider_collect_domains(source, depth=2)  # Depth can be adjusted as needed
    all_domains.update(domains)

print(f"\n🔍 Total raw domain entries found: {len(all_domains)}\n")

# WHOIS check: Verify and collect only the expired domains
expired_domains = []
print("🔎 Verifying which domains are expired...\n")
for domain in all_domains:
    if is_domain_expired(domain):
        print(f"✅ Expired: {domain}")
        expired_domains.append(domain)
    else:
        print(f"❌ Active: {domain}")

# Write only the expired domains to a CSV file
df = pd.DataFrame(expired_domains, columns=["Domain"])
filename = f"expired_domains_{datetime.now().strftime('%Y-%m-%d')}.csv"
df.to_csv(filename, index=False)
print(f"\n📄 Saved {len(expired_domains)} expired domains to {filename}")

