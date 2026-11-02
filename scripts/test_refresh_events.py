"""Small offline test suite; no official venue requests or API credentials required."""
import unittest
from datetime import datetime, timezone, timedelta
from refresh_events import classify, parse_date, date_in_url, parse_detail, merge, geohash, take_candidates
from bs4 import BeautifulSoup

class DateParsingTests(unittest.TestCase):
    def test_url_date(self):
        self.assertEqual(date_in_url('https://muziekgieterij.nl/event/bodega-2027-03-04/'), '2027-03-04')
        self.assertEqual(date_in_url('https://nieuwenor.nl/programma/2026/11/27/hard-surface'), '2026-11-27')
        self.assertEqual(date_in_url('https://example.org/agenda/complex-28-11-26'), None)

    def test_dutch_dates(self):
        self.assertEqual(parse_date('Zaterdag 21 november 2026'), '2026-11-21')
        self.assertEqual(parse_date('zo 07 mrt 2027'), '2027-03-07')

    def test_english_dates(self):
        self.assertEqual(parse_date('Sun Mar 7th 2027'), '2027-03-07')
        self.assertEqual(parse_date('2027-03-07T21:00:00+01:00'), '2027-03-07')

class ClassificationTests(unittest.TestCase):
    def test_hard_techno(self):
        category, tags = classify('The Vault', 'Industrial hard techno & schranz')
        self.assertEqual(category, 'techno')
        self.assertIn('hard techno', tags)

    def test_fast_trance(self):
        self.assertEqual(classify('XTRANCE', 'Hard trance and hard house')[0], 'trance')
        self.assertEqual(classify('Arman John', '')[0], 'trance')

    def test_guitars(self):
        self.assertEqual(classify('Slomosa', 'Heavy Norwegian riffs')[0], 'rock')
        self.assertEqual(classify('Basement Gig', 'Shoegaze noise rock')[0], 'rock')

    def test_skip_generic(self):
        self.assertIsNone(classify('Cooking Workshop', 'Fresh ingredients and recipes'))

class SourceTests(unittest.TestCase):
    def test_deduplicate_and_filter_links(self):
        source={'url':'https://complexmaastricht.nl/','pattern':r'^/agenda/[^/]+/?$','limit':30}
        html='<a href="/agenda/real-show">Industrial techno</a><a href="/agenda/real-show">Repeat</a><a href="https://other.example/agenda/untested">Other domain</a>'
        found=take_candidates(BeautifulSoup(html,'html.parser'),source)
        self.assertEqual(len(found),1)

    def test_parse_jsonld_event(self):
        day=(datetime.now(timezone.utc)+timedelta(days=18)).date().isoformat()
        html=f'''<html><main><h1>Altruism: Onlynumbers</h1><p>Industrial hard techno and schranz</p></main><script type="application/ld+json">{{"@type":"MusicEvent","name":"Altruism: Onlynumbers","startDate":"{day}T23:00:00+01:00"}}</script></html>'''
        source={'id':'complex','city':'Maastricht','country':'NL','venue':'Complex'}
        ev=parse_detail(html,'https://complexmaastricht.nl/agenda/onlynumbers',source,datetime.now(timezone.utc).date().isoformat())
        self.assertIsNotNone(ev)
        self.assertEqual(ev['category'],'techno')
        self.assertEqual(ev['date'],day)
        self.assertEqual(ev['time'],'23:00')

    def test_low_tickets_not_sold_out(self):
        day=(datetime.now(timezone.utc)+timedelta(days=8)).date().isoformat()
        html=f'<main><h1>Night: Arman John</h1><p>Almost sold out. Fast hard trance.</p><time datetime="{day}"></time></main>'
        ev=parse_detail(html,'https://complexmaastricht.nl/agenda/arman-john',{'id':'complex','city':'Maastricht','country':'NL','venue':'Complex'},day)
        self.assertEqual(ev['status'],'low-tickets')

    def test_merge_preserves_curated(self):
        day=(datetime.now(timezone.utc)+timedelta(days=8)).date().isoformat()
        original={'id':'original','date':day,'city':'Maastricht','venue':'Complex','title':'Altruism Onlynumbers','url':'https://complexmaastricht.nl/agenda/show','note':'Hand-checked description','status':'on-sale'}
        scanned={'id':'scan','date':day,'city':'Maastricht','venue':'Complex','title':'Altruism Onlynumbers','url':'https://complexmaastricht.nl/agenda/show','status':'sold-out'}
        result=merge([original],[scanned],datetime.now(timezone.utc).date().isoformat())
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['note'],'Hand-checked description')
        self.assertEqual(result[0]['status'],'sold-out')

if __name__=='__main__': unittest.main()
