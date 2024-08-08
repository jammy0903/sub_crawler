import requests , sys , json , warnings, re
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import urljoin

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def parse_content(content, content_type):
    if 'xml' in content_type.lower():
        return BeautifulSoup(content, 'xml')
    else:
        return BeautifulSoup(content, 'html.parser')


def is_valid_subdomain(subdomain, domain):
    pattern = r'^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.' + re.escape(domain) + '$'  
    return re.match(pattern, subdomain) is not None

def get_subdomains(domain):
    url = f"https://crt.sh/?q=%.{domain}&output=json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        subdomains = set()
        for entry in data:
            name_value = entry['name_value']
            if name_value.endswith(domain) and name_value != domain and is_valid_subdomain(name_value, domain):
                subdomains.add(name_value)
        return list(subdomains)
    except requests.RequestException as e:
        print(f"Error fetching subdomains: {e}")
        return []

def get_links(soup, base_url):
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        full_url = urljoin(base_url, href)
        if full_url.startswith(base_url):
            links.append(full_url)
    return links

def analyze_page(session, url):
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser', from_encoding=response.encoding)
        
        input_tags = []
        for tag in soup.find_all(['input', 'textarea', 'select']):
            if tag.name == 'input' and tag.get('type') in ['button', 'submit', 'reset']:
                continue
            input_tags.append(str(tag))
        
        form_data = {}
        for tag in soup.find_all(['input', 'textarea', 'select']):
            if tag.get('name'):
                if tag.name == 'select':
                    options = tag.find_all('option')
                    form_data[tag['name']] = options[0]['value'] if options else ''
                else:
                    form_data[tag['name']] = tag.get('value', 'test_value')
        
        csrf_token = None
        csrf_meta = soup.find('meta', attrs={'name': 'csrf-token'})
        if csrf_meta:
            csrf_token = csrf_meta.get('content')
            form_data['csrf_token'] = csrf_token
        
        post_response = None
        if form_data:
            try:
                post_response = session.post(url, data=form_data, timeout=10)
                post_response = post_response.text[:500]
            except requests.RequestException as e:
                post_response = f"POST request failed: {str(e)}"
        
        return {
            "url": url,
            "input_tags": input_tags,
            "cookies": dict(session.cookies),
            "csrf_token": csrf_token,
            "form_data": form_data,
            "post_response": post_response
        }
        
    except requests.Timeout:
        print(f"Timeout error occurred while accessing {url}")
        return None
    except requests.ConnectionError:
        print(f"Connection error occurred while accessing {url}")
        return None
    except requests.RequestException as e:
        print(f"Error occurred while analyzing {url}: {str(e)}")
        return None

def analyze_subdomain(subdomain):
    session = requests.Session()
    base_url = f"https://{subdomain}"
    try:
        response = session.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser', from_encoding=response.encoding)
        links = get_links(soup, base_url)
        
        results = [analyze_page(session, base_url)]
        for link in links[:5]:
            result = analyze_page(session, link)
            if result:
                results.append(result)
        
        return results
    except requests.RequestException as e:
        print(f"Error accessing {base_url}: {str(e)}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python sub.py <domain>")
        sys.exit(1)
    
    domain = sys.argv[1]
    subdomains = get_subdomains(domain)
    print("Found subdomains:")
    for subdomain in subdomains:
        print(subdomain)
    
    results = {}
    for subdomain in subdomains:
        print(f"\nAnalyzing {subdomain}...")
        analysis = analyze_subdomain(subdomain)
        if analysis:
            results[subdomain] = analysis
    
    with open(f"{domain}_analysis.json", "w", encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nAnalysis complete. Results saved to {domain}_analysis.json")

if __name__ == "__main__":
    main()
        
          
        
        
        
        
        
        
        
 