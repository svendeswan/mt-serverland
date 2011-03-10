"""
Implementation of a worker server that connects to Google Translate.
"""
import re
import sys
import urllib
import urllib2

from workers.worker import AbstractWorkerServer
from protobuf.TranslationRequestMessage_pb2 import TranslationRequestMessage


class GoogleWorker(AbstractWorkerServer):
    """
    Implementation of a worker server that connects to Google Translate.
    """
    __name__ = 'GoogleWorker'
    __splitter__ = '[GOOGLE_SPLITTER_TOKEN]'

    def language_pairs(self):
        """
        Returns a tuple of all supported language pairs for this worker.
        """
        languages = ('afr', 'alb', 'ara', 'arm', 'aze', 'baq', 'bel', 'bul',
          'cat', 'chi', 'hrv', 'cze', 'dan', 'dut', 'eng', 'est', 'phi',
          'fin', 'fre', 'glg', 'geo', 'ger', 'gre', 'hat', 'heb', 'hin',
          'hun', 'ice', 'ind', 'gla', 'ita', 'jpn', 'kor', 'lav', 'lit',
          'mac', 'may', 'mlt', 'nor', 'per', 'pol', 'por', 'rum', 'rus',
          'srp', 'slo', 'slv', 'spa', 'swa', 'swe', 'tha', 'tur', 'ukr',
          'urd', 'vie', 'wel', 'yid')
        return tuple([(a,b) for a in languages for b in languages if a != b])

    def language_code(self, iso639_2_code):
        """
        Converts a given ISO-639-2 code into the worker representation.

        Returns None for unknown languages.
        """
        mapping = {
          'afr': 'af', 'alb': 'sq', 'ara': 'ar', 'arm': 'hy', 'aze': 'az',
          'baq': 'eu', 'bel': 'be', 'bul': 'bg', 'cat': 'ca', 'chi': 'zh-CN',
          'hrv': 'hr', 'cze': 'cs', 'dan': 'da', 'dut': 'nl', 'eng': 'en',
          'est': 'et', 'phi': 'tl', 'fin': 'fi', 'fre': 'fr', 'glg': 'gl',
          'geo': 'ka', 'ger': 'de', 'gre': 'el', 'hat': 'ht', 'heb': 'iw',
          'hin': 'hi', 'hun': 'hu', 'ice': 'is', 'ind': 'id', 'gla': 'ir',
          'ita': 'it', 'jpn': 'ja', 'kor': 'ko', 'lav': 'lv', 'lit': 'lt',
          'mac': 'mk', 'may': 'ms', 'mlt': 'mt', 'nor': 'no', 'per': 'fa',
          'pol': 'pl', 'por': 'pt', 'rum': 'ro', 'rus': 'ru', 'srp': 'sr',
          'slo': 'sk', 'slv': 'sl', 'spa': 'es', 'swa': 'sw', 'swe': 'sv',
          'tha': 'th', 'tur': 'tr', 'ukr': 'uk', 'urd': 'ur', 'vie': 'vi',
          'wel': 'cy', 'yid': 'yi'
        }
        return mapping.get(iso639_2_code)

    def handle_translation(self, request_id):
        """
        Translation handler that obtains a translation via the Google
        translation web front end.
        """
        handle = open('/tmp/{0}.message'.format(request_id), 'r+b')
        message = TranslationRequestMessage()
        message.ParseFromString(handle.read())

        source = self.language_code(message.source_language)
        target = self.language_code(message.target_language)

        # Insert splitter tokens to allow re-construction of original lines.
        _source_text = []
        for source_line in message.source_text.split('\n'):
            _source_text.append(source_line.strip().encode('utf-8'))
            _source_text.append(self.__splitter__)

        the_url = 'http://translate.google.com/translate_t'
        the_data = urllib.urlencode({'js': 'n', 'sl': source, 'tl': target,
          'text': u'\n'.join(_source_text)})
        the_header = {'User-agent': 'Mozilla/5.0'}

        opener = urllib2.build_opener(urllib2.HTTPHandler)
        http_request = urllib2.Request(the_url, the_data, the_header)
        http_handle = opener.open(http_request)
        content = http_handle.read()
        http_handle.close()

        result_exp = re.compile('<span id=result_box.*?>(.*)</span></div>',
          re.I|re.U|re.S)

        result = result_exp.search(content)

        if result:
            # Normalize HTML line breaks to \n.
            result = result.group(1).replace('<br>', '\n')

            # Extract all <span>...</span> tags containing the translation.
            span_exp = re.compile('<span.*?>([^<]+?)</span>', re.I|re.U|re.S)
            span_iter = span_exp.finditer(result)
            spans = [unicode(match.group(1), 'utf-8') for match in span_iter]

            # Construct target text from list of spans, normalizing \n+ to \n.
            target_text = u'\n'.join([span.strip() for span in spans])  
            multibreaks = re.compile('\n+', re.I|re.U|re.S)
            target_text = multibreaks.sub(u'\n', target_text)

            # Re-construct original lines using the splitter tokens.
            _target_text = []
            _current_line = []
            for target_line in target_text.split('\n'):
                if target_line.strip() != self.__splitter__:
                    _current_line.append(target_line.strip())
                else:
                    _target_text.append(u' '.join(_current_line))
                    _current_line = []

            message.target_text = u'\n'.join(_target_text)
            handle.seek(0)
            handle.write(message.SerializeToString())

        else:
            message.target_text = "ERROR: result_exp did not match.\n" \
              "CONTENT: {0}".format(content)
            handle.seek(0)
            handle.write(message.SerializeToString())

        handle.close()
