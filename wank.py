#!/usr/bin/env python

import BaseHTTPServer
import SocketServer
import select
import socket
import urlparse

import socks

LISTEN_ADDR = '127.0.0.1'
LISTEN_PORT = 8123

TOR_ADDR = '127.0.0.1'
TOR_PORT = 9050

TIMEOUT = 20

class ProxyHandler (BaseHTTPServer.BaseHTTPRequestHandler):
    rbufsize = 0 # self.rfile Be unbuffered

    def _connect_to(self, netloc, soc):
        i = netloc.find(':')
        if i >= 0:
            host_port = netloc[:i], int(netloc[i+1:])
        else:
            host_port = netloc, 80
        #print "connect to %s:%d" % host_port
        try:
            soc.connect(host_port)
        except Exception:
            #self.send_error(502)
            return False
        return True

    def do_CONNECT(self):
        soc = socks.socksocket()
        soc.setproxy(socks.PROXY_TYPE_SOCKS5, TOR_ADDR, TOR_PORT)
        try:
            if self._connect_to(self.path, soc):
                #self.log_request(200)
                self.wfile.write(self.protocol_version +
                                 " 200 Connection established\r\n")
                self.wfile.write("\r\n")
                self._read_write(soc, 300)
        finally:
            #print "bye"
            soc.close()
            self.connection.close()

    def do_GET(self):
        (scm, netloc, path, params, query, fragment) = urlparse.urlparse(
            self.path, 'http')
        if scm != 'http' or fragment or not netloc:
            self.send_error(400, "bad url %s" % self.path)
            return
        soc = socks.socksocket()
        soc.setproxy(socks.PROXY_TYPE_SOCKS5, TOR_ADDR, TOR_PORT)
        try:
            if self._connect_to(netloc, soc):
                #self.log_request()
                soc.send("%s %s %s\r\n" % (
                    self.command,
                    urlparse.urlunparse(('', '', path, params, query, '')),
                    self.request_version))
                self.headers['Connection'] = 'close'
                del self.headers['Proxy-Connection']
                for header in self.headers.headers:
                    soc.send(header.strip() + '\r\n')
                soc.send("\r\n")
                self._read_write(soc)
        finally:
            #print "bye"
            soc.close()
            self.connection.close()

    def _read_write(self, soc, max_idling=TIMEOUT):
        iw = [self.connection, soc]
        count = 0
        while True:
            count += 1
            (ins, _, exs) = select.select(iw, [], iw, 3)
            if ins:
                for i in ins:
                    if i is soc:
                        out = self.connection
                    else:
                        out = soc
                    data = i.recv(8192)
                    if data:
                        out.send(data)
                        count = 0
            else:
                print "idle", count
            if exs:
                break
            if count == max_idling:
                #self.send_error(504, "Connection timed out")
                break

    do_HEAD   = do_GET
    do_POST   = do_GET
    do_PUT    = do_GET
    do_DELETE = do_GET

class WankProxy(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    def __init__(self):
        BaseHTTPServer.HTTPServer.__init__(self,
                                           (LISTEN_ADDR, LISTEN_PORT),
                                           ProxyHandler)

if __name__ == '__main__':
    try:
        print "Listening on %s:%s..." % (LISTEN_ADDR, LISTEN_PORT)
        httpd = WankProxy()
        httpd.serve_forever()
    except KeyboardInterrupt:
        print "Exiting on ^C..."
