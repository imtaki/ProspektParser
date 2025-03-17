
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from urllib.parse import urljoin


class Parser:
    def __init__(self):
        self.base_url = "https://www.prospektmaschine.de"
        self.session = requests.Session()
        self.results = []
        self.processed_urls = set() 
        
    def fetch_page(self, url):
        try:
            print(f"Sťahujem stránku: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Chyba pri sťahovaní stránky {url}: {e}")
            return None
    
    def parse_date_from_title(self, title_text):
        if not title_text:
            return None, None
        
        match = re.search(r"gültig ab dem (\d{2}\.\d{2}\.\d{4})", title_text)
        if match:
            date_str = match.group(1)
            day, month, year = date_str.split('.')
            return f"{year}-{month}-{day}", f"{year}-{month}-{day}"
        
        match = re.search(r"(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})", title_text)
        if match:
            from_date = match.group(1)
            to_date = match.group(2)
            
            day1, month1, year1 = from_date.split('.')
            day2, month2, year2 = to_date.split('.')
            
            return f"{year1}-{month1}-{day1}", f"{year2}-{month2}-{day2}"
        
        match = re.search(r"von\s+\w+\s+(\d{2}\.\d{2}\.\d{4})", title_text)
        if match:
            date_str = match.group(1)
            day, month, year = date_str.split('.')
            return f"{year}-{month}-{day}", f"{year}-{month}-{day}"

        match = re.search(r"(\d{2}\.\d{2}\.\d{4})", title_text)
        if match:
            date_str = match.group(1)
            day, month, year = date_str.split('.')
            return f"{year}-{month}-{day}", f"{year}-{month}-{day}"
        
        today = datetime.now().strftime("%Y-%m-%d")
        return today, today
    
    def extract_shop_name_from_url(self, url):
        parts = url.rstrip('/').split('/')
        for i, part in enumerate(parts):
            if part and part not in ['hypermarkte', 'prospekte', 'de', 'kataloge', 'www.prospektmaschine.de']:
                if i > 0 and parts[i-1] in ['hypermarkte', 'prospekte', 'kataloge'] or i == 3:
                    shop_name = part.replace('-', ' ').title()
                    return shop_name
        return "Neznámy obchod"
    
    def parse_brochure_element(self, element, shop_name=None):
        try:
            link_element = element.find('a')
            if not link_element:
                return None
                
            href = link_element.get('href')
            if not href:
                return None
            
            if not href.startswith('http'):
                href = urljoin(self.base_url, href)
                
            title = link_element.get('title', '')
            if not title:
                title_element = link_element.find('div', class_='brochure-title')
                if title_element:
                    title = title_element.text.strip()
                else:
                    title = 'Prospekt'
            
            valid_from, valid_to = self.parse_date_from_title(title)
            
            img_element = element.find('img')
            thumbnail = img_element.get('src') if img_element else ""
            if thumbnail and not thumbnail.startswith('http'):
                thumbnail = urljoin(self.base_url, thumbnail)
            
            if not shop_name:
                shop_name = self.extract_shop_name_from_url(href)
            
            brochure_id = f"{shop_name}_{valid_from}_{valid_to}"
            
            if brochure_id in self.processed_urls:
                return None
                
            self.processed_urls.add(brochure_id)
            
            return {
                "title": title,
                "thumbnail": thumbnail,
                "shop_name": shop_name,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "parsed_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            print(f"Chyba pri parsovaní letáku: {e}")
            return None
    
    def parse_hypermarkets_page(self):
        url = f"{self.base_url}/hypermarkte/"
        html = self.fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        
        brochure_elements = soup.select('.brochure-thumb')
        
        print(f"Nájdených {len(brochure_elements)} letákov na hlavnej stránke")
        
        for element in brochure_elements:
            prospekt = self.parse_brochure_element(element)
            if prospekt:
                self.results.append(prospekt)
                print(f"Pridaný leták: {prospekt['shop_name']}")
        
        shop_urls = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/prospekte/' in href or '/kataloge/' in href:
                full_url = urljoin(self.base_url, href)
                shop_name = self.extract_shop_name_from_url(full_url)
                shop_urls.append((full_url, shop_name))
        
        shop_urls = list(set(shop_urls))
        print(f"Nájdených {len(shop_urls)} odkazov na obchody")
        
        return shop_urls
    
    def parse_shop_page(self, url, shop_name):
        html = self.fetch_page(url)
        if not html:
            return
        
        soup = BeautifulSoup(html, 'html.parser')
        
        brochure_elements = soup.select('.brochure-thumb')
        
        print(f"Nájdených {len(brochure_elements)} letákov pre obchod {shop_name}")
        
        for element in brochure_elements:
            prospekt = self.parse_brochure_element(element, shop_name)
            if prospekt:
                self.results.append(prospekt)
                print(f"Pridaný leták: {prospekt['shop_name']}")
    
    def run(self):
        shop_urls = self.parse_hypermarkets_page()
        
        for i, (url, shop_name) in enumerate(shop_urls):
            print(f"Spracovávam obchod {i+1}/{len(shop_urls)}: {shop_name}")
            self.parse_shop_page(url, shop_name)
        
        print(f"Celkovo nájdených {len(self.results)} unikátnych letákov")
        return self.results
    
    def save_results(self, filename="prospekty.json"):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            print(f"Výsledky uložené do súboru {filename}")
            return True
        except Exception as e:
            print(f"Chyba pri ukladaní výsledkov: {e}")
            return False


# Spustenie parsera
if __name__ == "__main__":
    parser = Parser()
    parser.run()
    parser.save_results()