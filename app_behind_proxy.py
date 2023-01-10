from werkzeug.middleware import proxy_fix

from estimage.webapp import create_app

app = create_app()
app.wsgi_app = proxy_fix.ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)
