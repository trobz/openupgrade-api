import sqlite3
import json, glob, re
from flask import Flask, request, render_template
from flask_restful import abort, Api, Resource
from pathlib import Path
from pydantic import ValidationError
from config import (
    FLASK_HOST, FLASK_PORT, DEBUG, DB_PATH, CORS_ALLOW, GOOGLE_ANALYTICS_ID, APRIORI_VERSIONS
)

from upgrade_analysis_parser.models import ChangeRecord
from upgrade_analysis_parser.processing.db import sqlite_db
from upgrade_analysis_parser.processing.apriori import get_apriori, query_apriori

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
api = Api(app)
app_name = 'openupgrade-api'

# Add headers to all responses
@app.after_request
def add_headers(response):
    # Add common security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Add CORS headers
    response.headers['Access-Control-Allow-Origin'] = CORS_ALLOW
    # Add custom headers here
    response.headers['X-Application-Name'] = app_name
    return response

class ChangesResource(Resource):
    def get(self, major_version: float):
        module_filter = request.args.get('module')
        model_filter = request.args.get('model')
        minor_version_filter = request.args.get('version')

        try:
            with sqlite_db(major_version) as cursor:
                query = "SELECT * FROM changes WHERE 1=1"
                params = []

                if module_filter:
                    query += " AND module = ?"
                    params.append(module_filter)

                if model_filter:
                    query += " AND (model_name = ? OR record_model = ?)"
                    params.extend([model_filter, model_filter])

                if minor_version_filter:
                    query += " AND version LIKE ?"
                    params.append(f"{minor_version_filter}%")

                query += " ORDER BY version DESC"

                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        except sqlite3.Error as e:
            abort(500, message=f"Database error occurred: {str(e)}")

        if not rows:
            return [], 200

        try:
            validated_changes = []
            for row in rows:
                data_dict = dict(row)
                if data_dict.get('details_json') and isinstance(data_dict['details_json'], str):
                    data_dict['details_json'] = json.loads(data_dict['details_json'])

                validated_changes.append(ChangeRecord.model_validate(data_dict))

            response_data = [record.model_dump() for record in validated_changes]
            return response_data
        except ValidationError as e:
            abort(500, message=f"Data validation error: {e}")
        except Exception as e:
            abort(500, message=f"An unexpected processing error occurred: {str(e)}")


class Apriori(Resource):
    def get(self, version: None):
        query = request.args.get('q')
        only_table = request.args.get('table')
        if only_table not in ["renamed_modules", "merged_modules"]:
            only_table = None
        if query:
            logger.info(f"GET {request.full_path}")
            return query_apriori(query, only_table)
        logger.info(f"GET {request.path}")
        apriori = get_apriori(version, only_table)
        return apriori

api.add_resource(ChangesResource, '/<float:major_version>/changes')
api.add_resource(Apriori, '/api/apriori', '/api/apriori/<string:version>', '/api/apriori/<string:version>/')

@app.route('/')
def index():
    return render_template("index.html", GOOGLE_ANALYTICS_ID=GOOGLE_ANALYTICS_ID)

@app.route('/upgrade_info')
def upgrade_info():
    support_versions = [re.search(r'(\d*\.\d+)\.db$', f).group(1)
         for f in glob.glob(f'{DB_PATH}/*.db')
         if re.search(r'(\d*\.\d+)\.db$', f)]

    response = {}
    for version in support_versions:
        with sqlite_db(version) as cursor:
            query = "SELECT module, GROUP_CONCAT(all_models, ', ') AS all_models FROM ( SELECT DISTINCT module, COALESCE(model_name, record_model) AS all_models FROM changes ) AS sub GROUP BY module;"

            cursor.execute(query)
            rows = cursor.fetchall()

            data = [dict(row) for row in rows]
            response[version] = data

    return response

@app.route('/api/apriori/support_versions')
def support_version():
    support_version = APRIORI_VERSIONS.split(',')
    return json.dumps(support_version)

if __name__ == '__main__':
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG)