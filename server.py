import sqlite3
import json, glob, re
from flask import Flask, request, render_template
from flask_restful import abort, Api, Resource
from pathlib import Path
from pydantic import ValidationError
from config import (
    FLASK_HOST, FLASK_PORT, DEBUG, DB_PATH, CORS_ALLOW,
)

from upgrade_analysis_parser.models import ChangeRecord

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


def get_db_connection(major_version: float) -> sqlite3.Connection:
    db_path = Path(DB_PATH) / f"upgrade_{major_version}.db"
    if not db_path.exists():
        abort(
            404,
            message=f"Database for version {major_version} not found. "
            "Run 'python manage.py parse --version {major_version}' first.",
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


class ChangesResource(Resource):
    def get(self, major_version: float):
        module_filter = request.args.get('module')
        model_filter = request.args.get('model')
        minor_version_filter = request.args.get('version')

        try:
            conn = get_db_connection(major_version)
            cursor = conn.cursor()

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
            conn.close()
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


api.add_resource(ChangesResource, '/<float:major_version>/changes')

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/upgrade_info')
def upgrade_info():
    support_versions = [re.search(r'upgrade_(\d*\.\d+)\.db$', f).group(1)
         for f in glob.glob(f'{DB_PATH}/upgrade_*.db')
         if re.search(r'upgrade_(\d*\.\d+)\.db$', f)]
    response = {}
    for version in support_versions:
        
        conn = get_db_connection(version)
        cursor = conn.cursor()

        query = "SELECT module, GROUP_CONCAT(all_models, ', ') AS all_models FROM ( SELECT DISTINCT module, COALESCE(model_name, record_model) AS all_models FROM changes ) AS sub GROUP BY module;"

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        data = [dict(row) for row in rows]
        response[version] = data

    return response

if __name__ == '__main__':
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG)