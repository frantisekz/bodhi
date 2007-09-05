# $Id: test_controllers.py,v 1.3 2006/12/31 09:10:25 lmacken Exp $

import urllib
import cherrypy
import turbogears

from pprint import pprint
from turbogears import testutil, database, config

from bodhi.model import Release, PackageUpdate, User
from bodhi.controllers import Root

database.set_db_uri("sqlite:///:memory:")
turbogears.update_config(configfile='dev.cfg',
                         modulename='bodhi.config')

cherrypy.root = Root()

class TestControllers(testutil.DBTest):

    def save_update(self, params, session={}):
        pairs = urllib.urlencode(params)
        url = '/updates/save?' + pairs
        print url
        testutil.createRequest(url, headers=session, method='POST')

    def create_release(self):
        rel = Release(name='fc7', long_name='Fedora 7', id_prefix='FEDORA',
                      dist_tag='dist-fc7')
        assert rel

    def login(self, username='guest', display_name='guest'):
        guest = User(user_name=username, display_name=display_name)
        guest.password = 'guest'
        print guest
        testutil.createRequest('/updates/login?tg_format=json&login=Login&forward_url=/updates/&user_name=guest&password=guest', method='POST')
        assert cherrypy.response.status == '200 OK'
        cookies = filter(lambda x: x[0] == 'Set-Cookie',
                         cherrypy.response.header_list)
        cookiehdr = ""
        for cookie in zip(cookies[0], cookies[1])[1]:
            cookiehdr += cookie.split(';')[0] + '\r\n '
        cookiehdr = cookiehdr.strip()
        return { 'Cookie' : cookiehdr }

    def test_bad_password(self):
        x = testutil.createRequest('/updates/login?tg_format=json&login=Login&&user_name=guest&password=foo', method='POST')
        assert "The credentials you supplied were not correct or did not grant access to this resource." in cherrypy.response.body[0]
        assert cherrypy.response.status == '403 Forbidden'

    def test_good_password(self):
        guest = User(user_name='guest')
        guest.password = 'guest'
        x = testutil.createRequest('/updates/login?tg_format=json&login=Login&user_name=guest&password=guest', method='POST')
        assert cherrypy.response.status == '200 OK'

    def test_unauthenticated_update(self):
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '1234 5678',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(params)
        assert "You must provide your credentials before accessing this resource." in cherrypy.response.body[0]

    def test_new_update(self):
        session = self.login()
        self.create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)
        print cherrypy.response.body
        update = PackageUpdate.byTitle(params['builds'])
        assert update
        assert update.title == params['builds']
        assert update.builds[0].nvr == params['builds']
        assert update.release.long_name == params['release']
        assert update.bugs[0].bz_id == int(params['bugs'])
        assert update.cves[0].cve_id == params['cves']
        assert update.notes == params['notes']
        # we specified a CVE, so bodhi will automatically change the type
        assert update.type == 'security'

    def test_multibuild_update(self):
        session = self.login()
        self.create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7',
            'release' : 'Fedora 7',
            'type'    : 'enhancement',
            'bugs'    : '1234 5678',
            'cves'    : '',
            'notes'   : 'foobar'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update
        builds = map(lambda x: x.nvr, update.builds)
        for build in params['builds'].split():
            assert build in builds
        assert update.release.long_name == params['release']
        assert update.type == params['type']
        assert update.notes == params['notes']
        for bug in params['bugs'].split():
            assert int(bug) in map(lambda x: x.bz_id, update.bugs)

    def test_bad_build(self):
        session = self.login()
        params = {
            'builds'  : 'foobar',
            'release' : 'Fedora 7',
            'type'    : 'enhancement',
            'bugs'    : '1234 5678',
            'cves'    : '',
            'notes'   : 'foobar'
        }
        self.save_update(params, session)
        assert "Invalid package name; must be in package-version-release format" in cherrypy.response.body[0]

    def test_bad_release(self):
        session = self.login()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Ubuntu Bitchy Beaver',
            'type'    : 'enhancement',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        assert "Value must be one of: F7; Fedora 7 (not \'Ubuntu Bitchy Beaver\')" in cherrypy.response.body[0]

    def test_bad_type(self):
        session = self.login()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'REGRESSION!',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        pprint(cherrypy.response.body[0])
        assert "Value must be one of: bugfix; enhancement; security (not \'REGRESSION!\')" in cherrypy.response.body[0]

    def test_user_notes_encoding(self):
        session = self.login(username='guest', display_name='foo\xc3\xa9bar')
        self.create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'Foo\u2019bar'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle('TurboGears-1.0.2.2-2.fc7')
        assert update.title == params['builds']
        assert update.builds[0].nvr == params['builds']
        assert update.release.long_name == params['release']
        assert update.notes == params['notes']
