import json
import urllib
import urllib2
import StringIO
import zlib, gzip
import socket
import collections

USER_AGENT = 'SickbeardApiClient/alpha'

def getURL(url, post_data=None, headers=[]):
    """
    Returns a byte-string retrieved from the url provider.
    """

    opener = urllib2.build_opener()
    opener.addheaders = [('User-Agent', USER_AGENT), ('Accept-Encoding', 'gzip,deflate')]
    for cur_header in headers:
        opener.addheaders.append(cur_header)

    usock = opener.open(url, post_data)
    url = usock.geturl()
    encoding = usock.info().get("Content-Encoding")

    if encoding in ('gzip', 'x-gzip', 'deflate'):
        content = usock.read()
        if encoding == 'deflate':
            data = StringIO.StringIO(zlib.decompress(content))
        else:
            data = gzip.GzipFile('', 'rb', 9, StringIO.StringIO(content))
        result = data.read()
    else:
        result = usock.read()
    usock.close()
    return result


class Sickbeard(object):
    protocol = "http"
    hostname = "localhost"
    port = 8081
    api_key = ""
    path = ""

    def __init__(self, hostname, api_key, port=8081, protocol="http", path=""):
        self.hostname = hostname
        self.api_key = api_key
        self.port = port
        self.protocol = protocol
	self.path = path
    
    def __str__(self):
        return "%s://%s:%i%s/api/%s" % (self.protocol, self.hostname, int(self.port), self.path, self.api_key)

class SickbeardAPIException(Exception):
    "Error in API of Sickbeard"
        
    def __init__(self, msg, sickbeard=None, url=None, response=None):
        self.msg = msg
        self.sickbeard = sickbeard
        self.url = url
        self.reponse = response
        
    def __str__(self):
        return repr(self.msg)

