import sys
import urllib
import ted_talks_scraper
from talkDownloader import Download
from model.fetcher import Fetcher
from model.user import User
from model.rss_scraper import NewTalksRss
from model.favorites_scraper import Favorites
import menu_util
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon

__settings__ = xbmcaddon.Addon(id='plugin.video.ted.talks')
getLS = __settings__.getLocalizedString


def login(user_scraper, username, password):
    user_details = user_scraper.login(username, password)
    if not user_scraper:
        xbmcgui.Dialog().ok(getLS(30050), getLS(30051))
    return user_details


class UI:

    def __init__(self, logger, get_HTML, ted_talks, user, settings):
        self.logger = logger
        self.get_HTML = get_HTML
        self.ted_talks = ted_talks
        self.user = user
        self.settings = settings
        xbmcplugin.setContent(int(sys.argv[1]), 'movies')

    def endofdirectory(self, sortMethod = 'title'):
        # set sortmethod to something xbmc can use
        if sortMethod == 'title':
            sortMethod = xbmcplugin.SORT_METHOD_LABEL
        elif sortMethod == 'date':
            sortMethod = xbmcplugin.SORT_METHOD_DATE
        #Sort methods are required in library mode.
        xbmcplugin.addSortMethod(int(sys.argv[1]), sortMethod)
        #let xbmc know the script is done adding items to the list.
        xbmcplugin.endOfDirectory(handle = int(sys.argv[1]), updateListing = False)

    def addItem(self, title, mode, url = None, img = None, video_info = {}, talkID = None, isFolder = True):
        # Create action url
        args = {'mode': mode}
        if url:
            args['url'] = url
        if img:
            args['icon'] = img
        args = [k + '=' + urllib.quote_plus(v.encode('ascii', 'ignore')) for k, v in args.iteritems()]
        action_url = sys.argv[0] + '?' + "&".join(args)

        li = xbmcgui.ListItem(label = title, iconImage = img, thumbnailImage = img)
        video_info = dict((k, v) for k, v in video_info.iteritems() if k in ['date', 'duration', 'plot'])
        if len(video_info) > 0:
            li.setInfo('video', video_info)
        if not isFolder:
            li.setProperty("IsPlayable", "true") #let xbmc know this can be played, unlike a folder.
            context_menu = menu_util.create_context_menu(getLS = getLS, favorites_action = 'add', talkID = talkID)
            li.addContextMenuItems(context_menu, replaceItems = True)
        else:
            li.addContextMenuItems([], replaceItems = True)
        #add item to list
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=action_url, listitem=li, isFolder=isFolder)

    def playVideo(self, url, icon):
        video = self.ted_talks.getVideoDetails(url)
        li=xbmcgui.ListItem(video['Title'],
                            iconImage = icon,
                            thumbnailImage = icon,
                            path = video['url'])
        li.setInfo(type='Video', infoLabels=video)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)

    def navItems(self, navItems, mode):
        if navItems['next']:
            self.addItem(getLS(30020), mode, navItems['next'])
        if navItems['previous']:
            self.addItem(getLS(30021), mode, navItems['previous'])

    def showCategories(self):
        self.addItem(getLS(30001), 'newTalksRss', video_info = {'Plot':getLS(30031)})
        self.addItem(getLS(30002), 'speakers', video_info = {'Plot':getLS(30032)})
        self.addItem(getLS(30003), 'themes', video_info = {'Plot':getLS(30033)})
        #self.addItem({'Title':getLS(30004), 'mode':'search', 'Plot':getLS(30034)})
        if self.settings['username']:
            self.addItem(getLS(30005), 'favorites', video_info = {'Plot':getLS(30035)})
        self.endofdirectory()
        
    def newTalksRss(self):
        newTalks = NewTalksRss(self.logger)
        for talk in newTalks.get_new_talks():
            self.addItem(talk['title'], 'playVideo', talk['link'], talk['thumb'], talk, talk['id'], isFolder = False)
        self.endofdirectory(sortMethod = 'date')

    def speakers(self):
        speakers = ted_talks_scraper.Speakers(self.get_HTML, None)
        #add speakers to the list
        for title, link in speakers.getAllSpeakers():
            self.addItem(title, 'speakerVids', link, isFolder = True)
        #end the list
        self.endofdirectory()

    def speakerVids(self, url):
        speakers = ted_talks_scraper.Speakers(self.get_HTML, url)
        for title, link, img in speakers.getTalks():
            self.addItem(title, 'playVideo', link, img, isFolder = False)
        #end the list
        self.endofdirectory()

    def themes(self):
        themes = self.ted_talks.Themes(self.get_HTML, None)
        #add themes to the list
        for title, link, img in themes.getThemes():
            self.addItem(title, 'themeVids', link, img, isFolder = True)
        #end the list
        self.endofdirectory()

    def themeVids(self, url):
        themes = self.ted_talks.Themes(self.get_HTML, url)
        for title, link, img in themes.getTalks():
            self.addItem(title, 'playVideo', link, img, isFolder = False)
        self.endofdirectory()

    def favorites(self):
        newMode = 'playVideo'
        #attempt to login
        userID, realname = login(self.user, self.settings['username'], self.settings['password'])
        if userID:
            for talk in Favorites(self.logger, self.get_HTML).getFavoriteTalks(userID):
                talk['mode'] = newMode
                self.addItem(talk, isFolder = False)
            self.endofdirectory()


