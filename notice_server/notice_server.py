#!/usr/bin/env python3
import os
import sys
from wsgiref.simple_server import make_server
from pathlib import Path
import json

import filetype  # pip install filetype==1.2.0
import fitz      # pip install pymupdf==1.21.1
import multipart # pip install python-multipart==0.0.6

# Note: you really shouldn't use wsgiref.simple_server in production.
# It may have security, stability, or performance issues.

def notice_app(environ, start_response):
    # apng -- firefox: image/vnd.mozilla.apng, chrome: image/apng
    # avif, gif, jpg, png, webp, bmp, mp4, webm, 
    # gifv does not appear in the file dialog for chrome when show images (not show all files) is selected. chrome does not have mimetype for gifv
    
    file_type_dict = {
        'apng': {'mime_types': ['image/apng', 'image/png', 'image/vnd.mozilla.apng']  , 'html_tag': 'img'},
        'avif': {'mime_types': ['image/avif']              , 'html_tag': 'img'  },
        'gif' : {'mime_types': ['image/gif']               , 'html_tag': 'img'  },
        'jpg' : {'mime_types': ['image/jpeg']              , 'html_tag': 'img'  },
        'png' : {'mime_types': ['image/png']               , 'html_tag': 'img'  },
        #'svg' : {'mime_types': ['image/svg+xml']           , 'html_tag': 'img'  }, # filetype module returns None for svg files
        'webp': {'mime_types': ['image/webp']              , 'html_tag': 'img'  },
        'bmp' : {'mime_types': ['image/bmp']               , 'html_tag': 'img'  },
        #'gifv': {'mime_types': ['application/octet-stream'], 'html_tag': 'img'  }, # gifv is not a distinct file format. it is either webm or mp4. cannot download a gifv URL and get a gifv file.
        'mp4' : {'mime_types': ['video/mp4']               , 'html_tag': 'video'},
        'webm': {'mime_types': ['video/webm']              , 'html_tag': 'video'},
        'pdf' : {'mime_types': ['application/pdf']         , 'html_tag': 'NONE' } # html_tag: NONE indicates the file type is for upload and conversion only. the original file is not saved. any PDFs manually placed in the media folder will not be included in media.xml
    }
    fields = {}
    files = {}
    def on_field(field):
        fields[field.field_name] = field.value
    def on_file(file):
        files[file.field_name] = {'name': file.file_name, 'file_object': file.file_object}
    
    headers = [('Content-type', 'text/html; charset=utf-8')]
    content = 'Something went wrong.'
    content = [content.encode('utf-8')]
    status = '500 INTERNAL SERVER ERROR'

    #print(environ)
    #print(f"environ['PATH_INFO']: {environ['PATH_INFO']}")
    #print(f"environ['REQUEST_METHOD']: {environ['REQUEST_METHOD']}")

    url_path = Path(f".{environ['PATH_INFO']}")

    if environ['REQUEST_METHOD'].upper() == 'GET':
        # want to do something like url.startswith('media/') but cannot because of the different separator used by windows and posix
        # cannot use as_posix() to swap \ to / so rely on url_path.parts[0] to avoid backward and forward slashes
        # unfortunately url_path.parts[0] throws an exception when the root directory is requested, so use parts[0] sparingly
        if url_path.is_file() and url_path.parts[0] in ['media', 'assets']: # real files
            try:
                with open(url_path, 'rb') as f:
                    content = f.read()
                    content = [content]
            except IOError as e:
                print(f'Opening {url_path} failed.')
            else:
                kind = filetype.guess(url_path)
                if kind is not None: 
                    headers = [('Content-type', file_type_dict[kind.extension]['mime_types'][0])]
                    status = '200 OK'
                else:
                    content = f'Failed to get file in media/ or asset/.'
                    content = [content.encode('utf-8')]
                    status = '500 INTERNAL SERVER ERROR'
        elif url_path.is_file() and url_path.as_posix() in ['add.html', 'remove.html']: # real files
            try:
                with open(url_path, 'r') as f:
                    content = f.read()
                    content = [content.encode('utf-8')]
                    status = '200 OK'
            except IOError:
                print(f'Opening {url_path} failed.')
        elif url_path.as_posix() == 'media.xml':
            entries = sorted(Path('media').iterdir(), key=str) # iterdir does not return special directories nor subdirectories so may not be necessary to use is_file()
            files = list(filter(lambda e: e.is_file() and filetype.guess(e).extension in file_type_dict.keys(), entries))
            
            content = '<?xml version="1.0" encoding="UTF-8"?><media>'
            idx = 0
            for f in files:
                kind = filetype.guess(f)
                if kind is not None:
                    html_tag = file_type_dict[kind.extension]['html_tag']
                    if html_tag.upper() != 'NONE':
                        mtime = os.path.getmtime(f)
                        # if a new file with the same name as a file that has already been cached by browser is uploaded, then the new file will not be displayed by the browser
                        # to get around this caching problem append ? and the mtime of the file
                        # if a new file is uploaded the mtime will be different than the cached file so the browser will download the new file
                        # the mtime only changes when a new version is upload, so the browser can still take advantage of the cache
                        # an alternate solution is to have the html file use javascript to reload the page when a change in the media.xml results is detected
                        f = f"{f}?v={mtime}"
                        content += f'<file id="{idx}"><file_path>{f}</file_path><html_tag>{html_tag}</html_tag><file_mtime>{mtime}</file_mtime></file>'
                        idx += 1
            if idx > 0:
                content += '</media>'
                headers = [('Content-type', 'application/xml; charset=utf-8')]
                content = [content.encode('utf-8')]
                status = '200 OK'
            else:
                content = f'Failed to create media.xml.'
                content = [content.encode('utf-8')]
                status = '500 INTERNAL SERVER ERROR'
        elif url_path.as_posix() == 'types.json':
            content = json.dumps(file_type_dict)
            headers = [('Content-type', 'text/json; charset=utf-8')]
            content = [content.encode('utf-8')] 
            status = '200 OK'
        else:
            try:
                with open('index.html') as f: # real file
                    content = f.read()
                    content = [content.encode('utf-8')]
                    status = '200 OK'
            except IOError:
                print('Opening index.html failed.')

    elif environ['REQUEST_METHOD'].upper() in ['POST', 'PUT']: 
        if url_path.as_posix() == 'upload':
            # the body of the POST contains filename and Content-Type.
            # having Content-Type might be useful but not sure if I need it.
            # how to see the beginning of the body (very rough example)
            #body = environ['wsgi.input']
            #data = body.peek()[0:256]
            #print(data)
        
            multipart_headers = {'Content-Type': environ['CONTENT_TYPE']}
            multipart_headers['Content-Length'] = environ['CONTENT_LENGTH']
            multipart.parse_form(multipart_headers, environ['wsgi.input'], on_field, on_file)

            for each_file, each_file_details in files.items():
                status = -1
                fname = each_file_details['name'].decode('utf-8')
                kind = filetype.guess(each_file_details['file_object'])
                print(kind.extension)
                if kind is not None:
                    if kind.extension in file_type_dict.keys() and file_type_dict[kind.extension]['html_tag'].upper() != 'NONE':
                        try:
                            with open(f'media/{fname}', 'wb') as f:
                                uploaded_file = each_file_details['file_object']
                                uploaded_file.seek(0)
                                f.write(uploaded_file.read())
                                status = 0
                        except IOError as e:
                            status = -2
                            print(f'Saving {fname} failed.')
                    elif kind.extension == 'pdf':
                        # convert first page of pdf to png and save it
                        doc = fitz.open('pdf', stream=each_file_details['file_object'])
                        page = doc.load_page(0) # get first page only
                        pix = page.get_pixmap()
                        output = f'media/{fname}.png'
                        pix.save(output)
                        doc.close()
                        status = 0
                    #else not a supported file type and upload will be rejected

                if status == 0:
                    content = 'Upload finished.'
                    content = [content.encode('utf-8')]
                    status = '200 OK'
                elif status == -1:
                    content = f'Upload failed for {fname}. Unsupported file type.'
                    content = [content.encode('utf-8')]
                    status = '415 Unsupported Media Type'
                elif status == -2:
                    content = f'Upload failed for {fname}. Could not save file.'
                    content = [content.encode('utf-8')]
                    status = '500 INTERNAL SERVER ERROR'

    elif environ['REQUEST_METHOD'].upper() == 'DELETE':
        if url_path.as_posix() == 'delete':
            multipart_headers = {'Content-Type': environ['CONTENT_TYPE']}
            multipart_headers['Content-Length'] = environ['CONTENT_LENGTH']
            multipart.parse_form(multipart_headers, environ['wsgi.input'], on_field, on_file)
            for key, value in fields.items():
                fname = value.decode('utf-8')
                fname = fname.split('?', 1)[0]
                try:
                    os.remove(f'{fname}')
                except OSError as e:
                    content = 'Delete failed.'
                    content = [content.encode('utf-8')]
                    status = '500 INTERNAL SERVER ERROR'
                else:
                    content = 'Delete successful.'
                    content = [content.encode('utf-8')]
                    status = '200 OK'


    start_response(status, headers)
    return content
