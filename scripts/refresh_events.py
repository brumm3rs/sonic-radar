#!/usr/bin/env python3
"""Refresh SONIC RADAR by parsing publicly announced event pages.

Sources: official venues in Maastricht/Heerlen/Eindhoven, plus optional Ticketmaster
Discovery API (TICKETMASTER_API_KEY). Scraping is best-effort and deliberately
conservative: a show needs an official link, a future date, and matching genres.
On failures, the previously verified starter data remains available.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from hashlib import sha1
import json
import logging
import os
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / 'data' / 'events.json'
JS_FILE = ROOT / 'data' / 'events.js'
HEADERS = {'User-Agent': 'SonicRadar/1.0 (public event index, low-frequency updates; contact via repository README)'}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
LOG = logging.getLogger('sonic-radar')
SOURCES = [
    {'id':'complex','url':'https://complexmaastricht.nl/','pattern':r'^/agenda/[^/]+/?$','city':'Maastricht','venue':'Complex','country':'NL','limit':40},
    {'id':'muziekgieterij','url':'https://muziekgieterij.nl/','pattern':r'^/(?:en/)?event/[^/]+/?$','city':'Maastricht','venue':'Muziekgieterij','country':'NL','limit':70},
    {'id':'nieuwe-nor','url':'https://nieuwenor.nl/programma','pattern':r'^/programma/20\d{2}/\d{2}/\d{2}/[^/]+/?$','city':'Heerlen','venue':'Nieuwe Nor','country':'NL','limit':65},
    {'id':'effenaar','url':'https://effenaar.nl/agenda','pattern':r'^/(?:nl/)?agenda/[^/]+/?$','city':'Eindhoven','venue':'Effenaar','country':'NL','limit':80},
]
GENRE_TERMS = {
  'techno': [('hard techno',r'\bhard[ -]?techno\b'),('industrial',r'\bindustrial\b'),('schranz',r'\bschranz\b'),('techno',r'\btechno\b'),('hardgroove',r'\bhard[ -]?groove\b')],
  'trance': [('hard trance',r'\bhard[ -]?trance\b'),('eurotrance',r'\beurotrance\b'),('hard house',r'\bhard[ -]?house\b'),('trance',r'\btrance\b'),('groove',r'\bhardgroove\b')],
  'rock': [('shoegaze',r'\bshoegaze\b'),('noise rock',r'\bnoise[ -]?rock\b'),('slowcore',r'\bslowcore\b'),('grunge',r'\bgrunge\b'),('stoner rock',r'\bstoner[ -]?rock\b'),('desert rock',r'\bdesert[ -]?rock\b'),('post-punk',r'\bpost[ -]?punk\b'),('post-rock',r'\bpost[ -]?rock\b'),('post-metal',r'\bpost[ -]?metal\b'),('garage rock',r'\bgarage[ -]?(?:rock|punk)\b'),('indie rock',r'\bindie[ -]?rock\b'),('alternative rock',r'\balternat(?:ive|ief)[ -]?rock\b'),('psychedelic rock',r'\bpsych(?:edelic)?[ -]?rock\b'),('dream pop',r'\bdream[ -]?pop\b'),('art rock',r'\bart[ -]?rock\b'),('darkwave',r'\bdarkwave\b'),('indie',r'\bindie\b')],
}
ARTISTS = { 'her new knife':'rock','pixies':'rock','queens of the stone age':'rock','slomosa':'rock','bodega':'rock','midwife':'rock','bettie serveert':'rock','the haunted youth':'rock','meltheads':'rock','black box revelation':'rock','the vintage caravan':'rock','onlynumbers':'techno','nico moreno':'techno','toxic machinery':'techno','unwind':'techno','dax j':'techno','oguz':'techno','shlomo':'techno','dave clarke':'techno','arman john':'trance','ki/ki':'trance','dj heartstring':'trance','kyle starkey':'trance','hotline':'trance','mall grab':'trance','pegassi':'trance','kadavar':'rock','water damage':'rock','bongloard':'rock','psychedelic porn crumpets':'rock','lily seabird':'rock','grommet':'rock','cleopatrick':'rock','valley of the sun':'rock','acid invaderz':'techno' }
CLEAN_TITLE = re.compile(r'\s+[-|]\s+(?:Muziekgieterij|Nieuwe Nor|Effenaar|Complex).*$',re.I)
BAD_TITLES = re.compile(r'^(?:home|agenda|program(?:ma)?|more|tickets|buy tickets|programma|info|next|nieuws)$',re.I)
MONTH_MAP = {'jan':1,'januari':1,'january':1,'feb':2,'februari':2,'february':2,'mrt':3,'mar':3,'maart':3,'march':3,'apr':4,'april':4,'may':5,'mei':5,'jun':6,'juni':6,'june':6,'jul':7,'juli':7,'july':7,'aug':8,'august':8,'sep':9,'sept':9,'september':9,'okt':10,'oct':10,'october':10,'oktober':10,'nov':11,'november':11,'dec':12,'december':12,'dezember':12,'märz':3,'marz':3}
DATE_RE = re.compile(r'(?<!\d)(\d{1,2})\s+(jan(?:uari|uary)?|feb(?:ruari|ruary)?|mrt|maa(?:rt)?|mar(?:ch)?|apr(?:il)?|may|mei|jun(?:e|i)?|jul(?:y|i)?|aug(?:ust)?|sep(?:tember|t)?|okt(?:ober)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|dezember|märz)\s+(20\d{2})',re.I)


def get(url: str, timeout=18) -> requests.Response:
    r = SESSION.get(url,timeout=timeout)
    r.raise_for_status()
    return r


def date_in_url(url: str) -> str|None:
    m = re.search(r'(20\d{2})[-/](\d{2})[-/](\d{2})',url)
    if m:
        try: return datetime(int(m[1]),int(m[2]),int(m[3])).date().isoformat()
        except ValueError: pass
    m = re.search(r'/([0-9]{2})-([0-9]{2})-(20[0-9]{2})(?:/|$)',url)
    if m:
        try: return datetime(int(m[3]),int(m[2]),int(m[1])).date().isoformat()
        except ValueError: pass
    return None


def parse_date(text: str, url: str='') -> str|None:
    d = date_in_url(url)
    if d:return d
    m = DATE_RE.search(text)
    if m:
        mon = MONTH_MAP.get(m[2].lower())
        if mon:
            try:return datetime(int(m[3]),mon,int(m[1])).date().isoformat()
            except ValueError:pass
    iso = re.search(r'(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)',text)
    if iso:
        try:return datetime.strptime(iso[1],'%Y-%m-%d').date().isoformat()
        except ValueError:pass
    # Generic fall-through for text such as "Sat Mar 7th 2027".
    match = re.search(r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)[, ]+.{0,50}?20\d{2}',text,re.I)
    if match:
        alt=re.search(r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?[, ]+?(20\d{2})',match[0],re.I)
        if alt:
            mon=MONTH_MAP.get(alt[1].lower())
            if mon:
                try:return datetime(int(alt[3]),mon,int(alt[2])).date().isoformat()
                except ValueError:pass
    return None


def classify(title:str, context:str) -> tuple[str,list[str]]|None:
    """Return only meaningful genre matches; don't mistake a generic site nav for the gig's genre."""
    text=(title+' '+context[:2000]).lower()
    hits={group:[tag for tag,pattern in terms if re.search(pattern,text,re.I)] for group,terms in GENRE_TERMS.items()}
    for artist,genre in ARTISTS.items():
        if artist in title.lower() and artist not in ['unwind']:
            if not hits[genre]:hits[genre]=['artist match']
    # Industrial or hard techno takes priority over trance, then rock.
    if any(t in hits['techno'] for t in ['hard techno','industrial','schranz']):return 'techno',list(dict.fromkeys(hits['techno']))[:4]
    if any(t in hits['trance'] for t in ['hard trance','eurotrance','hard house','trance']):return 'trance',list(dict.fromkeys(hits['trance']))[:4]
    if hits['rock']:return 'rock',list(dict.fromkeys(hits['rock']))[:4]
    if hits['trance']:return 'trance',list(dict.fromkeys(hits['trance']))[:4]
    if hits['techno']:return 'techno',list(dict.fromkeys(hits['techno']))[:4]
    return None


def extract_jsonld(soup:BeautifulSoup)->dict|None:
    def walk(x):
        if isinstance(x,list):
            for v in x:yield from walk(v)
        elif isinstance(x,dict):
            typ=x.get('@type',[])
            if (isinstance(typ,str) and typ in ('Event','MusicEvent')) or (isinstance(typ,list) and any(v in ('Event','MusicEvent') for v in typ)):
                yield x
            for v in x.values():yield from walk(v)
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            for event in walk(json.loads(tag.string or tag.get_text())):
                if event.get('name') and event.get('startDate'):return event
        except (ValueError,TypeError):continue
    return None


def take_candidates(soup:BeautifulSoup,src:dict)->list[tuple[str,str]]:
    found={}
    for a in soup.select('a[href]'):
        href=urljoin(src['url'],a.get('href',''))
        if urlparse(href).netloc.removeprefix('www.')!=urlparse(src['url']).netloc.removeprefix('www.'):continue
        if not re.match(src['pattern'],urlparse(href).path):continue
        if href in found:continue
        anchor=a.get_text(' ',strip=True)
        parent=a.parent.get_text(' ',strip=True)[:220] if a.parent else ''
        found[href]=(anchor+' '+parent).strip()
    return list(found.items())[:src['limit']]


def parse_detail(html:str,url:str,src:dict,checked:str)->dict|None:
    soup=BeautifulSoup(html,'html.parser')
    structured=extract_jsonld(soup)
    title=(structured or {}).get('name','') if structured else ''
    h1=soup.find('h1')
    if not title and h1:title=h1.get_text(' ',strip=True)
    if not title:
        tag=soup.find('meta',property='og:title')
        title=tag.get('content','') if tag else ''
    title=CLEAN_TITLE.sub('',title).strip()
    if not title or BAD_TITLES.match(title) or len(title)>170:return None
    main=soup.find('main') or soup.find('article') or soup.body or soup
    text=main.get_text(' ',strip=True)
    # Date priority: URL slug, JSON-LD, <time>, visible date by headline, page text.
    date=date_in_url(url)
    if not date and structured:
        date=parse_date(str(structured.get('startDate','')))
    if not date:
        for t in soup.select('time[datetime]')[:6]:
            date=parse_date(t.get('datetime',''))
            if date:break
    if not date and h1:
        # h1 vicinity rather than everything (venue navigation has misleading dates).
        near=' '.join([h1.parent.get_text(' ',strip=True)[:1300] if h1.parent else '',text[:950]])
        date=parse_date(near)
    if not date:date=parse_date(text[:1100])
    if not date:return None
    if date < datetime.now(timezone.utc).date().isoformat():return None
    # Look near headline first, then nearby genre labels and description. Avoid unrelated promos.
    context=text[:2600]
    if h1:
        if title.lower() in text.lower():
            idx=text.lower().find(title.lower())
            context=text[max(0,idx-50):idx+2250]
    category=classify(title,context)
    if not category:return None
    group,tags=category
    if not tags:return None
    status='on-sale'
    short=context[:240].lower()
    if re.search(r'\b(?:almost sold out|bijna uitverkocht|laatste kaarten|last tickets|almost gone)\b',short):status='low-tickets'
    elif re.search(r'\b(?:sold out|uitverkocht|ausverkauft)\b',short):status='sold-out'
    time_value=None
    if structured:
        m=re.search(r'T(\d{2}:\d{2})',str(structured.get('startDate','')))
        if m:time_value=m[1]
    if not time_value:
        # Detail pages list start times separately; prefer first time close to heading.
        tm=re.search(r'\b(?:Aanvang|Start|Starts|Beginn|Event starts)\s*(\d{1,2}:\d{2})',context,re.I)
        if tm:time_value=tm[1]
    if not time_value and src['id']=='complex':
        tm=re.search(r'\b(2[1-3]:\d{2})\s*-\s*\d{1,2}:\d{2}',text)
        if tm:time_value=tm[1]
    kind='festival' if re.search(r'\bfestival\b',title,re.I) else 'club' if group in ('trance','techno') else 'gig'
    artists=[title]
    return {'id':'scan-'+sha1((url+date).encode()).hexdigest()[:13], 'title':title, 'date':date,
            'time':time_value,'city':src['city'],'venue':src['venue'],'country':src['country'],
            'category':group,'styles':tags,'artists':artists,'type':kind,'url':url,'status':status,
            'note':'Matched from the official venue announcement; check the event page for the complete lineup.',
            'source':src['venue'],'curated':False,'firstSeen':checked,'lastVerified':checked}


def crawl_official(src,checked):
    home=get(src['url'])
    soup=BeautifulSoup(home.text,'html.parser')
    candidates=take_candidates(soup,src)
    LOG.info('%s: discovered %d potential event links',src['id'],len(candidates))
    results=[]
    for idx,(url,anchor) in enumerate(candidates):
        # Avoid requests for obviously irrelevant events if their listing labels are descriptive.
        if len(anchor)>26 and not classify(anchor,anchor) and not any(a in anchor.lower() for a in ARTISTS):
            # Some venues don't provide genres in the listing; still inspect a small sample.
            if idx>35:continue
        try:
            page=get(url)
            event=parse_detail(page.text,url,src,checked)
            if event:results.append(event)
        except requests.RequestException as exc:
            LOG.warning('Failed %s: %s',url,str(exc)[:80])
        time.sleep(0.12)
    return results, bool(candidates)


def geohash(lat:float,lon:float,length=9):
    alphabet='0123456789bcdefghjkmnpqrstuvwxyz'; lat_rng=[-90.0,90.0];lon_rng=[-180.0,180.0]
    out=''; bits=0; num=0; even=True
    while len(out)<length:
        rng=lon_rng if even else lat_rng; value=lon if even else lat; mid=sum(rng)/2
        if value>=mid:num=(num<<1)|1;rng[0]=mid
        else:num=num<<1;rng[1]=mid
        even=not even;bits+=1
        if bits==5:out+=alphabet[num];bits=num=0
    return out


def crawl_ticketmaster(api_key:str,checked:str):
    keywords=['shoegaze','noise rock','post punk','stoner rock','hard techno','hard trance','industrial techno','Arman John','Pixies','Queens of the Stone Age']
    results=[]
    for q in keywords:
        params={'apikey':api_key,'keyword':q,'geoPoint':geohash(50.8514,5.6909),'radius':'250','unit':'km','size':100,'sort':'date,asc','locale':'*'}
        response=get('https://app.ticketmaster.com/discovery/v2/events.json?'+requests.Request('GET','https://app.ticketmaster.com/discovery/v2/events.json',params=params).prepare().url.split('?',1)[1])
        for ev in response.json().get('_embedded',{}).get('events',[]):
            d=ev.get('dates',{}).get('start',{}).get('localDate')
            venue=(ev.get('_embedded',{}).get('venues') or [{}])[0]
            title=ev.get('name','')
            if not d or not title or d < checked:continue
            details=' '.join([title,q]+[c.get('genre',{}).get('name','') for c in ev.get('classifications',[])])
            classification=classify(title,details)
            if not classification:continue
            group,tags=classification
            city=venue.get('city',{}).get('name') or 'Unknown city'
            location=venue.get('location') or {}
            try:lat=float(location['latitude']);lon=float(location['longitude'])
            except (KeyError,ValueError,TypeError):lat=lon=None
            entry={'id':'tm-'+str(ev.get('id',sha1(title.encode()).hexdigest()[:12])), 'title':title,
                   'date':d,'time':ev.get('dates',{}).get('start',{}).get('localTime','')[:5] or None,
                   'city':city,'venue':venue.get('name') or 'Venue TBA','country':venue.get('country',{}).get('countryCode',''),
                   'category':group,'styles':tags,'artists':[title],'type':'festival' if 'festival' in title.lower() else 'gig',
                   'url':ev.get('url',''),'status':'on-sale','source':'Ticketmaster Discovery API',
                   'note':'Found via Ticketmaster; verify the lineup and tickets with the promoter.','curated':False,
                   'firstSeen':checked,'lastVerified':checked}
            if lat is not None:entry.update(lat=lat,lon=lon)
            if entry['url'].startswith('https://'):results.append(entry)
        time.sleep(.1)
    return results


def similar(a,b):
    if a['date']!=b['date'] or a['city'].lower()!=b['city'].lower():return False
    if a['url'].rstrip('/')==b['url'].rstrip('/'):return True
    if a.get('venue','').lower()!=b.get('venue','').lower():return False
    an=re.sub(r'[^a-z0-9 ]','',a['title'].lower());bn=re.sub(r'[^a-z0-9 ]','',b['title'].lower())
    if an in bn or bn in an:return True
    return SequenceMatcher(None,an,bn).ratio()>.66


def merge(existing:list,new:list,today:str)->list:
    merged=[e for e in existing if e.get('date','')>=today and e.get('url','').startswith('https://')]
    for candidate in new:
        found=next((e for e in merged if similar(e,candidate)),None)
        if found:
            # Preserve human-written descriptions, genres, and verified official URLs.
            found['lastVerified']=today
            found['status']=candidate.get('status',found.get('status','on-sale'))
            if not found.get('time') and candidate.get('time'):found['time']=candidate['time']
        else:merged.append(candidate)
    merged.sort(key=lambda e:(e['date'],e.get('time') or '20:00',e['title']))
    return merged


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true',help='Inspect results without writing files')
    parser.add_argument('--no-network',action='store_true',help='Validate existing data locally')
    args=parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    payload=json.loads(EVENTS_FILE.read_text(encoding='utf-8'))
    checked=datetime.now(timezone.utc).date().isoformat()
    scanned=[];errors=[];attempted=0;new=[]
    if not args.no_network:
        for src in SOURCES:
            try:
                results,ok=crawl_official(src,checked)
                new.extend(results)
                if ok:scanned.append(src['id']);attempted+=1
                else:
                    errors.append({'source':src['id'],'error':'No event links found; venue markup may have changed'})
                    LOG.warning('%s: no event links detected; retained existing listings',src['id'])
                LOG.info('%s: %d genre-matching future events',src['id'],len(results))
            except (requests.RequestException,ValueError) as exc:
                errors.append({'source':src['id'],'error':str(exc)[:140]})
                LOG.warning('%s failed; original data preserved: %s',src['id'],str(exc)[:130])
        if os.environ.get('TICKETMASTER_API_KEY'):
            try:
                tm=crawl_ticketmaster(os.environ['TICKETMASTER_API_KEY'],checked)
                new+=tm;scanned.append('ticketmaster');LOG.info('Ticketmaster: %d matching events',len(tm))
            except (requests.RequestException,ValueError) as exc:
                errors.append({'source':'ticketmaster','error':str(exc)[:140]})
    merged=merge(payload['events'],new,checked)
    LOG.info('All events after merge: %d (%d scraped matches)',len(merged),len(new))
    if args.dry_run or args.no_network:return
    # Only claim the feed was refreshed if a network source really responded.
    if attempted or new:
        payload['events']=merged
        payload['meta'].update(updatedAt=datetime.now(timezone.utc).isoformat(timespec='seconds'),sourcesChecked=attempted,
                               mode='automated scan',scanStatus='ok' if not errors else 'partial',scanErrors=errors)
        EVENTS_FILE.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        JS_FILE.write_text('window.SONIC_DATA = '+json.dumps(payload,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    else:
        LOG.warning('All sources failed, leaving original dataset untouched')


if __name__=='__main__':main()