class Action(object):
    '''
    Some action that can be executed by the user.
    '''
    
    def __init__(self, mode, required_args, logger):
        self.mode = mode
        self.required_args = set(required_args)
        self.logger = logger
    
    def run(self, args):
        good = self.required_args.issubset(args.keys())
        if good:
            self.run_internal(args)
        else:
            self.report_problem(args)
    
    def report_problem(self, args):
        # The theory is that this might happen for a favorite from another version;
        # though we can't be sure about the cause hence vagueness in friendly message.
        friendly_message = "Action '%s' failed. Try re-creating the item." % (self.mode)
        self.logger("%s\nBad arguments: %s" % (friendly_message, args), friendly_message)
    

class PlayVideoAction(Action):
    
    def __init__(self, logger, ui):
        super(PlayVideoAction, self).__init__('playVideo', ['url', 'icon'], logger)
        self.ui = ui

    def run_internal(self, args):
        self.ui.playVideo(args['url'], args['icon'])


class NewTalksAction(Action):
    
    def __init__(self, logger, ui):
        super(NewTalksAction, self).__init__('newTalksRss', [], logger)
        self.ui = ui

    def run_internal(self, args):
        self.ui.newTalksRss()


class SpeakersAction(Action):
    
    def __init__(self, logger, ui):
        super(SpeakersAction, self).__init__('speakers', [], logger)
        self.ui = ui

    def run_internal(self, args):
        self.ui.speakers()

        
class SpeakerVideosAction(Action):
    
    def __init__(self, logger, ui):
        super(SpeakerVideosAction, self).__init__('speakerVids', ['url'], logger)
        self.ui = ui

    def run_internal(self, args):
        self.ui.speakerVids(args['url'])

        
class ThemesAction(Action):
    
    def __init__(self, logger, ui):
        super(ThemesAction, self).__init__('themes', [], logger)
        self.ui = ui

    def run_internal(self, args):
        self.ui.themes()

        
class ThemeVideosAction(Action):
    
    def __init__(self, logger, ui):
        super(ThemeVideosAction, self).__init__('themeVids', ['url'], logger)
        self.ui = ui

    def run_internal(self, args):
        self.ui.themeVids(args['url'])

        
class FavoritesAction(Action):
    
    def __init__(self, logger, ui):
        super(FavoritesAction, self).__init__('favorites', [], logger)
        self.ui = ui

    def run_internal(self, args):
        self.ui.favorites()

        
class SetFavoriteAction(Action):
    
    def __init__(self, logger, main):
        super(SetFavoriteAction, self).__init__('addToFavorites', ['talkID'], logger)
        self.main = main

    def run_internal(self, args):
        self.main.set_favorite(args['talkID'], True)

        
class RemoveFavoriteAction(Action):
    
    def __init__(self, logger, main):
        super(RemoveFavoriteAction, self).__init__('removeFromFavorites', ['talkID'], logger)
        self.main = main

    def run_internal(self, args):
        self.main.set_favorite(args['talkID'], False)
        
        
class DownloadVideoAction(Action):
    
    def __init__(self, logger, main):
        super(DownloadVideoAction, self).__init__('downloadVideo', ['url'], logger)
        self.main = main

    def run_internal(self, args):
        self.main.downloadVid(args['url'], False)


class Main:

    def __init__(self, logger, args_map):
        self.logger = logger
        self.args_map = args_map
        self.getSettings()
        self.get_HTML = Fetcher(logger, xbmc.translatePath).getHTML
        self.user = User(self.get_HTML)
        self.ted_talks = ted_talks_scraper.TedTalks(self.get_HTML)

    def getSettings(self):
        self.settings = dict()
        self.settings['username'] = __settings__.getSetting('username')
        self.settings['password'] = __settings__.getSetting('password')
        self.settings['downloadMode'] = __settings__.getSetting('downloadMode')
        self.settings['downloadPath'] = __settings__.getSetting('downloadPath')

    def set_favorite(self, talkID, is_favorite):
        """
        talkID ID for the talk.
        is_favorite True to set as a favorite, False to unset.
        """
        if login(self.user, self.settings['username'], self.settings['password']):
            favorites = Favorites(self.logger, self.get_HTML)
            if is_favorite:
                successful = favorites.addToFavorites(talkID)
            else:
                successful = favorites.removeFromFavorites(talkID)
            notification_messages = {(True, True): 30091, (True, False): 30092, (False, True): 30094, (False, False): 30095}
            notification_message = notification_messages[(is_favorite, successful)]
            xbmc.executebuiltin('Notification(%s,%s,)' % (getLS(30000), getLS(notification_message)))

    def downloadVid(self, url):
        video = self.ted_talks.getVideoDetails(url)
        if self.settings['downloadMode'] == 'true':
            downloadPath = xbmcgui.Dialog().browse(3, getLS(30096), 'files')
        else:
            downloadPath = self.settings['downloadPath']
        if downloadPath:
            Download(video['Title'], video['url'], downloadPath)

    def run(self):
        ui = UI(self.logger, self.get_HTML, self.ted_talks, self.user, self.settings)
        if 'mode' not in self.args_map:
            ui.showCategories()
        else:
            modes = [
                PlayVideoAction(self.logger, ui),
                NewTalksAction(self.logger, ui),
                SpeakersAction(self.logger, ui),
                SpeakerVideosAction(self.logger, ui),
                ThemesAction(self.logger, ui),
                ThemeVideosAction(self.logger, ui),
                FavoritesAction(self.logger, ui),
                SetFavoriteAction(self.logger, self),
                RemoveFavoriteAction(self.logger, self),
                DownloadVideoAction(self.logger, self),
            ]
            modes = dict([(m.mode, m) for m in modes])
            mode = self.args_map['mode']
            if mode in modes:
                modes[mode].run(self.args_map)
            else:
                # Bit of a hack (cough)
                Action(mode, [], self.logger).report_problem(self.args_map)
