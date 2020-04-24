# Got a bit of help for getting proxies and rotating them from:
#   https://codelike.pro/create-a-crawler-with-rotating-ip-proxy-in-python/

import requests
import random
import math
from bs4 import BeautifulSoup
from csv import writer
import time

headers = ['Value', 'Type', 'Reference', 'Bedrooms', 'Bathrooms', 'Furnishing', 'Size', 'Amenities', 'Agency', 'Location']
dataset = []        # List of entries; Entry as list of features (seen in headers ^)
bad_types = ['Whole Building', 'Bulk Rent Units']       # Types we want to exclude

delays = [7, 4, 6, 2, 10, 19]       # Lengths of time we might wait before making a request

request_nr = 0      # Counts the number of requests we make
proxies = []        # Will contain proxies [ip, port]

diff_auth = ['http', 'https']


def get_proxies():
    global proxies

    response = requests.get("https://sslproxies.org/")
    soup = BeautifulSoup(response.content, 'html.parser')
    proxies_table = soup.find(id='proxylisttable')

    # Save proxies in the list
    for row in proxies_table.tbody.find_all('tr'):
        proxies.append({
            'ip': row.find_all('td')[0].string,
            'port': row.find_all('td')[1].string
        })

def get_random_proxy():
    proxy_nr = len(proxies)
    proxy_index = random.randint(0, proxy_nr-1)
    proxy = proxies[proxy_index]
    proxy_str = proxy['ip'] + ':' + proxy['port']
    proxy_dict = {}
    for auth in diff_auth:
        proxy_dict[auth] = auth + '://' + proxy_str

    return (proxy_dict, proxy_index)

get_proxies()
(proxy, proxy_index) = get_random_proxy()



def get_list_count_per_page(first_soup):
    list_count_per_page = 0
    listings = first_soup.find_all(class_="card-list__item")
    for listing in listings:
        list_count_per_page += 1

    return list_count_per_page


def get_page_count(first_soup):
    list_count = int(first_soup.find(class_="property-header__list-count").get_text().replace(' results', ''))
    list_count_per_page = get_list_count_per_page(first_soup)
    page_count = math.ceil(list_count / list_count_per_page)

    return page_count


def make_csv_file(file_name, headers, data):
    print("----- Making csv file: " + file_name + " -----")
    with open(file_name, 'w') as csv_file:
        csv_writer = writer(csv_file)
        csv_writer.writerow(headers)
        csv_writer.writerows(data)



def request_listing(link):
    global request_nr, proxies, proxy, proxy_index

    # Every 10 requests, generate a new proxy
    if request_nr % 10 == 0:
        (proxy, proxy_index) = get_random_proxy()

    try:    # Request link with current proxy
        print('Requesting link now.')
        page = requests.get(link, proxies=proxy)
        print('#' + str(request_nr) + ': ' + link)
        request_nr += 1
        return page

    except:  # If error, delete this proxy and find another one
        del proxies[proxy_index]
        print('Proxy #' + str(proxy_index) + ' deleted.')
        (proxy, proxy_index) = get_random_proxy()



def scrape_listing(link, location, run_proxy=False):
    global dataset

    # Wait if you don't want to get banned
    # delay = random.choice(delays)
    # time.sleep(delay)

    print("Accessing listing on:", link)

    if run_proxy:
        page = request_listing(link)
    else:
        page = requests.get(link)

    if page == None:
        print(" - Could not reach page")
        return

    data = []
    soup = BeautifulSoup(page.text, 'html.parser')

    # Getting Value, Type, Reference, Bedrooms, Bathrooms, Furnishing, Size
    facts = soup.find_all(class_="facts__list-item")
    for fact in facts:
        data.append(fact.find(class_="facts__content").get_text().replace('\n', ''))

    # Check if this listing is a bad type
    for bad_t in bad_types:
        if bad_t in data:
            print(" - Found bad type, not including it in dataset")
            return

    # Getting Amenities
    all_amenities = []
    amenities = soup.find_all(class_="amenities__list-item")
    for amenity in amenities:
        all_amenities.append(amenity.find(class_="amenities__content").get_text())
    all_amenities_str = ' - '.join(all_amenities)
    data.append(all_amenities_str)

    # Getting Agency
    all_agent_info = []
    agent_info = soup.find_all(class_="agent-info__detail-content--bold")
    for info in agent_info:
        all_agent_info.append(info.get_text())
    data.append(all_agent_info[1])

    data.append(location)

    print(" - Data:", data)
    dataset.append(data)


def scrape_page(sp, root, run_proxy=False):
    cards = sp.find_all(class_="card-list__item")
    for card in cards:
        listing_link = root + card.find('a', class_="card--clickable", href=True)['href']
        listing_location = card.find(class_="card__location").get_text().replace(',', ' -')
        scrape_listing(listing_link, listing_location, run_proxy)


def scrape(root, link_pre, link_post, file_name, run_proxy=False):
    link1 = link_pre + '1' + link_post
    page1 = requests.get(link1)
    soup1 = BeautifulSoup(page1.text, 'html.parser')

    page_count = get_page_count(soup1)

    print("----- Starting scrape on " + str(page_count) + " pages -----")

    # Iterating through all pages on site
    start_page_nr = 1
    for page_nr in range(start_page_nr, page_count+1):
        print("---------- Accessing page", str(page_nr), "----------")
        link = link_pre + str(page_nr) + link_post
        page = requests.get(link)
        soup = BeautifulSoup(page.text, 'html.parser')
        scrape_page(soup, root, run_proxy)

        # Keep backing up dataset every 5 pages
        if page_nr % 5 == 0:
            file_name_nr = file_name + str(start_page_nr) + "_" + str(page_nr) + ".csv"
            make_csv_file(file_name_nr, headers, dataset)

        print("Size of dataset after scraping page", str(page_nr), ":", str(len(dataset)))

    print("----- Successfully scraped " + str(page_count+1) + "pages -----")


# PF for PropertyFinder

# Links are split depending on where the page nr fits in
PF_link_pre = 'https://www.propertyfinder.qa/en/search?c=2&l=9&ob=ba&page='
PF_link_post = '&rp=m'
PF_root = 'https://www.propertyfinder.qa'

PF_file_name = "PF_scrape_"
scrape(PF_root, PF_link_pre, PF_link_post, PF_file_name)
PF_file_name_final = "PF_scrape_final.csv"
make_csv_file(PF_file_name_final, headers, dataset)
