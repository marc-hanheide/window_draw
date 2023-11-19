FROM python:3.10

# update packages
RUN apt-get -qq update
RUN apt-get install --yes apache2 apache2-dev
RUN pip install mod_wsgi

RUN mkdir /code
WORKDIR /code

COPY . /code/

#RUN openssl req  -nodes -new -x509  -keyout server.key -out server.cert -days 3650 -subj "/C=GB/ST=LINCS/O=Marc Hanheide/OU=Admin/CN=www.hanheide.net/emailAddress=marc@hanheide.net"
RUN pip install -r requirements.txt
RUN chown -R www-data:www-data /code
CMD mod_wsgi-express start-server /code/app.py \
    --user www-data --group www-data --url-alias /static ./static --log-to-terminal \
    --processes 1 --threads 70
#    --https-port 8443 --https-only --server-name www.hanheide.net --ssl-certificate-file ./server.cert --ssl-certificate-key-file ./server.key