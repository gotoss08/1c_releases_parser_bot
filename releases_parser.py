import requests
from bs4 import BeautifulSoup

import sys
import json
import codecs

import bot_config as config

RELEASES_BASE_DISTROS_ID = '93'
RELEASES_INDUSTRY_DISTROS_ID = '162'

def releases_get_execution_value():
    path = 'https://login.1c.ru/login?service=https%3A%2F%2Freleases.1c.ru%2Fpublic%2Fsecurity_check'
    r = requests.get(path)
    soup = BeautifulSoup(r.text, 'html.parser')
    return soup.find('input', attrs={'name': 'execution'})['value']

def releases_parse_distros(distros, soup, parent_group_id):

    distro_path = 'https://releases.1c.ru'

    rows = soup.find_all('tr', attrs={'parent-group': parent_group_id})

    for row in rows:

        distro = {
            'type': '',
            'name': '',
            'url': '',
            'current_version': '',
            'release_date': ''
        }

        distro['type'] = '1c'

        name_el = row.find('td', class_='nameColumn')
        distro['name'] = name_el.get_text().strip()

        if parent_group_id == RELEASES_INDUSTRY_DISTROS_ID and distro['name'].find('Казахста') == -1:
            continue

        dist_link_el = name_el.find('a')
        if dist_link_el:
            distro['url'] = distro_path + dist_link_el['href'].strip()

        version_el = row.find('td', class_='versionColumn actualVersionColumn')
        if version_el:
            distro['current_version'] = version_el.get_text().strip()
            version_link_el = version_el.find('a')
            if version_link_el:
                distro['url'] = distro_path + version_link_el['href']

        release_date_el = row.find('td', class_='releaseDate')
        if release_date_el:
            distro['release_date'] = release_date_el.get_text().strip()

        distros.append(distro)

    return distros

def releases_fetch_distros(distros):

    path = 'https://login.1c.ru/login'
    payload = {
        'username': config.LOGIN_1C_RU_USERNAME,
        'password': config.LOGIN_1C_RU_PASSWORD,
        'rememberMe': 'on',
        'execution': releases_get_execution_value(),
        '_eventId': 'submit',
    }
    r = requests.post(path, data=payload)
    r.encoding = 'utf-8'
    soup = BeautifulSoup(r.text, 'html.parser')

    releases_parse_distros(distros, soup, RELEASES_BASE_DISTROS_ID)
    releases_parse_distros(distros, soup, RELEASES_INDUSTRY_DISTROS_ID)

def rating_fetch_distros(distros):

    path = 'https://download.1c-rating.kz'
    r = requests.get(path)
    r.encoding = 'utf-8'
    soup = BeautifulSoup(r.text, 'html.parser')

    rows = soup.select('tbody > tr')
    for row in rows:

        cols = row.find_all('td')
        if len(cols) < 3:
            continue

        distro = {
            'type': '',
            'name': '',
            'url': '',
            'current_version': '',
            'release_date': ''
        }

        distro['type'] = 'rating'

        name_el = cols[0]
        if name_el:
            name_el = name_el.find_all('a')
            if name_el:
                distro['name'] = name_el[0].get_text().strip()

        version_el = cols[1]
        if version_el:
            distro['current_version'] = version_el.get_text().strip()

            link_el = version_el.find('a')
            if link_el:
                distro['url'] = path + link_el['href']

        release_date_el = cols[2]
        if release_date_el:
            distro['release_date'] = release_date_el.get_text().strip()

        distros.append(distro)

def dump_distros_to_file(distros, file_name):
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(distros, f, ensure_ascii=False)

def load_distros_from_file(file_path):
    distros = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        distros = json.load(f)
    return distros

def diff_distros(distros1, distros2):
    diffed_distros = []
    for distro2 in distros2:
        found = False
        for distro1 in distros1:
            if distro1['name'] == distro2['name']:
                found = True
                if distro1['current_version'] != distro2['current_version']:
                    diffed_distros.append(distro2)
                continue
        if not found:
            diffed_distros.append(distro2)
    return diffed_distros

def fetch_distros():
    distros = []
    releases_fetch_distros(distros)
    rating_fetch_distros(distros)
    return distros

