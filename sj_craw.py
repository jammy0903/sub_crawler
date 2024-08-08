import scrapy
from scrapy.crawler import CrawlerProcess
import requests
import json
import os
from urllib.parse import urlparse

class DomainSpider(scrapy.Spider):
    name = "domain_spider"

    def __init__(self, domain=None, max_depth=3, *args, **kwargs):
        super(DomainSpider, self).__init__(*args, **kwargs)
        self.domain = domain
        self.max_depth = int(max_depth)
        self.subdomains = set()
        self.results = {}

    def start_requests(self):
        crt_subdomains = self.get_crtsh()
        if crt_subdomains:
            self.subdomains = crt_subdomains
        else:
            self.subdomains = self.load_seclists()

        for subdomain in self.subdomains:
            url = f'http://{subdomain}'
            yield scrapy.Request(url, callback=self.parse, meta={'subdomain': subdomain, 'depth': 0})

    def get_crtsh(self):
        url = f"https://crt.sh/?q=%.{self.domain}&output=json&expired=yes"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response_json = response.json()

            subdomains = set()
            for certi in response_json:
                name_value = certi['name_value']
                if name_value.endswith(self.domain) and name_value != self.domain:
                    subdomains.update(name_value.split('\n'))
            return list(subdomains) if subdomains else None
        except requests.RequestException as e:
            self.logger.error(f"Error requesting crt.sh: {e}")
            return None

    def load_seclists(self):
        seclists_path = os.path.join('SecLists', 'Discovery', 'DNS', 'subdomains-top1million-5000.txt')
        try:
            with open(seclists_path, 'r') as file:
                return {line.strip() + '.' + self.domain for line in file}
        except FileNotFoundError:
            self.logger.error(f"SecLists file not found at {seclists_path}")
            return set()



    def parse(self, response):
        subdomain = response.meta['subdomain']
        current_depth = response.meta['depth']
        parsed_url = urlparse(response.url)
        current_domain = parsed_url.netloc

        if current_domain not in self.results:
            self.results[current_domain] = {'pages': []}

        page_data = self.extract_page_data(response)
        self.results[current_domain]['pages'].append(page_data)

        if current_depth < self.max_depth:
            for href in response.css('a::attr(href)').getall():
                full_url = response.urljoin(href)
                if full_url.startswith(f'http://{self.domain}') or full_url.startswith(f'https://{self.domain}'):
                    yield scrapy.Request(full_url, callback=self.parse, 
                                         meta={'subdomain': subdomain, 'depth': current_depth + 1})

    def extract_page_data(self, response):
        input_tags = []
        for tag in response.xpath('//input|//textarea|//select'):
            tag_info = {
                'type': tag.attrib.get('type', 'text'),
                'name': tag.attrib.get('name', ''),
                'id': tag.attrib.get('id', ''),
                'value': tag.attrib.get('value', '')
            }
            input_tags.append(tag_info)

        csrf_token = response.xpath('//meta[@name="csrf-token"]/@content').get()
        
        form_data = {}
        for form in response.xpath('//form'):
            form_id = form.attrib.get('id', '')
            form_data[form_id] = {
                'action': form.attrib.get('action', ''),
                'method': form.attrib.get('method', 'get'),
                'inputs': [
                    {
                        'name': input.attrib.get('name', ''),
                        'value': input.attrib.get('value', 'test_value')
                    }
                    for input in form.xpath('.//input|.//textarea|.//select')
                    if 'name' in input.attrib
                ]
            }

        cookies = [cookie.decode() for cookie in response.headers.getlist('Set-Cookie')]
        
        return {
            'url': response.url,
            'input_tags': input_tags,
            'csrf_token': csrf_token,
            'form_data': form_data,
            'cookies': cookies,
        }

    def closed(self, reason):
        with open(f"{self.domain}_analysis.json", "w") as f:
            json.dump(self.results, f, indent=2)

    def error(self, failure):
        self.logger.error(f"Error on {failure.request.url}: {str(failure.value)}")

# Scrapy 설정
settings = {
    'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'LOG_LEVEL': 'INFO',
    'CONCURRENT_REQUESTS': 32,
    'DOWNLOAD_DELAY': 0.5,
}

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python domain_spider.py <domain> [max_depth]")
        sys.exit(1)

    domain = sys.argv[1]
    max_depth = int(sys.argv[2]) if len(sys.argv) == 3 else 3  # 기본값 3

    process = CrawlerProcess(settings)
    process.crawl(DomainSpider, domain=domain, max_depth=max_depth)
    process.start()