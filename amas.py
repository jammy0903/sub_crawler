import json
import asyncio
import aiohttp
import subprocess
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urlparse

class DomainSpider(CrawlSpider):
    name = "domain_spider"
    
    rules = (
        Rule(LinkExtractor(), callback='parse_item', follow=True),
    )

    def __init__(self, domain=None, max_depth=3, *args, **kwargs):
        super(DomainSpider, self).__init__(*args, **kwargs)
        self.domain = domain
        self.max_depth = int(max_depth)
        self.subdomains = set()
        self.results = {}
        self.start_urls = []

    def start_requests(self):
        loop = asyncio.get_event_loop()
        self.subdomains = loop.run_until_complete(self.get_subdomains())
        self.logger.info(f"Found {len(self.subdomains)} subdomains")

        for subdomain in self.subdomains:
            for scheme in ['http', 'https']:
                url = f'{scheme}://{subdomain}'
                self.start_urls.append(url)

        for url in self.start_urls:
            yield self.make_requests_from_url(url)

    async def get_subdomains(self):
        subdomains = set()
        subdomains.update(await self.get_amass_subdomains())
        if not subdomains:
            subdomains.update(await self.get_crtsh())
        
        if not subdomains:
            self.logger.info("No subdomains found, using main domain")
            subdomains.add(self.domain)
        else:
            subdomains.add(self.domain)  # Always include the main domain
        
        return list(subdomains)

    async def get_amass_subdomains(self):
        try:
            process = await asyncio.create_subprocess_exec(
                'amass', 'enum', '-d', self.domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if stderr:
                self.logger.error(f"Amass error: {stderr.decode()}")
            subdomains = set(stdout.decode().splitlines())
            return subdomains
        except Exception as e:
            self.logger.error(f"Error running Amass: {str(e)}")
            return set()

    async def get_crtsh(self):
        url = f"https://crt.sh/?q=%.{self.domain}&output=json"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return set(item['name_value'] for item in data 
                                   if item['name_value'].endswith(self.domain) 
                                   and item['name_value'] != self.domain)
                    else:
                        self.logger.error(f"Error requesting crt.sh: HTTP {response.status}")
                        return set()
            except Exception as e:
                self.logger.error(f"Error requesting crt.sh: {str(e)}")
                return set()

    def parse_item(self, response):
        current_depth = response.meta.get('depth', 0)
        if current_depth > self.max_depth:
            return

        parsed_url = urlparse(response.url)
        current_domain = parsed_url.netloc

        if current_domain not in self.results:
            self.results[current_domain] = {'pages': []}

        page_data = self.extract_page_data(response)
        self.results[current_domain]['pages'].append(page_data)

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
        self.logger.info(f"Spider closed: {reason}")
        with open(f"{self.domain}_analysis.json", "w", encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        self.logger.info(f"Results saved to {self.domain}_analysis.json")

# Scrapy settings
settings = {
    'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'LOG_LEVEL': 'INFO',
    'CONCURRENT_REQUESTS': 32,
    'DOWNLOAD_DELAY': 0.5,
    'DEPTH_LIMIT': 3,
    'RETRY_TIMES': 3,
    'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429]
}

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python domain_spider.py <domain> [max_depth]")
        sys.exit(1)

    domain = sys.argv[1]
    max_depth = int(sys.argv[2]) if len(sys.argv) == 3 else 3  # Default value 3

    process = CrawlerProcess(settings)
    process.crawl(DomainSpider, domain=domain, max_depth=max_depth)
    process.start()