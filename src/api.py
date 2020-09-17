import os
import shopify
import logging
from flask import Flask, redirect, request, render_template, abort

"""
The ScriptTag resource represents remote JavaScript code that is loaded into the pages of a shop's 
storefront or the order status page of checkout. This lets you add functionality to those pages 
without using theme templates.

"""

API_KEY = "your-api-key"
API_PW = "your-pwd"
SHOP_NAME = "your-shop-name"
API_VERSION = '2020-07'


# https://shopify.dev/docs/admin-api/access-scopes
SCOPES = ['write_script_tags',
          'read_script_tags',
          'read_products',
          'read_customers',
          'read_orders',
          'read_discounts',
]

APP_NAME = 'test'
# todo SHOP_NAME should be obtained from params, API_KEY and API_PW are part of configuration parameters
SHOP_URL = f"https://{API_KEY}:{API_PW}@{SHOP_NAME}.myshopify.com/admin"
APP_HOST = 'localhost'
APP_PORT = '8080'
APP_PROTO = 'http'
APP_AUTH_CALLBACK_URL = f"{APP_PROTO}://{APP_HOST}:{APP_PORT}/shopify_token"
APP_UNINSTALL_CALLBACK_URL = f"{APP_PROTO}://{APP_HOST}:{APP_PORT}/shopify_uninstall"
POST_INSTALL_REDIRECT_URL = f"https://{SHOP_NAME}.myshopify.com/admin/apps/"

app = Flask(__name__)

# TODO NONCES should be used ONCE per app install. Simplified for demo purpose.
NONCE = 'my-nonce'


@app.before_first_request
def setup():
    shopify.Session.setup(api_key=API_KEY, secret=API_PW)


@app.route('/shopify_install', methods=['GET'])
def app_launched():
    access_token = None
    params = request.args
    if not shopify.Session.validate_params(params):
        logging.error("Invalid params received")
        abort(400)

    shop = request.args.get('shop')
    # shop will be something like 'myshop.myshopify.com'
    if os.path.exists('ACCESS_TOKEN.txt'):
        with open('ACCESS_TOKEN.txt', 'r') as f:
            access_token = f.read()

    if access_token:
        #return render_template('welcome.html', shop=shop)
        logging.info("App was already authenticated")

    try:
        session = shopify.Session(SHOP_URL, API_VERSION)
    except shopify.api_version.VersionNotFoundError:
        logging.error("Unsoported API version has been configured")
        abort(503)
        return

    # nonce should be
    permission_url = session.create_permission_url(SCOPES, APP_AUTH_CALLBACK_URL, state=NONCE)

    return redirect(permission_url, code=302)


@app.route('/shopify_token', methods=['GET'])
def app_installed():
    params = request.args
    state = params.get('state')

    # Ok, NONCE matches, we can get rid of it now (a nonce, by definition, should only be used once)
    # Using the `code` received from Shopify we can generate an access token that is specific to the specified `shop`

    session = shopify.Session(SHOP_URL, API_VERSION)
    token = session.request_token(params)

    # TODO simple, for demo matters. It should be stored per store.
    with open('ACCESS_TOKEN.txt', 'w') as f:
        f.write(token)

    # We have an access token! Now let's register a webhook so Shopify will notify us if/when the app gets uninstalled
    # NOTE This webhook will call the #app_uninstalled function defined below
    session = shopify.Session(SHOP_URL, API_VERSION, token=token)
    shopify.ShopifyResource.activate_session(session)
    shopify.Webhook.create(dict(address=APP_UNINSTALL_CALLBACK_URL, topic="app/uninstalled"))

    return redirect(POST_INSTALL_REDIRECT_URL, code=302)


@app.route('/shopify_uninstall', methods=['GET'])
def app_uninstalled():
    params = request.args
    if not shopify.Session.validate_params(params):
        logging.error("Invalid params received")
        abort(400)

    with open('ACCESS_TOKEN.txt', 'w') as f:
        f.write('')
        logging.info("Uninstall request")
    return redirect(POST_INSTALL_REDIRECT_URL, code=302)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
