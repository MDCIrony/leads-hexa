# Like protected.inc, but an absent credential passes through anonymous; one
# that is present must still be valid.
auth_request     /_introspect_optional;
auth_request_set $internal_token $upstream_http_x_internal_token;
include          /etc/nginx/conf.d/proxy_headers.inc;
proxy_set_header Cookie "";
