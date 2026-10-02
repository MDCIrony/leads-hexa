# Every authenticated route takes its auth lines from here, so a new location
# cannot forget them; verify-e2e.sh checks `nginx -T` for exactly that.
auth_request     /_introspect;
auth_request_set $internal_token $upstream_http_x_internal_token;
include          /etc/nginx/conf.d/proxy_headers.inc;
proxy_set_header Cookie "";
