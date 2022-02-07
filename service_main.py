import tornado.web
import tornado.ioloop
import tornado.httpserver

class HealthzHandler(tornado.web.RequestHandler):
    def setHeader(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")

    def get(self):
        self.setHeader()
        self.finish()

def make_app():
    return tornado.web.Application([
        (r"/healthz", HealthzHandler),
    ])


if __name__ == "__main__":
    print('=====service start======')
    app = make_app()
    server = tornado.httpserver.HTTPServer(app)
    server.listen(6225, '0.0.0.0')
    server.start(1)
    try:
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.current().stop()
        print('=====service stop======')
