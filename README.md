# Graphotti

A social drawing web app for [Lincoln West End Lights](https://www.lincoln-west-end-lights.com/)

(c) by Marc Hanheide 2016-2023


## Deployment

### Prepare environment 

* Deploy via docker compose, `docker-compose.yaml` provided.
* in deployment directory, run `mkdir -p data/logs data/images; chmod -R 777 data/`

### Prepare Apache reverse proxy:

(specific for L-CAS environment)

```
<Location /graphotti>
  SSLRequireSSL
  SetEnv HTTPS On
  SetEnv HTTP_X_FORWARDED_PROTO "https"
  #SetEnv proxy-nokeepalive 1
  Require all granted
  SetEnv "proxy-sendchunked" 
  SetEnv "proxy-sendcl"
  ProxyPass           http://10.5.39.124:8000/graphotti disablereuse=On flushpackets=on
  ProxyPassReverse    http://10.5.39.124:8000/graphotti
</Location>
```

### start service
* fire it up: `docker compose up -d`
* shut it all down: `docker compose down`





