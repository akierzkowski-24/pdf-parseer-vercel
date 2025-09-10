import json
import io
import cgi
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

HTML_FORM = b"""<!doctype html>
<html><body>
  <h3>Upload a transcript PDF</h3>
  <form method="POST" enctype="multipart/form-data" action="/api/parse-transcript">
    <input type="file" name="pdf" accept="application/pdf" />
    <button type="submit">Upload</button>
  </form>
</body></html>
"""

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/api/parse-transcript':
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML_FORM)

    def do_POST(self):
        if self.path != '/api/parse-transcript':
            self.send_response(404)
            self.end_headers()
            return

        environ = {
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': self.headers.get('Content-Type', ''),
            'CONTENT_LENGTH': self.headers.get('Content-Length', ''),
        }

        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=environ)

        if 'pdf' not in form or not getattr(form['pdf'], 'file', None):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'No PDF provided'}).encode('utf-8'))
            return

        file_item = form['pdf']
        pdf_bytes = file_item.file.read()

        try:
            import pdfplumber
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
                        # Search for grade in next 15 lines
                        for j in range(15):
                            if i + j < len(lines):
                                next_line = lines[i + j].strip()
                                # Check for special case: multi-word title with "BE" (last two courses)
                                if re.search(r'[A-Za-z]+\s+[&A-Za-z]+\s+BE', next_line):
                                    i += j + 1
                                    break
                                # Parse decimal grade for other courses
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
                                break
                    else:
                        i += 1

                # Extract total credits and GPA from full text
                credits_match = re.search(r'(?:Gesamtcredits|Total Credits)\s*(\d+)', all_text, re.IGNORECASE)
                if credits_match:
                    total_credits = int(credits_match.group(1))
                
                gpa_match = re.search(r'Zwischennote\s*[\s\S]*?(\d+,\d)', all_text, re.IGNORECASE)
                if gpa_match:
                    gpa = float(gpa_match.group(1).replace(',', '.'))

                response_data = {'gpa': gpa, 'total_credits': total_credits, 'courses': courses}

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('localhost', 3000), handler)
    print('Server running on http://localhost:3000/api/parse-transcript')
    server.serve_forever()