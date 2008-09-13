import os
import sys
import re
import time
from optparse import OptionParser
from wsgiref import util
from wsgiref.headers import Headers
from wsgiref.simple_server import make_server, demo_app


# doc root
DOCUMENT_ROOT = os.path.join(os.path.dirname(__file__), 'public')

# file extention -> content type
DEFAULT_MIME_TYPES = {
    '.txt':  'text/plain',
    '.html': 'text/html',
    '.htm':  'text/html',
    '.css':  'text/css',

    '.js':   'application/x-javascript',
    '.pdf':  'application/pdf',
    '.rdf':  'application/rdf+xml',
    '.swf':  'application/x-shockwave-flash',

    '.zip':  'application/zip',
    '.tar':  'application/x-tar',
    '.gz':  'application/x-gzip',

    '.bmp':  'image/bmp',
    '.gif':  'image/gif',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.tif': 'image/tiff',
    '.tiff': 'image/tiff',
    
    '.png':  'image/png',
    '.ico':  'image/vnd.microsoft.icon',
}


def normalize_path(path):
    """Returns expanded and normalized ``path``"""
    return os.path.abspath(os.path.expanduser(path))

def request_path(environ):
    """Get a requested path from environ"""
    path = environ.get('PATH_INFO', '/')
    # default index.html
    if path == '' or path == '/':
        path = '/index.html'
    return path

def strftime_rfc822(sec):
    return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(sec))


class FileSystemMiddleware(object):
    """WSGI Middleware object that serves static files."""

    def __init__(self, pattern, path, docroot, mimetypes=None, follow_symlink=False, application=None):
        assert application and callable(application)

        self.re = re.compile(pattern)
        self.path = path
        self.follow_symlink = follow_symlink
        self.application = application

        self.docroot = normalize_path(docroot)
        self.mimetypes = dict(DEFAULT_MIME_TYPES)
        if mimetypes:
            self.mimetypes.update(mimetypes)

    def __call__(self, environ, start_response):
        match = self.re.match(request_path(environ))
        if match:
            path = match.expand(self.path)
            mimetype = self.find_mime_type(os.path.basename(path))
            if mimetype:
                # static file handling
                return self.handle_file(path, mimetype, environ, start_response)

        if self.application:
            return self.application(environ, start_response);
        else:
            return self.report_error("404 Not Found", start_response)

    def real_path(self, path):
        real_path = normalize_path('/'.join([self.docroot, path]))
        if not real_path.startswith(self.docroot):
            # unsafe file access
            return None
        return real_path

    def find_mime_type(self, filename):
        try:
            index = filename.rindex('.')
        except ValueError:
            return None
        else:
            assert index < len(filename)
            extention = filename[index:].lower()
            return self.mimetypes.get(extention)

    def make_headers(self, headers):
        h = Headers([("Allow", "GET, HEAD")])
        for item in headers:
            h.add_header(item[0], item[1])
        return h.items()

    def report_error(self, status, start_response):
        headers = self.make_headers([("Content-Type", "text/plain")])
        start_response(status, headers)
        return ['<html><head><title>%s</title></head><body><h1>%s</h1></body></html>\n' % (status, status)]

    def handle_file(self, path, mimetype, environ, start_response):
        """Handling static content request"""

        assert path and mimetype and environ and start_response
        method = environ["REQUEST_METHOD"]
        filepath = self.real_path(path)

        # error check
        if not method in ('GET', 'HEAD'):
            return self.report_error("405 Method Not Allowed")
        if not filepath or (not self.follow_symlink and os.path.islink(filepath)):
            return self.report_error("403 Forbidden", start_response)
        if not os.path.exists(filepath):
            return self.report_error("404 Not Found", start_response)

        # stat file
        try:
            mtime = time.gmtime(os.path.getmtime(filepath))
            headers = self.make_headers([
                ("Content-Type", mimetype),
                ("Content-Length", str(os.path.getsize(filepath))),
                ("Last-Modified", strftime_rfc822(os.path.getmtime(filepath))),
            ])
            start_response("200 OK", headers)
        except IOError:
            return self.report_error("500 Internal Server Error", start_response)

        if method == 'HEAD':
            return [""]

        # open file
        try:
            f = open(filepath)
        except IOError:
            return self.report_error("500 Internal Server Error", start_response)
        else:
            return util.FileWrapper(f)


def main(options):
    """Main routine"""

    application = demo_app
    application = FileSystemMiddleware(
        pattern=r'/(.*)$',
        path=r'\1',
        docroot=DOCUMENT_ROOT,
        application=application)

    httpd = make_server(options.address, options.port, application)
    print "Serving HTTP on %s:%d..." % httpd.server_address
    httpd.serve_forever()


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-l", "--address", dest="address", default="127.0.0.1",
        help="listen IP address (127.0.0.1)")
    parser.add_option("-p", "--port", dest="port", type='int', default=8000,
        help="port number (8000)")
    parser.add_option("-q", "--quiet", dest="verbose", default=True, action="store_false",
        help="don't print debug messages")
    (options, args) = parser.parse_args()

    main(options)