class SickbeardAPI():
    """
    Sickbeard API Client
    """
    sickbeard = None 
    
    class Show:
        """
        a TV show
        """
        
        def __init__(self, sickbeard_api, kwargs):
            self.sickbeard_api = sickbeard_api
            for k,v in kwargs.iteritems():
                setattr(self, str(k), v)
                
        def season(self, season_number):
            return SickbeardAPI.Season(season_number, self.sickbeard_api, self.sickbeard_api.get('show.seasons', {"tvdbid":self.tvdbid, "season":season_number}))
        
        @property
        def seasons(self):
            for number, season in self.sickbeard_api.get('show.seasons', {"tvdbid":self.tvdbid}).iteritems():
                yield SickbeardAPI.Season(number, self.sickbeard_api, season)
        
        def seasonlist(self):    
            return self.sickbeard_api.get('show.seasonlist', {"tvdbid":self.tvdbid})
        
        def refresh(self):
            return self.sickbeard_api.get('show.refresh', {"tvdbid":self.tvdbid})
        
        def pause(self, state=1):
            return self.sickbeard_api.get('show.pause', {"tvdbid":self.tvdbid, 'state':state})
        
        def unpause(self):
            return self.pause(state=0)
        
        def getBanner(self):
            return self.sickbeard_api.get('show.getbanner', {'tvdbid':self.tvdbid})
        
        def getPoster(self):
            return self.sickbeard_api.get('show.getposter', {'tvdbid':self.tvdbid})
        
        def getQuality(self):
            return self.sickbeard_api.get('show.getquality', {'tvdbid':self.tvdbid})
        
        def stats(self):
            return self.sickbeard_api.get('show.stats', {'tvdbid':self.tvdbid})
        
        def update(self):
            return self.sickbeard_api.get('show.update', {'tvdbid':self.tvdbid})
        
        def __str__(self):
            return self.show_name
    
    class Season:
        """
        Season of a TV show
        """
        number = 0
        _episodes = None
        
        # @todo: fix this
        def __init__(self, number, sickbeard_api, episodes):
            self.number = int(number)
            self.sickbeard_api = sickbeard_api
            # due to memory prob, temp fix
            self._episodes = {}
            for k,v in episodes.iteritems():
                self._episodes[k] = SickbeardAPI.Episode(number, k, self.sickbeard_api, v)
        
        @property
        def episodes(self):
            for episode in self._episodes.itervalues():
                yield episode
        
        def episode(self, season, episode, full_path=1):
            if self._episodes.haskey(episode):
                return self._episode[episode]
            return SickbeardAPI.Episode(self.number, self.sickbeard_api.get('episode', {"tvdbid":self.tvdbid, "season":season, "episode":episode, "full_path":full_path}))
        
        def __str__(self):
            return self.number
        
        def setStatus(self, status, force=0):
            if status not in self.Episode._status:
                raise SickbeardAPIException("Unkown status \"%s\, must be one of %s" % (status, "".join(self._status)))
            return self.sickbeard_api.get(episode.setstatus, {'tvdbid':self.tvdbid, 'season':self.number, 'status':status, 'force':force})
    
    class Episode:
        """
        Episode of season of a TV show
        """
        number = 0
        tvdbid = None
        location = "" 
        name = ""
        quality = None
        release_name = ""
        status = ""
        season = 0
        _status = ('wanted', 'skipped', 'archived', 'ignored')
        
        def __init__(self, season, number, sickbeard_api, kwargs):
            self.number = int(number)
            self.sickbeard_api = sickbeard_api
            for k,v in kwargs.iteritems():
                setattr(self, str(k), v)
        
        def setStatus(self, status, force=0):
            if status not in self._status:
                raise SickbeardAPIException("Unkown status \"%s\, must be one of %s" % (status, "".join(self._status)))
            return self.sickbeard_api.get(episode.setstatus, {'tvdbid':self.tvdbid, 'season':self.season, 'episode':self.number, 'status':status, 'force':force})
    
    def __init__(self, sickbeard):
        if not isinstance(sickbeard, Sickbeard):
            raise SickbeardAPIException("Sickbeard no good....");
        self.sickbeard = sickbeard
        self.ping()
        
    def ping(self):
        if self.get('sb.ping'):
            return True
        return False

    def build_url(self, cmd, params={}):
        sb = self.sickbeard
        return "%s://%s:%i%s/api/%s/?cmd=%s&%s" % (sb.protocol, sb.hostname, int(sb.port), sb.path, sb.api_key, cmd, urllib.urlencode(params))
    
    def get(self, cmd, params={}):
        try:
            data = getURL(self.build_url(cmd, params))
            if data is None:
                raise SickbeardAPIException("No response from sickbeard api", self.sickbeard, self.build_url(cmd, params))
            v = json.loads(data, object_pairs_hook=collections.OrderedDict)
            if v['result'] != "success":
                raise SickbeardAPIException(str(v['message']), self.sickbeard, self.build_url(cmd, params), data)                
            return v['data']
        except (AttributeError, KeyError, TypeError) as e:
            raise SickbeardAPIException(str(e), self.sickbeard, self.build_url(cmd, params), data)
        except urllib2.HTTPError as e:
            raise SickbeardAPIException(str(e.code), self.sickbeard, self.build_url(cmd, params), data)
        except urllib2.URLError as e:
            raise SickbeardAPIException(str(e.reason), self.sickbeard, self.build_url(cmd, params), data)
        except socket.timeout:
            raise SickbeardAPIException("timeout", self.sickbeard, self.build_url(cmd, params), data)
        except ValueError:
            raise SickbeardAPIException("Unknown error while loading URL", self.sickbeard, self.build_url(cmd, params), data)
    
    @property
    def shows(self):
        for show in self.get('shows').itervalues():
            yield self.Show(self, show)
        
    def show(self, tvdbid):
        return self.Show(self, self.get('show', {"tvdbid":tvdbid}))
    
    def season(self, tvdbid, season_number):
        return self.Season(season_number, self.sickbeard_api, self.get('show.seasons', {"tvdbid":tvdbid, "season":season_number}))
    
    def episode(self, tvdbid, season, episode, full_path=1):
        return self.Episode(season, self.get('episode', {"tvdbid":tvdbid, "season":season, "episode":episode, "full_path":full_path}))
    
    def history(self, limit=5):
        for episode in self.get('history', {'limit':limit}).itervalues():
            yield self.Episode(episode.season, episode.episode, self, episode)
    
    def history_clear(self):
        return self.get('history.clear', {})
    
    def history_trim(self):
        return self.get('history.trim', {})
    
    def logs(self, min_level='info'):
        levels = ['debug', 'info', 'warning', 'error']
        if min_level not in levels:
            raise SickbeardAPIException("Unkown log level \"%s\, must be one of %s" % (min_level, "".join(levels)))
        return self.get('logs', {'min_level':min_level})
    
    def sb(self):
        return self.get('sb', {})
    
    def sb_getMessage(self):
        return self.get('sb.getmessages', {})
    
    def sb_shutdown(self):
        return self.get('sb.shutdown', {})
    
    def sb_restart(self):
        return self.get('sb.restart', {})
    
    def sb_searchtvdb(self, name=None, tvdbid=None, lang=None):
        return self.get('sb.searchtvdb', {'name':name, 'tvdbid':tvdbid, 'lang':lang})
    
if __name__ == "__main__":
    sb = Sickbeard(hostname="yourdomain.nl", api_key='your_api_key_here')
    try:
        api = SickbeardAPI(sb)
        for show in api.shows:
            print(show.show_name)
            for season in show.seasons:
                print("\t%i" % season.number)
                for episode in season.episodes:
                    print("\t\t %i:%s" % (episode.number, episode.name))
    except SickbeardAPIException as e:
        print e
