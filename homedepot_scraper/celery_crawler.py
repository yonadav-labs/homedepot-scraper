import sys

from scrapy.utils.project import get_project_settings
from scrapy.crawler import CrawlerProcess
from homedepot_scraper.spiders.homedepot_spider import HomedepotSpider

def scrape_module():
    crawler = CrawlerProcess(get_project_settings())
    crawler.crawl(HomedepotSpider, task_id=sys.argv[1])
    crawler.start()

if __name__ == '__main__':
    scrape_module()