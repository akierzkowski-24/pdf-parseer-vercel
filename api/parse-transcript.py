# api/parse-transcript.py
import json
import io
import cgi
import re
import base64
import pdfplumber

def handler(event, context):
    method = event['httpMethod']
    path = event['path']

    if path != '/api/parse-transcript':
        return {'statusCode': 404, 'body': ''}

    if method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/html; charset=utf-8'},
            'body': """<!doctype html> <html><body> <h3>Upload a transcript PDF</h3> <form method="POST" enctype="multipart/form-data" action="/api/parse-transcript"> <input type="file" name="pdf" accept="application/pdf" /> <button type="submit">Upload</button> </form> </body></html> """
        }

    elif method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': ''
        }

    elif method == 'POST':
        try:
            content_type = event['headers'].get('content-type', event['headers'].get('Content-Type', ''))
            body = base64.b64decode(event['body']) if event.get('isBase64Encoded', False) else event['body'].encode('utf-8')
            fp = io.BytesIO(body)
            environ = {
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': content_type,
                'CONTENT_LENGTH': str(len(body)),
            }
            form = cgi.FieldStorage(fp=fp, environ=environ, keep_blank_values=True)

            if 'pdf' not in form or not form['pdf'].file:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json; charset=utf-8'},
                    'body': json.dumps({'error': 'No PDF provided'})
                }

            pdf_bytes = form['pdf'].file.read()

            courses = []
            total_credits = None
            gpa = None
            all_text = ''
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ''
                    all_text += page_text + '\n'
            all_text = re.sub(r'[ \t]+', ' ', all_text)
            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                id_match = re.search(r'[A-Z]{2,4}\d{4,7}(?:_[A-Z])?', line)
                if id_match:
                    module_id = id_match.group(0)
                    i += 1
                    for j in range(15):
                        if i + j >= len(lines):
                            break
                        next_line = lines[i + j].strip()
                        if re.search(r'[A-Za-z]+\s+[&A-Za-z]+\s+BE', next_line):
                            i += j + 1
                            break
                        grade_match = re.search(r'\d+,\d', next_line)
                        if grade_match:
                            grade_str = grade_match.group(0)
                            try:
                                grade = float(grade_str.replace(',', '.'))
                                if 1.0 <= grade <= 5.0:
                                    courses.append({'module_id': module_id, 'grade': f"{grade:.1f}"})
                                    i += j + 1
                                    break
                            except ValueError:
                                pass
                else:
                    i += 1
            credits_match = re.search(r'(?:Gesamtcredits|Total Credits)\s*(\d+)', all_text, re.IGNORECASE)
            if credits_match:
                total_credits = int(credits_match.group(1))
            gpa_match = re.search(r'Zwischennote\s*[\s\S]*?(\d+,\d)', all_text, re.IGNORECASE)
            if gpa_match:
                gpa = float(gpa_match.group(1).replace(',', '.'))
            response_data = {'gpa': gpa, 'total_credits': total_credits, 'courses': courses}
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json; charset=utf-8',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(response_data, ensure_ascii=False)
            }
        except Exception as e:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json; charset=utf-8'},
                'body': json.dumps({'error': str(e)})
            }

    else:
        return {'statusCode': 405, 'body': 'Method Not Allowed'}
