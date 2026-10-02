# Included by every proxied location: nginx drops server-level
# proxy_set_header as soon as a location declares one of its own.
proxy_http_version 1.1;
proxy_set_header Connection        "";
proxy_set_header Host              $http_host;
proxy_set_header X-Request-Id      $req_id;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Api-Key         "";
# Always overwritten: an Authorization header from the client never reaches a
# service. Empty (and therefore not sent) when no introspection ran.
proxy_set_header Authorization     $internal_authorization;
# The gateway owns the response id, including on the errors it generates.
proxy_hide_header X-Request-Id;
proxy_connect_timeout 2s;
