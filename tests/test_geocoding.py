import http.client
import io
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))
import geocoding
from server import Handler

DATA = {'features':[{'properties':{'name':'Rhodes','country':'Greece'},
                      'geometry':{'coordinates':[28.227,36.443]}}]}

class GeocodingTests(unittest.TestCase):
    def setUp(self):
        geocoding._cache.clear(); geocoding._last_request=0

    def test_coordinate_order_labels_and_invalid_results(self):
        data = {'features':DATA['features']*2 + [{'properties':{'name':'Bad'},'geometry':{'coordinates':[20,float('nan')]}}]}
        self.assertEqual(geocoding.parse_places(data),[{'label':'Rhodes, Greece','latitude':36.443,'longitude':28.227}])

    def test_search_encodes_unicode_and_caches(self):
        with patch('geocoding.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(DATA).encode())) as fetch:
            first = geocoding.search_places('Ρόδος, Ελλάδα')
            self.assertEqual(first,geocoding.search_places('  Ρόδος,   Ελλάδα '))
            self.assertEqual(fetch.call_count,1)
            request = fetch.call_args.args[0]
            self.assertIn('%CE',request.full_url)
            self.assertIn('RFTrafficMonitor',request.get_header('User-agent'))

    def test_invalid_input_and_offline_failure(self):
        for query in (None,'a','x'*161):
            with self.assertRaises(ValueError):geocoding.search_places(query)
        with patch('geocoding.urllib.request.urlopen',side_effect=OSError('offline')):
            with self.assertRaisesRegex(LookupError,'coordinates manually'):geocoding.search_places('Rhodes')
        self.assertEqual(len(geocoding._cache),0)

    def test_rate_limit_and_empty_results(self):
        with patch('geocoding.time.monotonic',return_value=10),patch('geocoding.time.sleep') as sleep,patch('geocoding.urllib.request.urlopen',side_effect=lambda *a,**k:io.BytesIO(b'{"features":[]}')):
            self.assertEqual(geocoding.search_places('Athens'),[])
            self.assertEqual(geocoding.search_places('Milan'),[])
            self.assertEqual(sleep.call_args.args[0],1.0)

    def test_authenticated_endpoint_does_not_change_config(self):
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.controller = type('Controller',(),{'token':'test-token'})()
        worker = threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            conn = http.client.HTTPConnection('127.0.0.1',server.server_port)
            with patch('server.search_places',return_value=geocoding.parse_places(DATA)) as search:
                conn.request('POST','/api/place-search',body='{"query":"Rhodes"}')
                response=conn.getresponse();self.assertEqual(response.status,403);response.read();search.assert_not_called()
                conn.request('POST','/api/place-search',body='{"query":"Rhodes"}',headers={'X-Radar-Token':'test-token'})
                response=conn.getresponse();self.assertEqual(response.status,200)
                self.assertEqual(json.loads(response.read())['results'][0]['latitude'],36.443)
            with patch('server.search_places',side_effect=LookupError('Search unavailable')):
                conn.request('POST','/api/place-search',body='{"query":"Rhodes"}',headers={'X-Radar-Token':'test-token'})
                response=conn.getresponse();self.assertEqual(response.status,503);response.read()
            conn.close()
        finally:
            server.shutdown();server.server_close();worker.join()

if __name__=='__main__':unittest.main()