notice_app.str_current_image = ''

    
if __name__ == "__main__":
    port = 8080 # need root permissions to run on port 80.
    use_ssl = False
    usage = """
-h or unexpected arguments used.

Usage examples:
notice_server.py       # runs an http  server on port 8080
notice_server.py 8081  # runs an http  server on port 8081
notice_server.py ssl   # runs an https server on port 8080. A SSL certificate is required.
notice_server.py 80    # runs an http  server on port 80 (standard web server port). You need root permissions to run this. It is not recommended to run this program as root.
notice_server.py ssl N # runs an https server on port N. You need root permission for ports below 1024.
notice_server.py -h    # prints this message"""

    if len(sys.argv) == 2:
        if sys.argv[1].isnumeric():
            port = int(sys.argv[1])
        elif sys.argv[1].lower() == 'ssl':
            use_ssl = true
        else:
            print(usage)
            exit(-1)
    elif len(sys.argv) == 3:
        if sys.argv[1].isnumeric():
            port = int(sys.argv[1])
        elif sys.argv[2].isnumeric():
            port = int(sys.argv[2])
        else:
            print(usage)
            exit(-1)

        if sys.argv[1].lower() == 'ssl' or sys.argv[2].lower() == 'ssl':
            use_ssl = True
        else:
            print(usage)
            exit(-1)

    elif len(sys.argv) != 1:
      print(usage)
      exit(-1)


    with make_server('', port, notice_app) as httpd:
        protocol = 'http'
        if use_ssl:
            import ssl
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain('../server.pem')   # need to run something like the following to get a self-signed SSL certificate if you want to use https: openssl req -new -x509 -days 999 -nodes -out ../server.pem -keyout ../server.pem
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
            protocol = 'https'
        print(f"Serving {protocol} on port {port}...")
        httpd.serve_forever()
