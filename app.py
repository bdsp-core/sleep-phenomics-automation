import argparse
import logging
from app import create_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the SPA Flask application')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable debug logging (prints step-by-step trace for each request)'
    )
    args = parser.parse_args()

    app = create_app()

    if args.verbose:
        app.logger.setLevel(logging.DEBUG)
        logging.getLogger('werkzeug').setLevel(logging.DEBUG)
        app.logger.debug('Verbose/debug logging enabled')

    #app.run(debug=True, host='127.0.0.1', port=5000)
    app.run(debug=False, host='0.0.0.0', port=5000)
