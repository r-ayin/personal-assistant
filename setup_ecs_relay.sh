#!/bin/bash
# 添加 ECS nginx 非 SSL 端口 18801 用于 WebSocket 隧道
cat > /etc/nginx/conf.d/ws-relay-direct.conf << 'NGINX'
server {
    listen 18801;
    server_name 115.29.199.130;

    location = /ws/tunnel {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location = /ws/live {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
NGINX
nginx -t && nginx -s reload
echo "ECS relay direct port setup done"
