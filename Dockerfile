FROM nginx:alpine
# Kopiert deine Dateien in den Webserver-Ordner
COPY . /usr/share/nginx/html