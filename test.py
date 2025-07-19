import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time
from urllib.parse import urljoin, urlparse

visited_urls = set()

# Alternative WHOIS check using a public WHOIS lookup API (no dbm dependency)
def is_domain_expired(domain):
    try:
        url = f"https://api.api-ninjas.com/v1/whois?domain={domain}"
        headers = {'X-Api-Key': 'YOUR_API_KEY_HERE'}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            expiry_str = data.get("expires")
            if expiry_str:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%dT%H:%M:%S")
                return expiry_date < datetime.now()
        return True
    except Exception as e:
        print(f"WHOIS API failed for {domain}: {e}")
        return True

# Function to check if domain has past content using Wayback Machine
def has_past_content(domain):
    url = f"http://web.archive.org/web/*/http://{domain}"
    try:
        res = requests.get(url, timeout=10)
        return "No results found" not in res.text
    except:
        return False

# Estimate brandability score (simple heuristic)
def estimate_brandability(domain):
    score = 0
    name = domain.split('.')[0]
    if len(name) <= 10:
        score += 1
    if re.match(r'^[a-zA-Z]+$', name):
        score += 1
    if re.search(r'(fit|tech|cloud|shop|home|ai|data|bot|go|get)', name, re.IGNORECASE):
        score += 1
    return score

# Estimate backlinks by scraping OpenLinkProfiler (free SEO backlink checker)
def estimate_backlinks(domain):
    try:
        url = f"https://openlinkprofiler.org/r/{domain}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            counter = soup.find('span', class_='counter')
            if counter:
                digits = re.findall(r'\d+', counter.text)
                if digits:
                    return int(digits[0])
    except Exception as e:
        print(f"Backlink check failed for {domain}: {e}")
    return 0

# Extract only valid domain names (not full URLs) from HTML text
def extract_domains_from_html(html):
    text = BeautifulSoup(html, 'html.parser').get_text()
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
            links.add(full_url.split('#')[0])
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
    domains = spider_collect_domains(source, depth=2)
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

# Evaluate SEO metrics
seo_data = []
print("📊 Evaluating SEO metrics for expired domains...\n")
for domain in expired_domains:
    try:
        past_used = has_past_content(domain)
        brand_score = estimate_brandability(domain)
        backlinks = estimate_backlinks(domain)
        seo_data.append({
            "Domain": domain,
            "PastUsage": "Yes" if past_used else "No",
            "BrandabilityScore": brand_score,
            "Backlinks": backlinks
        })
        print(f"🔍 {domain} - Past Usage: {past_used}, Brandability: {brand_score}, Backlinks: {backlinks}")
    except Exception as e:
        print(f"⚠️ Error evaluating {domain}: {e}")

# Write SEO-enriched expired domain data to CSV
df = pd.DataFrame(seo_data)
filename = f"expired_domains_enriched_{datetime.now().strftime('%Y-%m-%d')}.csv"
df.to_csv(filename, index=False)
print(f"\n📄 Saved enriched expired domain data to {filename}")
