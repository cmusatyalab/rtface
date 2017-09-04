#! /usr/bin/env python2
import BaseHTTPServer, SimpleHTTPServer
import ssl

httpd = BaseHTTPServer.HTTPServer(('0.0.0.0', 10002), SimpleHTTPServer.SimpleHTTPRequestHandler)
httpd.socket = ssl.wrap_socket(httpd.socket, keyfile='../../server.pem', certfile='../../cert.pem', server_side=True)
httpd.serve_forever()
